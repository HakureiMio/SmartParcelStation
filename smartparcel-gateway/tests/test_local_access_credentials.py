from gateway.models.entities import CredentialStatus, CredentialType, LocalNfcCredential, LocalParcel, ParcelStatus
from tests.stage2_helpers import access_service, database


def test_active_card_recognized_but_terminal_cards_rejected():
    engine, db = database()
    try:
        card = LocalNfcCredential(credential_type=CredentialType.CARD_UID, credential_value="ACTIVE", user_id="2", station_id="1", status=CredentialStatus.ACTIVE)
        db.add_all([card, LocalParcel(server_parcel_id="1", parcel_code="P1", receiver_user_id="2", station_id="1", status=ParcelStatus.WAITING_PICKUP, shelf_code="A03")]); db.commit()
        assert access_service(db).handle_access_card("GATE01", "CARD_UID", "ACTIVE")["access"] == "GRANTED"
        for status in (CredentialStatus.REPLACED, CredentialStatus.LOST):
            card.status = status; db.commit()
            assert access_service(db).handle_access_card("GATE01", "CARD_UID", "ACTIVE")["access"] == "DENIED"
    finally: db.close(); engine.dispose()
