import json
import uuid

from gateway.core.config import reload_settings
from gateway.db.init_db import init_db
from gateway.db.session import SessionLocal
from gateway.models.entities import (
    BindingStatus,
    CredentialStatus,
    CredentialType,
    GatewayTask,
    LocalNfcCredential,
    LocalParcel,
    LocalParcelTagBinding,
    LocalPickupSession,
    ParcelStatus,
    SyncQueue,
    TaskType,
)
from gateway.services.access_control_service import AccessControlService
from gateway.services.ble_service import BleService
from gateway.services.server_client import ServerClient
from gateway.services.sync_service import SyncService
from gateway.services.task_service import TaskService


class DummyClient(ServerClient):
    def sync_push(self, payload):
        return {"ok": True}


class FakeBleService(BleService):
    """Test double — returns OK for all BLE operations without hardware."""

    def tag_wake(self, tag_id, led_color="BLUE", blink_pattern="SLOW", beep_pattern="SHORT_INTERVAL", duration_sec=30, pickup_session_id=None):
        return {"tag_id": tag_id, "action": "TAG_WAKE", "result": "OK", "led_color": led_color, "duration_sec": duration_sec, "pickup_session_id": pickup_session_id}

    def tag_stop(self, tag_id, pickup_session_id=None):
        return {"tag_id": tag_id, "action": "TAG_STOP", "result": "OK", "pickup_session_id": pickup_session_id}

    def tag_status_query(self, tag_id):
        return {"tag_id": tag_id, "action": "TAG_STATUS_QUERY", "result": "OK", "battery_level": 80}


def build_service(db, settings):
    return AccessControlService(
        db,
        SyncService(db, DummyClient(settings), settings.station_id),
        TaskService(db),
        FakeBleService(),
        settings.station_id,
    )


def seed_credential(db, settings, card, user_id):
    db.add(
        LocalNfcCredential(
            credential_type=CredentialType.CARD_UID,
            credential_value=card,
            user_id=user_id,
            station_id=settings.station_id,
            status=CredentialStatus.ACTIVE,
        )
    )


def seed_parcel(db, settings, user_id, code, shelf, tag_id=None):
    db.add(
        LocalParcel(
            server_parcel_id=code,
            parcel_code=code,
            receiver_user_id=user_id,
            station_id=settings.station_id,
            status=ParcelStatus.WAITING_PICKUP,
            shelf_code=shelf,
        )
    )
    if tag_id:
        db.add(
            LocalParcelTagBinding(
                pickup_binding_id=uuid.uuid4().hex,
                server_parcel_id=code,
                tag_id=tag_id,
                station_id=settings.station_id,
                status=BindingStatus.ACTIVE,
            )
        )


def event_types(db):
    return [json.loads(row.payload_json)["event_type"] for row in db.query(SyncQueue).all()]


def event_payloads_for_session(db, session_id):
    payloads = [json.loads(row.payload_json) for row in db.query(SyncQueue).all()]
    return [payload for payload in payloads if payload.get("payload_json", {}).get("pickup_session_id") == session_id]


def test_gate_access_single_parcel_grants_and_wakes_tag():
    settings = reload_settings()
    init_db()
    db = SessionLocal()
    user_id = f"u-{uuid.uuid4().hex}"
    card = f"CARD-{uuid.uuid4().hex}"
    try:
        seed_credential(db, settings, card, user_id)
        seed_parcel(db, settings, user_id, f"P-{uuid.uuid4().hex}", "A03", "TAG001")
        db.commit()
        task_count_before = db.query(GatewayTask).filter(GatewayTask.task_type == TaskType.TAG_WAKE).count()

        result = build_service(db, settings).handle_access_card("GATE01", "CARD_UID", card)

        assert result["access"] == "GRANTED"
        assert result["pickup_count"] == 1
        assert result["shelves"] == ["A03"]
        assert result["session_color"]
        assert result["items"][0]["wake_result"] == "OK"
        assert db.query(GatewayTask).filter(GatewayTask.task_type == TaskType.TAG_WAKE).count() == task_count_before + 1
        assert {"NFC_ACCESS_GRANTED", "TAG_WAKE_STARTED"}.issubset({payload["event_type"] for payload in event_payloads_for_session(db, result["pickup_session_id"])})
    finally:
        db.close()


def test_gate_access_multi_parcel_uses_one_color_and_multiple_shelves():
    settings = reload_settings()
    init_db()
    db = SessionLocal()
    user_id = f"u-{uuid.uuid4().hex}"
    card = f"CARD-{uuid.uuid4().hex}"
    try:
        seed_credential(db, settings, card, user_id)
        for shelf, tag in [("A03", "TAG-A"), ("B12", "TAG-B"), ("C07", "TAG-C")]:
            seed_parcel(db, settings, user_id, f"P-{uuid.uuid4().hex}", shelf, tag)
        db.commit()

        result = build_service(db, settings).handle_access_card("GATE01", "CARD_UID", card)
        colors = {item["ble_result"]["led_color"] for item in result["items"]}

        assert result["access"] == "GRANTED"
        assert result["pickup_count"] == 3
        assert result["shelves"] == ["A03", "B12", "C07"]
        assert len(colors) == 1
        assert "A03 B12 C07" in result["display_text"]
        assert result["session_color"] in result["display_text"] or result["color_display_name"] in result["display_text"]
    finally:
        db.close()


def test_gate_access_unknown_card_is_denied_and_audited():
    settings = reload_settings()
    init_db()
    db = SessionLocal()
    try:
        result = build_service(db, settings).handle_access_card("GATE01", "CARD_UID", f"MISSING-{uuid.uuid4().hex}")
        assert result["access"] == "DENIED"
        assert result["reason"] == "CREDENTIAL_NOT_FOUND"
        assert "NFC_ACCESS_DENIED" in event_types(db)
    finally:
        db.close()


def test_gate_access_user_without_waiting_parcel_is_denied():
    settings = reload_settings()
    init_db()
    db = SessionLocal()
    user_id = f"u-{uuid.uuid4().hex}"
    card = f"CARD-{uuid.uuid4().hex}"
    try:
        seed_credential(db, settings, card, user_id)
        db.commit()
        result = build_service(db, settings).handle_access_card("GATE01", "CARD_UID", card)
        assert result["access"] == "DENIED"
        assert result["reason"] == "NO_WAITING_PARCEL"
    finally:
        db.close()


def test_gate_access_waiting_parcel_without_binding_grants_with_warning():
    settings = reload_settings()
    init_db()
    db = SessionLocal()
    user_id = f"u-{uuid.uuid4().hex}"
    card = f"CARD-{uuid.uuid4().hex}"
    try:
        seed_credential(db, settings, card, user_id)
        seed_parcel(db, settings, user_id, f"P-{uuid.uuid4().hex}", "A03")
        db.commit()

        result = build_service(db, settings).handle_access_card("GATE01", "CARD_UID", card)

        assert result["access"] == "GRANTED"
        assert "NO_ACTIVE_TAG_BINDING" in result["warnings"]
        assert db.query(LocalPickupSession).filter(LocalPickupSession.session_id == result["pickup_session_id"]).count() == 1
        session_events = {payload["event_type"] for payload in event_payloads_for_session(db, result["pickup_session_id"])}
        assert "NFC_ACCESS_GRANTED" in session_events
        assert "TAG_WAKE_STARTED" not in session_events
    finally:
        db.close()
