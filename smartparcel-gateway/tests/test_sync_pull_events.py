from gateway.models.entities import CredentialStatus, GateAuthSession, LocalNfcCredential, LocalParcel
from gateway.services.sync_service import SyncService
from tests.stage2_helpers import Client, database


def test_sync_pull_applies_event_envelope():
    events = [
        {"event_type":"USER_ACCESS_CREDENTIAL_UPSERT","payload_json":{"credential_type":"CARD_UID","credential_value":"CARD1","user_id":"2","station_id":"1","status":"ACTIVE"}},
        {"event_type":"PARCEL_UPSERT","payload_json":{"parcel_id":"10","parcel_code":"P10","user_id":"2","station_id":"1","shelf":"A03","status":"WAITING_PICKUP"}},
        {"event_type":"GATE_USER_AUTH_REQUESTED","payload_json":{"auth_method":"GATE_QR","reader_id":"GATE01","user_id":"2","request_id":"req-1","session_id":"qr-1"}},
    ]
    engine, db = database()
    try:
        SyncService(db, Client(events), "1").sync_pull_once()
        assert db.query(LocalNfcCredential).one().status == CredentialStatus.ACTIVE
        assert db.query(LocalParcel).one().shelf_code == "A03"
        assert db.query(GateAuthSession).filter_by(session_id="qr-1").one().pickup_count == 1
    finally: db.close(); engine.dispose()


def test_sync_pull_event_prefers_shelf_code_and_accepts_shelf_alias():
    events = [
        {"event_type": "PARCEL_UPSERT", "payload_json": {
            "parcel_id": "10", "parcel_code": "P10", "shelf": "A03",
        }},
        {"event_type": "PARCEL_UPSERT", "payload_json": {
            "parcel_id": "10", "parcel_code": "P10", "shelf_code": "B01", "shelf": "OLD",
        }},
    ]
    engine, db = database()
    try:
        SyncService(db, Client(events), "1").sync_pull_once()
        assert db.query(LocalParcel).one().shelf_code == "B01"
    finally:
        db.close(); engine.dispose()


def test_legacy_denormalized_sync_preserves_and_updates_shelf_code():
    class LegacyClient:
        def __init__(self, payload):
            self.payload = payload

        def sync_pull(self):
            return self.payload

    engine, db = database()
    try:
        SyncService(db, LegacyClient({"parcels": [{
            "server_parcel_id": "20", "parcel_code": "P20", "shelf": "A03",
        }]}), "1").sync_pull_once()
        parcel = db.query(LocalParcel).one()
        assert parcel.shelf_code == "A03"

        SyncService(db, LegacyClient({"parcels": [{
            "server_parcel_id": "20", "parcel_code": "P20", "shelf_code": "B01",
        }]}), "1").sync_pull_once()
        assert db.query(LocalParcel).one().shelf_code == "B01"

        SyncService(db, LegacyClient({"parcels": [{
            "server_parcel_id": "20", "parcel_code": "P20",
        }]}), "1").sync_pull_once()
        assert db.query(LocalParcel).one().shelf_code == "B01"
    finally:
        db.close(); engine.dispose()
