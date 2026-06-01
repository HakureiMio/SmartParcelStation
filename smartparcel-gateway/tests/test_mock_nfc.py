import json
from gateway.core.config import reload_settings
from gateway.db.init_db import init_db
from gateway.db.session import SessionLocal
from gateway.models.entities import (
    CredentialStatus,
    CredentialType,
    LocalNfcCredential,
    LocalParcel,
    LocalParcelTagBinding,
    ParcelStatus,
    TaskType,
)
from gateway.services.mock_ble_service import MockBleService
from gateway.services.mock_nfc_service import MockNfcService
from gateway.services.server_client import ServerClient
from gateway.services.sync_service import SyncService
from gateway.services.task_service import TaskService


class DummyClient(ServerClient):
    def __init__(self, settings):
        super().__init__(settings)

    def sync_push(self, payload):
        return {"ok": True}


def test_mock_nfc_creates_tag_wake_task():
    settings = reload_settings()
    init_db()
    db = SessionLocal()
    try:
        db.add(LocalNfcCredential(credential_type=CredentialType.CARD_UID, credential_value="CARD_1", user_id="u1", station_id=settings.station_id, status=CredentialStatus.ACTIVE))
        db.add(LocalParcel(server_parcel_id="sp1", parcel_code="p1", receiver_user_id="u1", station_id=settings.station_id, status=ParcelStatus.WAITING_PICKUP))
        db.add(LocalParcelTagBinding(pickup_binding_id="pb1", server_parcel_id="sp1", tag_id="tag-1", station_id=settings.station_id))
        db.commit()

        svc = MockNfcService(db, SyncService(db, DummyClient(settings), settings.station_id), TaskService(db), MockBleService())
        result = svc.handle_card("CARD_1")
        assert result["ok"] is True
        tasks = TaskService(db).list_tasks()
        assert any(t.task_type == TaskType.TAG_WAKE for t in tasks)
    finally:
        db.close()
