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
