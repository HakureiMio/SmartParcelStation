from gateway.models.entities import CredentialStatus, LocalNfcCredential
from gateway.services.sync_service import SyncService
from tests.stage2_helpers import Client, database


def test_replacement_disables_old_and_activates_new():
    engine, db = database()
    try:
        service = SyncService(db, Client(), "1")
        service.apply_sync_event("USER_ACCESS_CREDENTIAL_UPSERT", {"credential_type":"CARD_UID","credential_value":"OLD","user_id":"2","station_id":"1","status":"ACTIVE"})
        service.apply_sync_event("USER_ACCESS_CREDENTIAL_REPLACED", {"old_credential_value":"OLD","new_credential_value":"NEW","credential_type":"CARD_UID","user_id":"2","station_id":"1"}); db.commit()
        assert db.query(LocalNfcCredential).filter_by(credential_value="OLD").one().status == CredentialStatus.REPLACED
        assert db.query(LocalNfcCredential).filter_by(credential_value="NEW").one().status == CredentialStatus.ACTIVE
    finally: db.close(); engine.dispose()
