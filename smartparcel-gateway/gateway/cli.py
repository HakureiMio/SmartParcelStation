"""
SmartParcel Gateway CLI.

Commands:
- init-db, health, bootstrap-activate, heartbeat, sync-pull, sync-push
- inbound-parcel, bind-tag, register-tag, register-nfc-credential
- release-tag, report-tag-exception, confirm-pickup
- gate-access, local-api
- run, provisioning, hotspot-start, hotspot-stop, status
- list-parcels, list-tags, list-tasks
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path

import typer
from loguru import logger
from sqlalchemy import select

from gateway.core.config import Settings, get_settings, reload_settings
from gateway.core.logging import setup_logging
from gateway.console import setup_utf8_console
from gateway.db.init_db import init_db
from gateway.db.session import SessionLocal
from gateway.models.entities import (
    BindingStatus,
    CredentialStatus,
    CredentialType,
    GatewayBindingStatus,
    GatewayConfig,
    LocalNfcCredential,
    LocalParcel,
    LocalParcelTagBinding,
    LocalTag,
    ParcelStatus,
    PickupEventType,
    TagStatus,
)
from gateway.mqtt.client import GatewayMqttClient
from gateway.mqtt.handlers import handle_server_command
from gateway.services.access_control_service import AccessControlService
from gateway.services.ble.adapter import RealBleCommandService
from gateway.services.heartbeat_service import HeartbeatService
from gateway.services.server_client import ServerClient
from gateway.services.sync_service import SyncService
from gateway.services.task_service import TaskService

app = typer.Typer(help="SmartParcel Local Gateway CLI")


def _prepare_console() -> None:
    setup_utf8_console()


def _upsert_env_values(env_path: Path, values: dict[str, str]) -> None:
    """Write key=value pairs into .env, creating a .env.bak backup first."""
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


def _sync_config_to_db(settings: Settings) -> None:
    """Mirror current settings into the gateway_config table."""
    db = SessionLocal()
    try:
        cfg = db.query(GatewayConfig).first()  # type: ignore[attr-defined]
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
        logger.warning("Failed to sync config to DB: {}", exc)
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


@app.command("init-db")
def cli_init_db():
    """Initialize the local SQLite database."""
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    init_db()
    typer.echo("database initialized")


# ---------------------------------------------------------------------------
# Server communication
# ---------------------------------------------------------------------------


@app.command("health")
def cli_health():
    """Check server health."""
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    client = ServerClient(settings)
    typer.echo(client.health())


@app.command("bootstrap-activate")
def cli_bootstrap_activate(
    gateway_code: str = typer.Option(..., help="Gateway code to activate"),
    station_id: int = typer.Option(..., help="Station ID"),
    registration_token: str = typer.Option(..., prompt=True, help="Short-lived registration token from server"),
    server_base_url: str = typer.Option(..., help="Server base URL without /api/v1"),
    env_path: Path = typer.Option(Path(".env"), help="Local .env path to update"),
    write_env: bool = typer.Option(True, help="Write activated configuration to .env"),
):
    """Admin-only: directly activate gateway registration with server and write config."""
    _prepare_console()
    setup_logging("INFO")
    result = ServerClient.bootstrap_activate(
        server_base_url,
        {
            "gateway_code": gateway_code,
            "station_id": station_id,
            "registration_token": registration_token,
            "device_info": {"source": "gateway-cli", "version": "0.2.0"},
        },
    )
    values = {
        "GATEWAY_CODE": result["gateway_code"],
        "GATEWAY_SECRET": result["gateway_secret"],
        "STATION_ID": str(result["station_id"]),
        "SERVER_BASE_URL": server_base_url.rstrip("/"),
        "BINDING_STATUS": "BOUND",
    }
    if write_env:
        _upsert_env_values(env_path, values)
        typer.echo("Gateway registered successfully.")
        typer.echo(f"Config written to {env_path}, original backed up as {env_path}.bak.")
        typer.echo("GATEWAY_CODE=" + values["GATEWAY_CODE"])
        typer.echo("GATEWAY_SECRET=********")
        typer.echo("STATION_ID=" + values["STATION_ID"])
        typer.echo("SERVER_BASE_URL=" + values["SERVER_BASE_URL"])
        typer.echo("DO NOT commit .env to Git.")
    else:
        typer.echo("Gateway registered. Save these values (secret shown only once):")
        typer.echo("GATEWAY_CODE=" + values["GATEWAY_CODE"])
        typer.echo("GATEWAY_SECRET=" + values["GATEWAY_SECRET"])
        typer.echo("STATION_ID=" + values["STATION_ID"])
        typer.echo("SERVER_BASE_URL=" + values["SERVER_BASE_URL"])


@app.command("heartbeat")
def cli_heartbeat():
    """Send a single heartbeat to the server."""
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    client = ServerClient(settings)
    typer.echo(HeartbeatService(client).send_once())


@app.command("sync-pull")
def cli_sync_pull():
    """Pull sync data from server."""
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    db = SessionLocal()
    try:
        data = SyncService(db, ServerClient(settings), settings.station_id).sync_pull_once()
        typer.echo(f"sync pull done: keys={list(data.keys())}")
    finally:
        db.close()


@app.command("sync-push")
def cli_sync_push():
    """Push sync data to server."""
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    db = SessionLocal()
    try:
        count = SyncService(db, ServerClient(settings), settings.station_id).sync_push_once()
        typer.echo(f"sync push sent: {count}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Local data management
# ---------------------------------------------------------------------------


@app.command("inbound-parcel")
def cli_inbound_parcel(
    parcel_code: str = typer.Option(..., prompt=True),
    receiver_phone: str = typer.Option(..., prompt=True),
    pickup_code: str | None = typer.Option(None),
    receiver_user_id: str | None = typer.Option(None),
    receiver_name_masked: str | None = typer.Option(None),
    shelf_code: str | None = typer.Option(None),
):
    """Manually queue an inbound parcel locally."""
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    db = SessionLocal()
    try:
        parcel = db.scalar(select(LocalParcel).where(LocalParcel.parcel_code == parcel_code))
        if parcel is None:
            parcel = LocalParcel(
                server_parcel_id=parcel_code,
                parcel_code=parcel_code,
                pickup_code=pickup_code,
                receiver_user_id=receiver_user_id,
                receiver_phone=receiver_phone,
                receiver_name_masked=receiver_name_masked,
                shelf_code=shelf_code,
                station_id=settings.station_id,
                status=ParcelStatus.WAITING_PICKUP,
                origin="GATEWAY_INBOUND",
                sync_status="SYNC_PENDING",
            )
            db.add(parcel)
        else:
            parcel.pickup_code = pickup_code or parcel.pickup_code
            parcel.receiver_user_id = receiver_user_id or parcel.receiver_user_id
            parcel.receiver_phone = receiver_phone
            parcel.receiver_name_masked = receiver_name_masked or parcel.receiver_name_masked
            parcel.shelf_code = shelf_code or parcel.shelf_code
            parcel.status = ParcelStatus.WAITING_PICKUP
            parcel.origin = "GATEWAY_INBOUND"
            parcel.sync_status = "SYNC_PENDING"
        db.commit()
        SyncService(db, ServerClient(settings), settings.station_id).enqueue_event_upload(
            {
                "event_id": uuid.uuid4().hex,
                "event_type": "GATEWAY_INBOUND",
                "payload_json": {
                    "parcel_code": parcel_code,
                    "receiver_phone": receiver_phone,
                    "pickup_code": pickup_code,
                    "receiver_user_id": receiver_user_id,
                    "receiver_name_masked": receiver_name_masked,
                    "shelf_code": shelf_code,
                    "station_id": settings.station_id,
                },
            }
        )
        typer.echo(f"inbound parcel queued: {parcel_code}")
    finally:
        db.close()


@app.command("bind-tag")
def cli_bind_tag(
    parcel_code: str = typer.Option(..., prompt=True),
    tag_id: str = typer.Option(..., prompt=True),
    encrypted_token: str = typer.Option("", help="Optional local binding token"),
    allow_unsafe_dev_autoregister: bool = typer.Option(
        False, "--allow-unsafe-dev-autoregister",
        help="UNSAFE: auto-create tag if not registered (DEVELOPMENT ONLY)",
    ),
    upload_audit: bool = typer.Option(False, help="Upload TAG_BOUND as business audit event"),
):
    """Bind a tag to a parcel locally."""
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    db = SessionLocal()
    try:
        parcel = db.scalar(select(LocalParcel).where(LocalParcel.parcel_code == parcel_code))
        if parcel is None:
            raise typer.BadParameter(f"parcel not found: {parcel_code}")
        tag = db.scalar(select(LocalTag).where(LocalTag.tag_id == tag_id))
        if tag is None:
            if not allow_unsafe_dev_autoregister:
                raise typer.BadParameter(
                    f"tag not registered locally: {tag_id}. "
                    "Run register-tag first or pass --allow-unsafe-dev-autoregister for development."
                )
            if not settings.allow_unsafe_dev_autoregister:
                raise typer.BadParameter(
                    "Unsafe dev autoregister is disabled in config. "
                    "Set ALLOW_UNSAFE_DEV_AUTOREGISTER=true in .env to enable."
                )
            tag = LocalTag(
                tag_id=tag_id,
                encrypted_token=encrypted_token,
                station_id=settings.station_id,
                status=TagStatus.IDLE,
                hw_model="E73-2G4M04S1A",
                registered_at=datetime.utcnow(),
            )
            db.add(tag)
            db.commit()
        elif encrypted_token:
            tag.encrypted_token = encrypted_token

        active_binding = db.scalar(select(LocalParcelTagBinding).where(
            LocalParcelTagBinding.server_parcel_id == parcel.server_parcel_id,
            LocalParcelTagBinding.tag_id == tag_id,
            LocalParcelTagBinding.status == BindingStatus.ACTIVE,
        ))
        if active_binding:
            db.commit()
            typer.echo(f"tag already bound locally: {parcel_code} -> {tag_id}")
            return

        binding_id = uuid.uuid4().hex
        binding = LocalParcelTagBinding(
            pickup_binding_id=binding_id,
            server_parcel_id=parcel.server_parcel_id,
            tag_id=tag_id,
            station_id=settings.station_id,
            status=BindingStatus.ACTIVE,
        )
        db.add(binding)
        tag.status = TagStatus.RUNNING
        db.commit()
        if upload_audit:
            SyncService(db, ServerClient(settings), settings.station_id).enqueue_event_upload(
                {
                    "event_id": uuid.uuid4().hex,
                    "event_type": "TAG_BOUND",
                    "payload_json": {
                        "parcel_code": parcel_code,
                        "tag_id": tag_id,
                        "pickup_binding_id": binding_id,
                        "station_id": settings.station_id,
                        "audit_only": True,
                    },
                }
            )
        typer.echo(f"tag bound locally: {parcel_code} -> {tag_id}")
    finally:
        db.close()


@app.command("register-tag")
def cli_register_tag(
    tag_id: str = typer.Option(..., prompt=True),
    tag_uid: str | None = typer.Option(None),
    hw_model: str = typer.Option("E73-2G4M04S1A"),
    fw_version: str | None = typer.Option(None),
    encrypted_token: str | None = typer.Option(None, "--encrypted-token", "--tag-token", help="Optional local binding token"),
):
    """Register a tag locally."""
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    db = SessionLocal()
    try:
        tag = db.scalar(select(LocalTag).where(LocalTag.tag_id == tag_id))
        if tag is None:
            tag = LocalTag(
                tag_id=tag_id,
                tag_uid=tag_uid,
                encrypted_token=encrypted_token or "",
                station_id=settings.station_id,
                status=TagStatus.IDLE,
                hw_model=hw_model,
                fw_version=fw_version,
                registered_at=datetime.utcnow(),
            )
            db.add(tag)
        else:
            tag.tag_uid = tag_uid or tag.tag_uid
            tag.hw_model = hw_model or tag.hw_model
            tag.fw_version = fw_version or tag.fw_version
            if encrypted_token is not None:
                tag.encrypted_token = encrypted_token
            tag.registered_at = tag.registered_at or datetime.utcnow()
        db.commit()
        typer.echo(f"tag registered locally: {tag_id}")
    finally:
        db.close()


@app.command("register-nfc-credential")
def cli_register_nfc_credential(
    credential_value: str = typer.Option(..., "--credential-value", "--card-uid", prompt=True),
    user_id: str = typer.Option(...),
    credential_type: str = typer.Option("CARD_UID"),
):
    """Register an NFC credential locally."""
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    try:
        credential_type_value = CredentialType(credential_type.upper())
    except ValueError as exc:
        raise typer.BadParameter(f"unsupported credential_type: {credential_type}") from exc
    db = SessionLocal()
    try:
        credential = db.scalar(select(LocalNfcCredential).where(
            LocalNfcCredential.credential_type == credential_type_value,
            LocalNfcCredential.credential_value == credential_value,
            LocalNfcCredential.station_id == settings.station_id,
        ))
        if credential is None:
            credential = LocalNfcCredential(
                credential_type=credential_type_value,
                credential_value=credential_value,
                user_id=user_id,
                station_id=settings.station_id,
                status=CredentialStatus.ACTIVE,
            )
            db.add(credential)
        else:
            credential.user_id = user_id
            credential.status = CredentialStatus.ACTIVE
        db.commit()
        typer.echo(f"nfc credential registered: {credential_type_value.value} -> user {user_id}")
    finally:
        db.close()


@app.command("release-tag")
def cli_release_tag(
    tag_id: str = typer.Option(..., prompt=True),
    parcel_code: str | None = typer.Option(None),
    release_reason: str = typer.Option("MANUAL_RELEASE"),
):
    """Release a tag from its binding(s)."""
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    db = SessionLocal()
    try:
        tag = db.scalar(select(LocalTag).where(LocalTag.tag_id == tag_id))
        if tag is None:
            raise typer.BadParameter(f"tag not registered locally: {tag_id}")

        query = select(LocalParcelTagBinding).where(
            LocalParcelTagBinding.tag_id == tag_id,
            LocalParcelTagBinding.status == BindingStatus.ACTIVE,
        )
        if parcel_code:
            parcel = db.scalar(select(LocalParcel).where(LocalParcel.parcel_code == parcel_code))
            if parcel is None:
                raise typer.BadParameter(f"parcel not found: {parcel_code}")
            query = query.where(LocalParcelTagBinding.server_parcel_id == parcel.server_parcel_id)

        bindings = list(db.scalars(query))
        now = datetime.utcnow()
        for binding in bindings:
            binding.status = BindingStatus.RELEASED
            binding.released_at = now
            binding.release_reason = release_reason
        tag.status = TagStatus.IDLE
        db.commit()
        typer.echo(f"tag released locally: {tag_id}, bindings={len(bindings)}")
    finally:
        db.close()


@app.command("report-tag-exception")
def cli_report_tag_exception(
    tag_id: str = typer.Option(..., prompt=True),
    exception_type: str = typer.Option(...),
    severity: str = typer.Option("WARNING"),
    message: str = typer.Option(...),
):
    """Report a tag exception/error."""
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    db = SessionLocal()
    try:
        tag = db.scalar(select(LocalTag).where(LocalTag.tag_id == tag_id))
        if tag is None:
            raise typer.BadParameter(f"tag not registered locally: {tag_id}")

        now = datetime.utcnow()
        tag.last_error_type = exception_type
        tag.last_error_message = message
        tag.last_error_at = now
        if exception_type.upper() == "LOW_BATTERY":
            tag.status = TagStatus.LOW_BATTERY
        elif severity.upper() in {"ERROR", "CRITICAL"}:
            tag.status = TagStatus.ERROR

        payload = {
            "event_type": "TAG_EXCEPTION_REPORTED",
            "gateway_code": settings.gateway_code,
            "station_id": settings.station_id,
            "tag_ref": tag_id,
            "exception_type": exception_type,
            "severity": severity,
            "message": message,
            "occurred_at": now.isoformat() + "Z",
        }
        SyncService(db, ServerClient(settings), settings.station_id).enqueue_event_upload(
            {
                "event_id": uuid.uuid4().hex,
                "event_type": "TAG_EXCEPTION_REPORTED",
                "payload_json": payload,
            }
        )
        db.commit()
        typer.echo(f"tag exception queued: {tag_id} {exception_type} {severity}")
    finally:
        db.close()


@app.command("confirm-pickup")
def cli_confirm_pickup(
    parcel_code: str = typer.Option(..., prompt=True),
    receiver_phone: str | None = typer.Option(None),
    pickup_code: str | None = typer.Option(None),
    pickup_method: str = typer.Option("OFFLINE_MANUAL"),
):
    """Confirm a pickup locally."""
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    db = SessionLocal()
    try:
        parcel = db.scalar(select(LocalParcel).where(LocalParcel.parcel_code == parcel_code))
        if parcel is None:
            raise typer.BadParameter(f"parcel not found: {parcel_code}")
        if receiver_phone and parcel.receiver_phone and receiver_phone != parcel.receiver_phone:
            raise typer.BadParameter("receiver_phone does not match local parcel")
        if pickup_code and parcel.pickup_code and pickup_code != parcel.pickup_code:
            raise typer.BadParameter("pickup_code does not match local parcel")
        parcel.status = ParcelStatus.PICKED_UP
        parcel.sync_status = "SYNC_PENDING"
        method = pickup_method.upper()
        now = datetime.utcnow()
        bindings = list(db.scalars(select(LocalParcelTagBinding).where(
            LocalParcelTagBinding.server_parcel_id == parcel.server_parcel_id,
            LocalParcelTagBinding.status == BindingStatus.ACTIVE,
        )))
        for binding in bindings:
            binding.status = BindingStatus.RELEASED
            binding.released_at = now
            binding.release_reason = f"PICKUP_{method}"
            tag = db.scalar(select(LocalTag).where(LocalTag.tag_id == binding.tag_id))
            if tag:
                tag.status = TagStatus.IDLE
        service = SyncService(db, ServerClient(settings), settings.station_id)
        event = service.create_pickup_event(
            PickupEventType.OFFLINE_PICKUP,
            {
                "parcel_code": parcel_code,
                "server_parcel_id": parcel.server_parcel_id,
                "receiver_phone_confirmed": bool(receiver_phone),
                "pickup_code_confirmed": bool(pickup_code),
                "pickup_method": method,
            },
            server_parcel_id=parcel.server_parcel_id,
            user_id=parcel.receiver_user_id,
        )
        db.commit()
        typer.echo(f"pickup confirmed and queued: {event.event_id}")
    finally:
        db.close()


@app.command("gate-access")
def cli_gate_access(
    reader_id: str = typer.Option("GATE01"),
    card_uid: str | None = typer.Option(None, help="Shortcut for --credential-type CARD_UID --credential-value"),
    credential_type: str = typer.Option("CARD_UID"),
    credential_value: str | None = typer.Option(None),
):
    """Simulate a gate access attempt using real BLE backend."""
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    value = credential_value or card_uid
    if not value:
        raise typer.BadParameter("pass --card-uid or --credential-value")
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
        )
        result = service.handle_access_card(
            reader_id=reader_id,
            credential_type=credential_type,
            credential_value=value,
        )
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Server commands
# ---------------------------------------------------------------------------


@app.command("local-api")
def cli_local_api(
    host: str = typer.Option("0.0.0.0"),
    port: int = typer.Option(19000),
):
    """Start the local FastAPI server."""
    _prepare_console()
    import uvicorn
    uvicorn.run("gateway.local_api:app", host=host, port=port, reload=False)


# ---------------------------------------------------------------------------
# Listing commands
# ---------------------------------------------------------------------------


@app.command("list-parcels")
def cli_list_parcels(limit: int = 50):
    """List local parcels."""
    _prepare_console()
    db = SessionLocal()
    try:
        rows = list(db.scalars(select(LocalParcel).order_by(LocalParcel.created_at.desc()).limit(limit)))
        for r in rows:
            typer.echo(f"{r.server_parcel_id} {r.parcel_code} {r.status} shelf={r.shelf_code}")
    finally:
        db.close()


@app.command("list-tags")
def cli_list_tags(limit: int = 50):
    """List local tags."""
    _prepare_console()
    db = SessionLocal()
    try:
        rows = list(db.scalars(select(LocalTag).order_by(LocalTag.created_at.desc()).limit(limit)))
        for r in rows:
            typer.echo(f"{r.tag_id} {r.status} battery={r.battery_level}")
    finally:
        db.close()


@app.command("list-tasks")
def cli_list_tasks(limit: int = 50):
    """List local tasks."""
    _prepare_console()
    db = SessionLocal()
    try:
        for t in TaskService(db).list_tasks(limit=limit):
            typer.echo(f"{t.task_id} {t.task_type} {t.status} retries={t.retry_count}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Deployment / lifecycle commands
# ---------------------------------------------------------------------------


@app.command("hotspot-start")
def cli_hotspot_start():
    """Start the Wi-Fi provisioning hotspot."""
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    from gateway.network import get_hotspot_manager
    hotspot = get_hotspot_manager()
    status = hotspot.ensure_ap_started()
    if status.active:
        typer.echo(f"Hotspot active: SSID={status.ssid}, IP={status.ip_address}")
    else:
        typer.echo(f"Hotspot failed: {status.error}", err=True)
        raise typer.Exit(code=1)


@app.command("hotspot-stop")
def cli_hotspot_stop():
    """Stop the Wi-Fi provisioning hotspot."""
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    from gateway.network import get_hotspot_manager
    hotspot = get_hotspot_manager()
    status = hotspot.stop_ap()
    typer.echo(f"Hotspot stopped: SSID={status.ssid}")


@app.command("provisioning")
def cli_provisioning():
    """Start provisioning mode: hotspot + provisioning API only.

    Use this when the gateway is UNBOUND and waiting for staff to
    connect via hotspot and complete binding.
    """
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    init_db()
    _sync_config_to_db(settings)

    if settings.is_bound:
        typer.echo("Gateway is already BOUND. Use 'run' instead of 'provisioning'.", err=True)
        raise typer.Exit(code=1)

    # Start hotspot
    if settings.wifi_ap_enabled:
        from gateway.network import get_hotspot_manager
        hotspot = get_hotspot_manager()
        ap_status = hotspot.ensure_ap_started()
        if ap_status.active:
            typer.echo(f"Hotspot active: SSID={ap_status.ssid}, IP={ap_status.ip_address}")
        else:
            typer.echo(f"WARNING: Hotspot failed to start: {ap_status.error}", err=True)
    else:
        typer.echo("WIFI_AP_ENABLED=false, skipping hotspot")

    # Start provisioning API
    import uvicorn
    typer.echo(f"Starting provisioning API on {settings.provisioning_host}:{settings.provisioning_port}")
    typer.echo("Waiting for binding via POST /local/provisioning/bind ...")
    uvicorn.run(
        "gateway.provisioning_api:provisioning_app",
        host=settings.provisioning_host,
        port=settings.provisioning_port,
        reload=False,
    )


@app.command("status")
def cli_status():
    """Show current gateway status (no secrets)."""
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)

    ssid = None
    if settings.wifi_ap_enabled:
        suffix = (settings.gateway_serial or settings.gateway_device_id or "0000")[-4:]
        ssid = f"{settings.wifi_ap_ssid_prefix}-{suffix}"

    db = SessionLocal()
    try:
        cfg = db.query(GatewayConfig).first()  # type: ignore[attr-defined]
        last_hb_status = cfg.last_heartbeat_status if cfg else None
        last_hb_at = cfg.last_heartbeat_at.isoformat() if (cfg and cfg.last_heartbeat_at) else None
    finally:
        db.close()

    typer.echo("=== Gateway Status ===")
    typer.echo(f"binding_status:       {settings.binding_status.upper()}")
    typer.echo(f"gateway_code:         {settings.gateway_code or '(not set)'}")
    typer.echo(f"gateway_device_id:    {settings.gateway_device_id or '(not set)'}")
    typer.echo(f"gateway_serial:       {settings.gateway_serial or '(not set)'}")
    typer.echo(f"station_id:           {settings.station_id or '(not set)'}")
    typer.echo(f"server_base_url:      {settings.server_base_url or '(not set)'}")
    typer.echo(f"last_heartbeat:       {last_hb_status or 'N/A'}")
    typer.echo(f"last_heartbeat_at:    {last_hb_at or 'N/A'}")
    typer.echo(f"local_api:            {settings.local_api_host}:{settings.local_api_port}")
    typer.echo(f"ap_ssid:              {ssid or '(not configured)'}")
    typer.echo(f"hotspot_enabled:      {settings.wifi_ap_enabled}")
    typer.echo(f"provisioning_enabled: {settings.provisioning_enabled}")
    typer.echo(f"ble_backend:          {settings.ble_backend}")
    typer.echo(f"config_version:       {settings.config_version}")


@app.command("run")
def cli_run():
    """Unified gateway startup.

    - If UNBOUND: start hotspot + provisioning API, wait for binding.
    - If BOUND: verify secret, heartbeat, start local API + runtime loops.
    """
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    init_db()
    _sync_config_to_db(settings)

    if settings.is_unbound:
        typer.echo("Gateway is UNBOUND — entering provisioning mode.")
        typer.echo("Start hotspot and provisioning API...")

        if settings.wifi_ap_enabled:
            from gateway.network import get_hotspot_manager
            hotspot = get_hotspot_manager()
            ap_status = hotspot.ensure_ap_started()
            if ap_status.active:
                typer.echo(f"Hotspot active: SSID={ap_status.ssid}, IP={ap_status.ip_address}")
            else:
                typer.echo(f"WARNING: Hotspot failed: {ap_status.error}", err=True)

        import uvicorn
        typer.echo(f"Provisioning API on {settings.provisioning_host}:{settings.provisioning_port}")
        uvicorn.run(
            "gateway.provisioning_api:provisioning_app",
            host=settings.provisioning_host,
            port=settings.provisioning_port,
            reload=False,
        )
        return

    # --- BOUND mode ---
    typer.echo(f"Gateway BOUND: {settings.gateway_code} @ {settings.server_base_url}")

    # Verify server connection
    client = ServerClient(settings)
    try:
        health = client.health()
        logger.info("Server health: {}", health)
    except Exception as ex:
        logger.warning("Server health check failed: {}", ex)

    # Send heartbeat
    hb_service = HeartbeatService(client)
    try:
        hb_result = hb_service.send_once()
        logger.info("Initial heartbeat: {}", hb_result)
        # Update DB
        db2 = SessionLocal()
        try:
            cfg = db2.query(GatewayConfig).first()  # type: ignore[attr-defined]
            if cfg:
                cfg.last_heartbeat_at = datetime.utcnow()
                cfg.last_heartbeat_status = "ONLINE"
                try:
                    cfg.binding_status = GatewayBindingStatus.ONLINE
                except ValueError:
                    pass
                db2.commit()
        finally:
            db2.close()
    except Exception as ex:
        logger.warning("Initial heartbeat failed: {}", ex)

    # Start local API in background thread
    import threading
    import uvicorn as _uvicorn

    def _run_local_api():
        _uvicorn.run(
            "gateway.local_api:app",
            host=settings.local_api_host,
            port=settings.local_api_port,
            reload=False,
            log_level="info",
        )

    api_thread = threading.Thread(target=_run_local_api, daemon=True)
    api_thread.start()
    typer.echo(f"Local API at http://{settings.local_api_host}:{settings.local_api_port}")

    # Start runtime loops
    db = SessionLocal()
    sync_service = SyncService(db, client, settings.station_id)

    # MQTT (optional)
    mqtt_client = None
    if settings.mqtt_host:
        def _on_mqtt_command(payload: dict):
            ble_svc = RealBleCommandService()
            result = handle_server_command(db, payload, ble_svc)
            if mqtt_client:
                mqtt_client.publish_event({"type": "server_command_result", "result": result})

        mqtt_client = GatewayMqttClient(
            host=settings.mqtt_host,
            port=settings.mqtt_port,
            username=settings.mqtt_username,
            password=settings.mqtt_password,
            gateway_code=settings.gateway_code,
            command_handler=_on_mqtt_command,
        )
        mqtt_client.start()
        typer.echo(f"MQTT connected to {settings.mqtt_host}:{settings.mqtt_port}")

    last_hb = 0.0
    last_pull = 0.0
    last_push = 0.0

    typer.echo("Gateway runtime started. Press Ctrl+C to stop.")
    try:
        while True:
            now = time.time()
            if now - last_hb >= settings.heartbeat_interval_seconds:
                try:
                    hb_service.send_once()
                    if mqtt_client:
                        mqtt_client.publish_status({"status": "ONLINE", "ts": int(now)})
                except Exception as ex:
                    logger.warning("heartbeat failed: {}", ex)
                last_hb = now

            if now - last_pull >= settings.sync_pull_interval_seconds:
                try:
                    sync_service.sync_pull_once()
                except Exception as ex:
                    logger.warning("sync pull failed: {}", ex)
                last_pull = now

            if now - last_push >= settings.sync_push_interval_seconds:
                try:
                    sync_service.sync_push_once()
                except Exception as ex:
                    logger.warning("sync push failed: {}", ex)
                last_push = now

            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("gateway stopped")
    finally:
        if mqtt_client:
            mqtt_client.stop()
        db.close()


if __name__ == "__main__":
    app()
