"""
SmartParcel Gateway Local API.

Provides:
- /local/health           — always available
- /local/gate/access-card — gate access control (requires local auth when bound)
- /local/tags/*           — BLE tag management (requires local auth when bound)
- /local/provisioning/*   — served by provisioning_api when unbound

Authentication:
- When BINDING_STATUS=UNBOUND, only /local/health and /local/provisioning/* are open.
- When BOUND, business endpoints require Authorization: Bearer <local_session_token>.
"""

from __future__ import annotations

import re
import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from gateway.core.config import get_settings
from gateway.db.init_db import init_db
from gateway.db.session import SessionLocal
from gateway.local_api_auth import validate_gate_reader_auth, validate_local_session
from gateway.models.entities import GateAuthSession, GateAuthStatus, LocalTag, TagStatus
from gateway.services.access_control_service import AccessControlService
from gateway.services.ble import get_ble_tag_service
from gateway.services.ble.adapter import RealBleCommandService
from gateway.services.server_client import ServerClient
from gateway.services.sync_service import SyncService
from gateway.services.task_service import TaskService

app = FastAPI(title="SmartParcel Gateway Local API")
FACTORY_BLE_NAME_RE = re.compile(r"^SPS-[A-Z0-9]{2,8}-[0-9]{8}-[0-9]{4,8}$")
LEGACY_BLE_NAME_RE = re.compile(r"^SPS-TAG-[0-9A-Fa-f]{4,8}$")


@app.on_event("startup")
def ensure_local_database_schema() -> None:
    init_db()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class GateAccessIn(BaseModel):
    reader_id: str
    credential_type: str = "CARD_UID"
    credential_value: str


class ScanTagsIn(BaseModel):
    timeout_sec: float = 5.0


class RegisterFromBleIn(BaseModel):
    ble_name: str
    ble_address: str


class WakeTagIn(BaseModel):
    color: str = "BLUE"
    duration_sec: int = 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.utcnow()


def _is_valid_ble_name(ble_name: str) -> bool:
    return bool(FACTORY_BLE_NAME_RE.match(ble_name) or LEGACY_BLE_NAME_RE.match(ble_name))


def _next_local_no(db) -> int:
    current = db.scalar(select(func.max(LocalTag.local_no))) or 0
    return int(current) + 1


def _tag_status_value(tag: LocalTag) -> str:
    status = tag.status
    return status.value if hasattr(status, "value") else str(status)


def _tag_summary(tag: LocalTag) -> dict:
    return {
        "tag_id": tag.tag_id,
        "display_name": tag.display_name,
        "local_no": tag.local_no,
        "status": _tag_status_value(tag),
        "battery_mv": tag.battery_mv,
        "battery_level": tag.battery_level,
        "last_seen_at": tag.last_seen_at.isoformat() if tag.last_seen_at else None,
        "ble_name": tag.ble_name,
        "ble_address": tag.ble_address,
    }


def _tag_detail(tag: LocalTag) -> dict:
    data = _tag_summary(tag)
    data.update(
        {
            "tag_uid": tag.tag_uid,
            "registered_at": tag.registered_at.isoformat() if tag.registered_at else None,
            "last_connected_at": tag.last_connected_at.isoformat() if tag.last_connected_at else None,
            "hw_model": tag.hw_model,
            "fw_version": tag.fw_version,
        }
    )
    return data


def _find_tag(db, tag_id: str) -> LocalTag:
    tag = db.scalar(select(LocalTag).where(LocalTag.tag_id == tag_id))
    if tag is None:
        raise HTTPException(status_code=404, detail=f"tag not found: {tag_id}")
    return tag


def _require_ble_address(tag: LocalTag) -> str:
    if not tag.ble_address:
        raise HTTPException(status_code=400, detail="tag has no ble_address")
    return tag.ble_address


def _apply_ble_result(tag: LocalTag, result: dict, success_status: TagStatus | None = None) -> None:
    if result.get("ok"):
        if success_status is not None:
            tag.status = success_status
        tag.last_seen_at = _now()
        if "battery_mv" in result:
            tag.battery_mv = result.get("battery_mv")
        if "battery_level" in result:
            tag.battery_level = result.get("battery_level")
        return

    tag.status = TagStatus.ERROR
    tag.last_error_type = result.get("error") or "ble_error"
    tag.last_error_message = result.get("message")
    tag.last_error_at = _now()


