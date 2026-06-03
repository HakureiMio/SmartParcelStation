from __future__ import annotations

import uuid
import time
import shutil
import json
from pathlib import Path
from datetime import datetime
from sqlalchemy import select
import typer
from loguru import logger

from gateway.core.config import get_settings
from gateway.core.logging import setup_logging
from gateway.console import setup_utf8_console
from gateway.db.init_db import init_db
from gateway.db.session import SessionLocal
from gateway.models.entities import BindingStatus, CredentialStatus, CredentialType, LocalNfcCredential, LocalParcel, LocalParcelTagBinding, LocalTag, ParcelStatus, PickupEventType, TagStatus
from gateway.mqtt.client import GatewayMqttClient
from gateway.mqtt.handlers import handle_server_command
from gateway.services.access_control_service import AccessControlService
from gateway.services.heartbeat_service import HeartbeatService
from gateway.services.mock_ble_service import MockBleService
from gateway.services.mock_nfc_service import MockNfcService
from gateway.services.server_client import ServerClient
from gateway.services.sync_service import SyncService
from gateway.services.task_service import TaskService


app = typer.Typer(help="SmartParcel Local Gateway CLI")


def _prepare_console() -> None:
    setup_utf8_console()


def _upsert_env_values(env_path: Path, values: dict[str, str]) -> None:
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


@app.command("init-db")
def cli_init_db():
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    init_db()
    typer.echo("database initialized")


@app.command("health")
def cli_health():
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    client = ServerClient(settings)
    typer.echo(client.health())


@app.command("bootstrap-activate")
def cli_bootstrap_activate(
    gateway_code: str = typer.Option("GW001", help="Gateway code to activate"),
    station_id: int = typer.Option(1, help="Station ID bound to the registration token"),
    registration_token: str = typer.Option(..., prompt=True, help="Short-lived registration token from server"),
    server_base_url: str = typer.Option("http://127.0.0.1:18000", help="Server base URL without /api/v1"),
    env_path: Path = typer.Option(Path(".env"), help="Local .env path to update"),
    write_env: bool = typer.Option(True, help="Write activated configuration to .env and create .env.bak first"),
):
    _prepare_console()
    setup_logging("INFO")
    result = ServerClient.bootstrap_activate(
        server_base_url,
        {
            "gateway_code": gateway_code,
            "station_id": station_id,
            "registration_token": registration_token,
            "device_info": {"source": "gateway-cli", "version": "0.1.0"},
        },
    )
    values = {
        "GATEWAY_CODE": result["gateway_code"],
        "GATEWAY_SECRET": result["gateway_secret"],
        "STATION_ID": str(result["station_id"]),
        "SERVER_BASE_URL": server_base_url.rstrip("/"),
    }
    if write_env:
        _upsert_env_values(env_path, values)
        typer.echo("网关注册成功。")
        typer.echo(f"配置已写入 {env_path}，原文件已备份为 {env_path}.bak。")
        typer.echo("GATEWAY_CODE=" + values["GATEWAY_CODE"])
        typer.echo("GATEWAY_SECRET=********")
        typer.echo("STATION_ID=" + values["STATION_ID"])
        typer.echo("SERVER_BASE_URL=" + values["SERVER_BASE_URL"])
        typer.echo("长期密钥已保存，请不要提交 .env 到 Git。")
    else:
        typer.echo("网关注册成功。请手动保存以下配置，长期密钥只显示这一次：")
        typer.echo("GATEWAY_CODE=" + values["GATEWAY_CODE"])
        typer.echo("GATEWAY_SECRET=" + values["GATEWAY_SECRET"])
        typer.echo("STATION_ID=" + values["STATION_ID"])
        typer.echo("SERVER_BASE_URL=" + values["SERVER_BASE_URL"])


@app.command("heartbeat")
def cli_heartbeat():
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    client = ServerClient(settings)
    typer.echo(HeartbeatService(client).send_once())


@app.command("sync-pull")
def cli_sync_pull():
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
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    db = SessionLocal()
    try:
        count = SyncService(db, ServerClient(settings), settings.station_id).sync_push_once()
        typer.echo(f"sync push sent: {count}")
    finally:
        db.close()


