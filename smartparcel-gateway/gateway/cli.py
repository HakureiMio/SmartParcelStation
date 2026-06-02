from __future__ import annotations

import uuid
import time
from sqlalchemy import select
import typer
from loguru import logger

from gateway.core.config import get_settings
from gateway.core.logging import setup_logging
from gateway.db.init_db import init_db
from gateway.db.session import SessionLocal
from gateway.models.entities import BindingStatus, LocalParcel, LocalParcelTagBinding, LocalTag, ParcelStatus, PickupEventType
from gateway.mqtt.client import GatewayMqttClient
from gateway.mqtt.handlers import handle_server_command
from gateway.services.heartbeat_service import HeartbeatService
from gateway.services.mock_ble_service import MockBleService
from gateway.services.mock_nfc_service import MockNfcService
from gateway.services.server_client import ServerClient
from gateway.services.sync_service import SyncService
from gateway.services.task_service import TaskService


app = typer.Typer(help="SmartParcel Local Gateway CLI")


@app.command("init-db")
def cli_init_db():
    settings = get_settings()
    setup_logging(settings.log_level)
    init_db()
    typer.echo("database initialized")


@app.command("health")
def cli_health():
    settings = get_settings()
    setup_logging(settings.log_level)
    client = ServerClient(settings)
    typer.echo(client.health())


@app.command("heartbeat")
def cli_heartbeat():
    settings = get_settings()
    setup_logging(settings.log_level)
    client = ServerClient(settings)
    typer.echo(HeartbeatService(client).send_once())


@app.command("sync-pull")
def cli_sync_pull():
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
):
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
):
    settings = get_settings()
    setup_logging(settings.log_level)
    db = SessionLocal()
    try:
        parcel = db.scalar(select(LocalParcel).where(LocalParcel.parcel_code == parcel_code))
        if parcel is None:
            raise typer.BadParameter(f"parcel not found: {parcel_code}")
        tag = db.scalar(select(LocalTag).where(LocalTag.tag_id == tag_id))
        if tag is None:
            tag = LocalTag(tag_id=tag_id, encrypted_token=encrypted_token, station_id=settings.station_id)
            db.add(tag)
            db.commit()
        binding_id = uuid.uuid4().hex
        binding = LocalParcelTagBinding(
            pickup_binding_id=binding_id,
            server_parcel_id=parcel.server_parcel_id,
            tag_id=tag_id,
            station_id=settings.station_id,
            status=BindingStatus.ACTIVE,
        )
        db.add(binding)
        db.commit()
        SyncService(db, ServerClient(settings), settings.station_id).enqueue_event_upload(
            {
                "event_id": uuid.uuid4().hex,
                "event_type": "TAG_BOUND",
                "payload_json": {
                    "parcel_code": parcel_code,
                    "tag_id": tag_id,
                    "encrypted_token": encrypted_token,
                    "pickup_binding_id": binding_id,
                    "station_id": settings.station_id,
                },
            }
        )
        typer.echo(f"tag bound and queued: {parcel_code} -> {tag_id}")
    finally:
        db.close()


@app.command("confirm-pickup")
def cli_confirm_pickup(
    parcel_code: str = typer.Option(..., prompt=True),
    receiver_phone: str | None = typer.Option(None),
    pickup_code: str | None = typer.Option(None),
):
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
        service = SyncService(db, ServerClient(settings), settings.station_id)
        event = service.create_pickup_event(
            PickupEventType.OFFLINE_PICKUP,
            {
                "parcel_code": parcel_code,
                "server_parcel_id": parcel.server_parcel_id,
                "receiver_phone_confirmed": bool(receiver_phone),
                "pickup_code_confirmed": bool(pickup_code),
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


@app.command("list-parcels")
def cli_list_parcels(limit: int = 50):
    db = SessionLocal()
    try:
        rows = list(db.scalars(select(LocalParcel).order_by(LocalParcel.created_at.desc()).limit(limit)))
        for r in rows:
            typer.echo(f"{r.server_parcel_id} {r.parcel_code} {r.status}")
    finally:
        db.close()


@app.command("list-tags")
def cli_list_tags(limit: int = 50):
    db = SessionLocal()
    try:
        rows = list(db.scalars(select(LocalTag).order_by(LocalTag.created_at.desc()).limit(limit)))
        for r in rows:
            typer.echo(f"{r.tag_id} {r.status} battery={r.battery_level}")
    finally:
        db.close()


@app.command("list-tasks")
def cli_list_tasks(limit: int = 50):
    db = SessionLocal()
    try:
        for t in TaskService(db).list_tasks(limit=limit):
            typer.echo(f"{t.task_id} {t.task_type} {t.status} retries={t.retry_count}")
    finally:
        db.close()


@app.command("run")
def cli_run():
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