# ---------------------------------------------------------------------------
# Public endpoint (always available)
# ---------------------------------------------------------------------------


@app.get("/local/health")
def local_health():
    settings = get_settings()
    return {
        "status": "ok",
        "gateway_code": settings.gateway_code or None,
        "station_id": settings.station_id or None,
        "binding_status": settings.binding_status.upper(),
    }


# ---------------------------------------------------------------------------
# Authenticated endpoints (require Bearer token when BOUND)
# ---------------------------------------------------------------------------


@app.post("/local/gate/access-card")
def gate_access_card(
    payload: GateAccessIn,
    auth: dict = Depends(validate_gate_reader_auth),
):
    settings = get_settings()
    if payload.reader_id != auth["reader_id"]:
        raise HTTPException(status_code=403, detail="reader_id does not match authenticated reader")
    db = SessionLocal()
    try:

        def _lookup_ble_address(tag_id: str) -> str | None:
            tag = db.scalar(select(LocalTag).where(LocalTag.tag_id == tag_id))
            return tag.ble_address if tag else None

        ble_service = RealBleCommandService(address_lookup=_lookup_ble_address)
        service = AccessControlService(
            db,
            SyncService(db, ServerClient(settings), settings.station_id),
            TaskService(db),
            ble_service,
            settings.station_id,
            gateway_code=settings.gateway_code,
            auth_result_ttl_seconds=settings.gate_auth_result_ttl_seconds,
        )
        result = service.handle_access_card(
            reader_id=payload.reader_id,
            credential_type=payload.credential_type,
            credential_value=payload.credential_value,
        )
        gate_session = GateAuthSession(
            session_id=result.get("pickup_session_id") or f"card_{uuid.uuid4().hex}",
            auth_method="CARD_UID", reader_id=payload.reader_id, gateway_code=settings.gateway_code,
            station_id=settings.station_id,
            status=GateAuthStatus.GRANTED if result["access"] == "GRANTED" else GateAuthStatus.DENIED,
            user_id=result.get("user_id"), pickup_count=result.get("pickup_count", 0),
            parcel_codes_json=json.dumps([item["parcel_code"] for item in result.get("items", [])]),
            shelves_json=json.dumps(result.get("shelves", [])), session_color=result.get("session_color"),
            display_text=result.get("display_text", ""), reason=result.get("reason"), confirmed_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=settings.gate_auth_result_ttl_seconds),
        )
        db.add(gate_session); db.commit()
        return result
    finally:
        db.close()


def _gate_session_result(row: GateAuthSession) -> dict:
    if row.status == GateAuthStatus.PENDING and row.expires_at and row.expires_at < datetime.utcnow():
        row.status = GateAuthStatus.EXPIRED
        row.reason, row.display_text = "AUTH_RESULT_EXPIRED", "认证结果已过期"
    return {
        "ok": True, "status": row.status.value, "auth_method": row.auth_method,
        "reader_id": row.reader_id, "user_id": row.user_id, "pickup_count": row.pickup_count,
        "parcel_codes": json.loads(row.parcel_codes_json or "[]"), "shelves": json.loads(row.shelves_json or "[]"),
        "session_color": row.session_color, "display_text": row.display_text, "reason": row.reason,
        "session_id": row.session_id,
    }


@app.get("/local/gate/qr-session")
def gate_qr_session(reader_id: str, auth: dict = Depends(validate_gate_reader_auth)):
    if reader_id != auth["reader_id"]: raise HTTPException(status_code=403, detail="reader_id mismatch")
    settings = get_settings(); now = int(time.time()); expires = now + settings.gate_qr_ttl_seconds
    session_id, nonce = f"qr_{uuid.uuid4().hex}", secrets.token_urlsafe(16)
    params = {"v": "1", "gateway_code": settings.gateway_code, "reader_id": reader_id,
              "station_id": settings.station_id, "session_id": session_id, "nonce": nonce, "expires_at": str(expires)}
    signature = hmac.new(settings.gateway_secret.encode(), urlencode(params).encode(), hashlib.sha256).hexdigest()
    params["signature"] = signature; qr_payload = "sps://gate-qr?" + urlencode(params)
    db = SessionLocal()
    try:
        db.add(GateAuthSession(session_id=session_id, auth_method="GATE_QR", reader_id=reader_id,
            gateway_code=settings.gateway_code, station_id=settings.station_id,
            nonce_hash=hashlib.sha256(nonce.encode()).hexdigest(), challenge_payload=qr_payload,
            status=GateAuthStatus.PENDING, expires_at=datetime.utcnow() + timedelta(seconds=settings.gate_qr_ttl_seconds)))
        db.commit()
    finally: db.close()
    return {"ok": True, "auth_method": "GATE_QR", "session_id": session_id, "reader_id": reader_id,
            "gateway_code": settings.gateway_code, "station_id": settings.station_id, "nonce": nonce,
            "expires_at": expires, "qr_payload": qr_payload}