@app.command("inbound-parcel")
def cli_inbound_parcel(
    parcel_code: str = typer.Option(..., prompt=True),
    receiver_phone: str = typer.Option(..., prompt=True),
    pickup_code: str | None = typer.Option(None),
    receiver_user_id: str | None = typer.Option(None),
    receiver_name_masked: str | None = typer.Option(None),
    shelf_code: str | None = typer.Option(None),
):
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
    encrypted_token: str = typer.Option("", help="Mock tag token"),
    auto_register: bool = typer.Option(False, help="Development only: create the local tag if it was not registered first"),
    upload_audit: bool = typer.Option(False, help="Compatibility only: upload TAG_BOUND as a business audit event"),
):
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
            if not auto_register:
                raise typer.BadParameter(f"tag not registered locally: {tag_id}. Run register-tag first or pass --auto-register for development.")
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
        typer.echo(f"nfc credential registered locally: {credential_type_value.value} {credential_value} -> user {user_id}")
    finally:
        db.close()


@app.command("release-tag")
def cli_release_tag(
    tag_id: str = typer.Option(..., prompt=True),
    parcel_code: str | None = typer.Option(None),
    release_reason: str = typer.Option("MANUAL_RELEASE"),
):
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


@app.command("mock-nfc")
def cli_mock_nfc(card_uid: str):
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    db = SessionLocal()
    try:
        service = MockNfcService(
            db,
            SyncService(db, ServerClient(settings), settings.station_id),
            TaskService(db),
            MockBleService(),
        )
        typer.echo(service.handle_card(card_uid))
    finally:
        db.close()


@app.command("gate-access")
def cli_gate_access(
    reader_id: str = typer.Option("GATE01"),
    card_uid: str | None = typer.Option(None, help="Shortcut for --credential-type CARD_UID --credential-value"),
    credential_type: str = typer.Option("CARD_UID"),
    credential_value: str | None = typer.Option(None),
):
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    value = credential_value or card_uid
    if not value:
        raise typer.BadParameter("pass --card-uid or --credential-value")
    db = SessionLocal()
    try:
        service = AccessControlService(
            db,
            SyncService(db, ServerClient(settings), settings.station_id),
            TaskService(db),
            MockBleService(),
            settings.station_id,
        )
        result = service.handle_access_card(reader_id=reader_id, credential_type=credential_type, credential_value=value)
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        db.close()


@app.command("local-api")
def cli_local_api(
    host: str = typer.Option("0.0.0.0"),
    port: int = typer.Option(19000),
):
    _prepare_console()
    import uvicorn

    uvicorn.run("gateway.local_api:app", host=host, port=port, reload=False)


@app.command("list-parcels")
def cli_list_parcels(limit: int = 50):
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
    _prepare_console()
    db = SessionLocal()
    try:
        for t in TaskService(db).list_tasks(limit=limit):
            typer.echo(f"{t.task_id} {t.task_type} {t.status} retries={t.retry_count}")
    finally:
        db.close()


@app.command("run")
def cli_run():
    _prepare_console()
    settings = get_settings()
    setup_logging(settings.log_level)
    init_db()

    client = ServerClient(settings)
    try:
        logger.info("health: {}", client.health())
    except Exception as ex:
        logger.warning("server health check failed: {}", ex)

    db = SessionLocal()
    ble = MockBleService()

    def on_command(payload: dict):
        result = handle_server_command(db, payload, ble)
        mqtt_client.publish_event({"type": "server_command_result", "result": result})

    mqtt_client = GatewayMqttClient(
        host=settings.mqtt_host,
        port=settings.mqtt_port,
        username=settings.mqtt_username,
        password=settings.mqtt_password,
        gateway_code=settings.gateway_code,
        command_handler=on_command,
    )

    mqtt_client.start()
    hb_service = HeartbeatService(client)
    sync_service = SyncService(db, client, settings.station_id)

    last_hb = 0.0
    last_pull = 0.0
    last_push = 0.0

    try:
        while True:
            now = time.time()
            if now - last_hb >= settings.heartbeat_interval_seconds:
                try:
                    hb_service.send_once()
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
        mqtt_client.stop()
        db.close()


if __name__ == "__main__":
    app()
