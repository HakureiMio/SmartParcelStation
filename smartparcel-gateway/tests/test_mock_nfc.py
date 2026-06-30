import json
import uuid
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
from gateway.legacy.mock_ble_service import MockBleService
from gateway.legacy.mock_nfc_service import MockNfcService
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
    card_uid = f"CARD-{uuid.uuid4().hex}"
    user_id = f"u-{uuid.uuid4().hex}"
    parcel_id = f"sp-{uuid.uuid4().hex}"
    binding_id = f"pb-{uuid.uuid4().hex}"
    tag_id = f"tag-{uuid.uuid4().hex}"
    try:
        db.add(LocalNfcCredential(credential_type=CredentialType.CARD_UID, credential_value=card_uid, user_id=user_id, station_id=settings.station_id, status=CredentialStatus.ACTIVE))
        db.add(LocalParcel(server_parcel_id=parcel_id, parcel_code=f"p-{uuid.uuid4().hex}", receiver_user_id=user_id, station_id=settings.station_id, status=ParcelStatus.WAITING_PICKUP))
        db.add(LocalParcelTagBinding(pickup_binding_id=binding_id, server_parcel_id=parcel_id, tag_id=tag_id, station_id=settings.station_id))
        db.commit()

        svc = MockNfcService(db, SyncService(db, DummyClient(settings), settings.station_id), TaskService(db), MockBleService())
        result = svc.handle_card(card_uid)
        assert result["ok"] is True
        tasks = TaskService(db).list_tasks()
        assert any(t.task_type == TaskType.TAG_WAKE for t in tasks)
    finally:
        db.close()