@app.get("/local/gate/nfc-payload")
def gate_nfc_payload(reader_id: str, auth: dict = Depends(validate_gate_reader_auth)):
    if reader_id != auth["reader_id"]: raise HTTPException(status_code=403, detail="reader_id mismatch")
    settings = get_settings()
    params = {"v": "1", "gateway_code": settings.gateway_code, "reader_id": reader_id,
              "station_id": settings.station_id, "gate_nfc_tag_id": settings.gate_nfc_tag_id}
    return {"ok": True, "auth_method": "GATE_NFC_TAG", "reader_id": reader_id,
            "gateway_code": settings.gateway_code, "station_id": settings.station_id,
            "gate_nfc_tag_id": settings.gate_nfc_tag_id, "nfc_payload": "sps://gate-nfc?" + urlencode(params)}


@app.get("/local/gate/auth-result")
def gate_auth_result(reader_id: str, auth: dict = Depends(validate_gate_reader_auth)):
    if reader_id != auth["reader_id"]: raise HTTPException(status_code=403, detail="reader_id mismatch")
    db = SessionLocal()
    try:
        row = db.scalar(select(GateAuthSession).where(GateAuthSession.reader_id == reader_id).order_by(GateAuthSession.created_at.desc()))
        if row is None: return {"ok": True, "status": "PENDING", "display_text": "请刷卡 / 扫码 / 手机 NFC"}
        result = _gate_session_result(row); db.commit(); return result
    finally: db.close()


@app.get("/local/gate/auth-session/{session_id}/result")
def gate_auth_session_result(session_id: str, auth: dict = Depends(validate_gate_reader_auth)):
    db = SessionLocal()
    try:
        row = db.scalar(select(GateAuthSession).where(GateAuthSession.session_id == session_id,
                                                       GateAuthSession.reader_id == auth["reader_id"]))
        if row is None: raise HTTPException(status_code=404, detail="gate auth session not found")
        result = _gate_session_result(row); db.commit(); return result
    finally: db.close()


@app.post("/local/tags/scan")
async def scan_tags(
    payload: ScanTagsIn,
    auth: dict = Depends(validate_local_session),
):
    db = SessionLocal()
    try:
        items = await get_ble_tag_service().scan_tags(payload.timeout_sec)
        merged = []
        now = _now()
        for item in items:
            ble_name = item.get("ble_name")
            ble_address = item.get("ble_address")
            if item.get("ok") is False:
                merged.append(item)
                continue

            tag = None
            if ble_name or ble_address:
                tag = db.scalar(
                    select(LocalTag).where(
                        or_(
                            LocalTag.ble_name == ble_name,
                            LocalTag.tag_uid == ble_name,
                            LocalTag.ble_address == ble_address,
                        )
                    )
                )
            data = dict(item)
            if tag:
                tag.last_seen_at = now
                tag.ble_address = ble_address or tag.ble_address
                data.update(
                    {
                        "registered": True,
                        "tag_id": tag.tag_id,
                        "local_no": tag.local_no,
                        "display_name": tag.display_name,
                        "status": _tag_status_value(tag),
                        "last_seen_at": tag.last_seen_at.isoformat(),
                    }
                )
            else:
                data.update({"registered": False, "local_no": None, "display_name": None})
            merged.append(data)
        db.commit()
        return {"ok": True, "items": merged}
    finally:
        db.close()


