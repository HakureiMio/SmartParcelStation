from gateway.models.entities import GateAuthSession, GateAuthStatus, LocalParcel, ParcelStatus
from tests.stage2_helpers import access_service, database


def test_user_gate_auth_granted_and_denied_are_recorded():
    engine, db = database()
    try:
        service = access_service(db)
        denied = service.handle_gate_auth_by_user("GATE_QR", "GATE01", "none", "req-denied", "qr-denied")
        assert denied["access"] == "DENIED"
        db.add(LocalParcel(server_parcel_id="2", parcel_code="P2", receiver_user_id="2", station_id="1", status=ParcelStatus.WAITING_PICKUP, shelf_code="B01")); db.commit()
        granted = service.handle_gate_auth_by_user("GATE_NFC_TAG", "GATE01", "2", "req-granted")
        assert granted["access"] == "GRANTED"
        assert {x.status for x in db.query(GateAuthSession).all()} == {GateAuthStatus.DENIED, GateAuthStatus.GRANTED}
    finally: db.close(); engine.dispose()
