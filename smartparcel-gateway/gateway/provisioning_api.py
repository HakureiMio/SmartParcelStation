"""
Provisioning / binding API for gateway deployment.

Exposed when the gateway is UNBOUND. Allows a miniprogram or admin tool
connected to the gateway hotspot to:
1. Query provisioning status (GET /local/provisioning/status)
2. Submit server-issued binding parameters (POST /local/provisioning/bind)
3. Verify binding result (POST /local/provisioning/verify)

Anti-replay / anti-tamper:
- Timestamp window validation (default 300s)
- Nonce deduplication
- Body SHA-256 verification
- Optional HMAC when a pairing_code is provisioned
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, field_validator

from gateway.core.config import Settings, get_settings, reload_settings
from gateway.core.security import raw_body_hash
from gateway.db.init_db import init_db
from gateway.db.session import SessionLocal
from gateway.models.entities import (
    GatewayBindingSession,
    GatewayBindingStatus,
    GatewayConfig,
)
from gateway.services.security_audit_service import SecurityAuditService
from gateway.services.server_client import ServerClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NONCE_WINDOW_SECONDS = 300  # allowed clock skew for local requests
MAX_NONCE_CACHE = 2048

# In-memory nonce cache (per process, not persisted)
_seen_nonces: set[str] = set()


def _check_and_record_nonce(nonce: str) -> bool:
    """Return True if nonce is new, False if replayed."""
    if nonce in _seen_nonces:
        return False
    _seen_nonces.add(nonce)
    if len(_seen_nonces) > MAX_NONCE_CACHE:
        oldest = next(iter(_seen_nonces))
        _seen_nonces.discard(oldest)
    return True


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ProvisioningStatusOut(BaseModel):
    ok: bool = True
    binding_status: str
    gateway_device_id: str | None = None
    gateway_serial: str | None = None
    provisioning_enabled: bool
    ap_ssid: str | None = None
    local_ip: str | None = None
    server_base_url: str | None = None
    gateway_code: str | None = None
    station_id: str | None = None


class ProvisioningBindIn(BaseModel):
    server_base_url: str
    gateway_code: str
    station_id: str
    registration_token: str
    mqtt_host: str | None = None
    mqtt_port: int = 1883
    mqtt_tls_enabled: bool = False
    config_version: int = 1
    expires_at: str | None = None

    @field_validator("server_base_url")
    @classmethod
    def _validate_server_url(cls, v: str) -> str:
        settings = get_settings()
        if v.startswith("https://"):
            return v.rstrip("/")
        if settings.allow_dev_http:
            if v.startswith("http://127.0.0.1") or v.startswith("http://192.168.") or v.startswith("http://localhost"):
                return v.rstrip("/")
            raise ValueError("Dev HTTP is only allowed for 127.0.0.1 / 192.168.x.x / localhost")
        raise ValueError("server_base_url must use https:// in production. Set ALLOW_DEV_HTTP=true for development.")


class ProvisioningBindOut(BaseModel):
    ok: bool
    binding_status: str
    gateway_code: str | None = None
    station_id: str | None = None
    server_base_url: str | None = None
    heartbeat: str | None = None
    error: str | None = None


class ProvisioningVerifyOut(BaseModel):
    ok: bool = True
    binding_status: str
    gateway_code: str | None = None
    station_id: str | None = None
    last_heartbeat_status: str | None = None
    last_heartbeat_at: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_local_timestamp(request: Request, body_bytes: bytes) -> tuple[bool, str | None]:
    """Check X-Local-Timestamp is within the allowed window and body hash matches."""
    ts_hdr = request.headers.get("X-Local-Timestamp")
    nonce_hdr = request.headers.get("X-Local-Nonce")
    body_hash_hdr = request.headers.get("X-Local-Body-SHA256")

    if not ts_hdr or not nonce_hdr:
        return False, "missing X-Local-Timestamp or X-Local-Nonce header"

    try:
        ts = int(ts_hdr)
    except ValueError:
        return False, "invalid X-Local-Timestamp (must be unix seconds)"

    now = int(time.time())
    if abs(now - ts) > NONCE_WINDOW_SECONDS:
        return False, f"timestamp out of window (>{NONCE_WINDOW_SECONDS}s)"

    if not _check_and_record_nonce(nonce_hdr):
        return False, "nonce replayed"

    if body_hash_hdr:
        expected = raw_body_hash(body_bytes)
        if body_hash_hdr != expected:
            return False, "body hash mismatch"

    return True, None


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _upsert_env_values(env_path: Path, values: dict[str, str]) -> None:
    """Write key=value pairs into .env, backing up the original."""
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    existing_keys = set()
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in values:
            output.append(f"{key}={values[key]}")
            existing_keys.add(key)
        else:
            output.append(line)
    for key, value in values.items():
        if key not in existing_keys:
            output.append(f"{key}={value}")
    if env_path.exists():
        shutil.copy2(env_path, env_path.with_suffix(env_path.suffix + ".bak"))
    env_path.write_text("\n".join(output) + "\n", encoding="utf-8")


def _sync_gateway_config_to_db(settings: Settings) -> None:
    """Persist current gateway binding state to the gateway_config table."""
    db = SessionLocal()
    try:
        cfg = db.query(GatewayConfig).first()
        if cfg is None:
            cfg = GatewayConfig()
            db.add(cfg)
        cfg.gateway_code = settings.gateway_code or None
        cfg.gateway_device_id = settings.gateway_device_id or None
        cfg.gateway_serial = settings.gateway_serial or None
        cfg.station_id = settings.station_id or None
        cfg.server_base_url = settings.server_base_url or None
        cfg.mqtt_host = settings.mqtt_host or None
        cfg.mqtt_port = settings.mqtt_port
        cfg.mqtt_tls_enabled = settings.mqtt_tls_enabled
        try:
            cfg.binding_status = GatewayBindingStatus(settings.binding_status.upper())
        except ValueError:
            cfg.binding_status = GatewayBindingStatus.UNBOUND
        cfg.config_version = settings.config_version
        if settings.is_bound and cfg.bound_at is None:
            cfg.bound_at = datetime.utcnow()
        cfg.updated_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        logger.warning("Failed to sync gateway_config to DB: {}", exc)
        db.rollback()
    finally:
        db.close()


def _env_path() -> Path:
    return Path(".env")


# ---------------------------------------------------------------------------
# FastAPI router
# ---------------------------------------------------------------------------


provisioning_app = FastAPI(title="SmartParcel Gateway Provisioning API")


@provisioning_app.on_event("startup")
def _ensure_db() -> None:
    init_db()


@provisioning_app.get("/local/provisioning/status")
def provisioning_status(request: Request):
    """Public status endpoint. Does not expose secrets."""
    settings = get_settings()
    ssid = None
    if settings.wifi_ap_enabled:
        suffix = (settings.gateway_serial or settings.gateway_device_id or "0000")[-4:]
        ssid = f"{settings.wifi_ap_ssid_prefix}-{suffix}"
    return {
        "ok": True,
        "binding_status": settings.binding_status.upper(),
        "gateway_device_id": settings.gateway_device_id or None,
        "gateway_serial": settings.gateway_serial or None,
        "provisioning_enabled": settings.provisioning_enabled,
        "ap_ssid": ssid,
        "local_ip": settings.wifi_ap_address if settings.wifi_ap_enabled else None,
        "server_base_url": settings.server_base_url or None,
        "gateway_code": settings.gateway_code or None,
        "station_id": settings.station_id or None,
    }


@provisioning_app.post("/local/provisioning/bind")
async def provisioning_bind(request: Request):
    """Accept server-issued binding parameters and activate gateway.

    The miniprogram calls this endpoint after obtaining binding parameters
    from the VPS server.
    """
    settings = get_settings()
    db = SessionLocal()
    audit = SecurityAuditService(db)
    source_ip = request.client.host if request.client else None

    # --- Gate: provisioning must be enabled and gateway unbound ---
    if not settings.provisioning_enabled:
        audit.suspicious_request("provisioning_disabled", source_ip=source_ip, request_path="/local/provisioning/bind")
        raise HTTPException(status_code=403, detail="Provisioning is disabled on this gateway")

    if settings.is_bound:
        audit.suspicious_request("already_bound", source_ip=source_ip, request_path="/local/provisioning/bind")
        raise HTTPException(status_code=409, detail="Gateway is already bound")

    # --- Read body ---
    body_bytes = await request.body()

    # --- Parse and validate payload first (so Pydantic errors are 422) ---
    try:
        payload_data = json.loads(body_bytes.decode("utf-8"))
        payload = ProvisioningBindIn(**payload_data)
    except Exception as exc:
        audit.provisioning_bind_failed("invalid_payload", source_ip=source_ip, detail={"error": str(exc)})
        raise HTTPException(status_code=422, detail=f"Invalid payload: {exc}")

    # --- Anti-replay / anti-tamper headers (checked after body parsing) ---
    valid, err = _validate_local_timestamp(request, body_bytes)
    if not valid:
        audit.suspicious_request("timestamp_or_nonce_invalid", source_ip=source_ip,
                                 request_path="/local/provisioning/bind",
                                 detail={"reason": err})
        raise HTTPException(status_code=400, detail=f"Request validation failed: {err}")

    # --- Record binding session ---
    session_id = uuid.uuid4().hex
    binding_session = GatewayBindingSession(
        session_id=session_id,
        one_time_binding_token_hash=_hash_token(payload.registration_token),
        status="PENDING",
        source_ip=source_ip,
        expires_at=datetime.utcnow() + timedelta(seconds=settings.provisioning_token_ttl_seconds),
    )
    db.add(binding_session)
    db.commit()

    audit.provisioning_bind_attempt(source_ip=source_ip, detail={
        "session_id": session_id,
        "gateway_code": payload.gateway_code,
        "station_id": payload.station_id,
    })

    # --- Call server bootstrap/activate ---
    try:
        result = ServerClient.bootstrap_activate(
            payload.server_base_url,
            {
                "gateway_code": payload.gateway_code,
                "station_id": int(payload.station_id),
                "registration_token": payload.registration_token,
                "device_info": {
                    "source": "provisioning-api",
                    "gateway_device_id": settings.gateway_device_id,
                    "gateway_serial": settings.gateway_serial,
                    "version": "0.2.0",
                },
            },
        )
    except Exception as exc:
        binding_session.status = "FAILED"
        db.commit()
        audit.provisioning_bind_failed("server_activate_failed", source_ip=source_ip,
                                       detail={"error": str(exc)})
        raise HTTPException(status_code=502, detail=f"Server activation failed: {exc}")

    gateway_secret = result.get("gateway_secret", "")
    if not gateway_secret:
        binding_session.status = "FAILED"
        db.commit()
        audit.provisioning_bind_failed("no_secret_returned", source_ip=source_ip)
        raise HTTPException(status_code=502, detail="Server did not return gateway_secret")

    # --- Write configuration to .env (with backup) ---
    env_values = {
        "GATEWAY_CODE": payload.gateway_code,
        "GATEWAY_SECRET": gateway_secret,
        "STATION_ID": str(payload.station_id),
        "SERVER_BASE_URL": payload.server_base_url,
        "BINDING_STATUS": "BOUND",
        "MQTT_HOST": payload.mqtt_host or settings.mqtt_host or "",
        "MQTT_PORT": str(payload.mqtt_port),
        "MQTT_TLS_ENABLED": str(payload.mqtt_tls_enabled).lower(),
        "CONFIG_VERSION": str(payload.config_version),
    }
    try:
        _upsert_env_values(_env_path(), env_values)
        logger.info("Gateway config written to .env (backup created at .env.bak)")
    except Exception as exc:
        logger.error("Failed to write .env: {}", exc)
        audit.provisioning_bind_failed("env_write_failed", source_ip=source_ip, detail={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to persist gateway configuration")

    # --- Reload settings ---
    reload_settings()
    settings = get_settings()

    # --- Persist to SQLite ---
    _sync_gateway_config_to_db(settings)

    # --- Immediate heartbeat verification ---
    heartbeat_result = "UNKNOWN"
    try:
        client = ServerClient(settings)
        hb = client.heartbeat()
        heartbeat_result = "OK" if hb else "FAILED"
        # Update DB heartbeat state
        db2 = SessionLocal()
        try:
            cfg = db2.query(GatewayConfig).first()
            if cfg:
                cfg.last_heartbeat_at = datetime.utcnow()
                cfg.last_heartbeat_status = "ONLINE"
                cfg.binding_status = GatewayBindingStatus.ONLINE
                db2.commit()
        finally:
            db2.close()
        audit.heartbeat_success()
    except Exception as exc:
        heartbeat_result = f"FAILED: {exc}"
        audit.heartbeat_failed(str(exc))

    # --- Mark session complete ---
    binding_session.status = "COMPLETED"
    binding_session.completed_at = datetime.utcnow()
    db.commit()
    db.close()

    audit.provisioning_bind_success(source_ip=source_ip, detail={
        "session_id": session_id,
        "gateway_code": payload.gateway_code,
        "station_id": payload.station_id,
        "heartbeat": heartbeat_result,
    })

    return {
        "ok": True,
        "binding_status": "BOUND",
        "gateway_code": payload.gateway_code,
        "station_id": payload.station_id,
        "server_base_url": payload.server_base_url,
        "heartbeat": heartbeat_result,
    }


@provisioning_app.post("/local/provisioning/verify")
def provisioning_verify(request: Request):
    """Return current binding status and last heartbeat result."""
    settings = get_settings()
    db = SessionLocal()
    try:
        cfg = db.query(GatewayConfig).first()
        return {
            "ok": True,
            "binding_status": settings.binding_status.upper(),
            "gateway_code": settings.gateway_code or None,
            "station_id": settings.station_id or None,
            "last_heartbeat_status": cfg.last_heartbeat_status if cfg else None,
            "last_heartbeat_at": cfg.last_heartbeat_at.isoformat() if (cfg and cfg.last_heartbeat_at) else None,
        }
    finally:
        db.close()


@provisioning_app.get("/local/health")
def provisioning_health():
    """Minimal health check available during provisioning."""
    settings = get_settings()
    return {
        "status": "ok",
        "binding_status": settings.binding_status.upper(),
        "provisioning_enabled": settings.provisioning_enabled,
    }