@app.post("/local/tags/register-from-ble")
def register_from_ble(
    payload: RegisterFromBleIn,
    auth: dict = Depends(validate_local_session),
):
    ble_name = payload.ble_name.strip()
    ble_address = payload.ble_address.strip()
    if not _is_valid_ble_name(ble_name):
        raise HTTPException(status_code=400, detail="invalid ble_name")

    db = SessionLocal()
    try:
        now = _now()
        tag = db.scalar(
            select(LocalTag).where(
                or_(
                    LocalTag.ble_name == ble_name,
                    LocalTag.tag_uid == ble_name,
                    LocalTag.tag_id == ble_name,
                )
            )
        )
        if tag is None:
            local_no = _next_local_no(db)
            tag = LocalTag(
                tag_id=f"SPS-TAG-{local_no:04d}",
                tag_uid=ble_name,
                ble_name=ble_name,
                ble_address=ble_address,
                local_no=local_no,
                display_name=f"标签 {local_no:03d}",
                encrypted_token="",
                station_id=str(get_settings().station_id),
                status=TagStatus.ONLINE,
                registered_at=now,
                last_seen_at=now,
            )
            db.add(tag)
        else:
            tag.tag_uid = tag.tag_uid or ble_name
            tag.ble_name = tag.ble_name or ble_name
            tag.ble_address = ble_address
            tag.local_no = tag.local_no or _next_local_no(db)
            tag.display_name = tag.display_name or f"标签 {tag.local_no:03d}"
            tag.registered_at = tag.registered_at or now
            tag.last_seen_at = now
            tag.status = TagStatus.ONLINE
        db.commit()
        db.refresh(tag)
        return {"ok": True, "item": _tag_detail(tag)}
    finally:
        db.close()


@app.get("/local/tags")
def list_tags(
    auth: dict = Depends(validate_local_session),
):
    db = SessionLocal()
    try:
        items = list(db.scalars(select(LocalTag).order_by(LocalTag.local_no.asc(), LocalTag.created_at.desc())))
        return {"ok": True, "items": [_tag_summary(item) for item in items]}
    finally:
        db.close()


@app.get("/local/tags/{tag_id}")
def get_tag(
    tag_id: str,
    auth: dict = Depends(validate_local_session),
):
    db = SessionLocal()
    try:
        return {"ok": True, "item": _tag_detail(_find_tag(db, tag_id))}
    finally:
        db.close()


@app.post("/local/tags/{tag_id}/connect")
async def connect_tag(
    tag_id: str,
    auth: dict = Depends(validate_local_session),
):
    db = SessionLocal()
    try:
        tag = _find_tag(db, tag_id)
        result = await get_ble_tag_service().connect_tag(_require_ble_address(tag))
        if result.get("ok"):
            tag.status = TagStatus.ONLINE
            tag.last_connected_at = _now()
        else:
            _apply_ble_result(tag, result)
        db.commit()
        return {"ok": bool(result.get("ok")), "result": result, "item": _tag_detail(tag)}
    finally:
        db.close()


@app.post("/local/tags/{tag_id}/wake")
async def wake_tag(
    tag_id: str,
    payload: WakeTagIn,
    auth: dict = Depends(validate_local_session),
):
    db = SessionLocal()
    try:
        tag = _find_tag(db, tag_id)
        result = await get_ble_tag_service().wake_tag(_require_ble_address(tag), payload.color, payload.duration_sec)
        _apply_ble_result(tag, result, TagStatus.RUNNING)
        db.commit()
        return {"ok": bool(result.get("ok")), "result": result, "item": _tag_detail(tag)}
    finally:
        db.close()


@app.post("/local/tags/{tag_id}/stop")
async def stop_tag(
    tag_id: str,
    auth: dict = Depends(validate_local_session),
):
    db = SessionLocal()
    try:
        tag = _find_tag(db, tag_id)
        result = await get_ble_tag_service().stop_alert(_require_ble_address(tag))
        _apply_ble_result(tag, result, TagStatus.ONLINE)
        db.commit()
        return {"ok": bool(result.get("ok")), "result": result, "item": _tag_detail(tag)}
    finally:
        db.close()


@app.get("/local/tags/{tag_id}/status")
async def read_tag_status(
    tag_id: str,
    auth: dict = Depends(validate_local_session),
):
    db = SessionLocal()
    try:
        tag = _find_tag(db, tag_id)
        result = await get_ble_tag_service().read_status(_require_ble_address(tag))
        _apply_ble_result(tag, result, TagStatus.ONLINE if result.get("ok") else None)
        db.commit()
        return {"ok": bool(result.get("ok")), "result": result, "item": _tag_detail(tag)}
    finally:
        db.close()
