from fastapi.testclient import TestClient
from gateway.local_api import app


def test_access_card_rejects_local_bearer_without_reader_token():
    response = TestClient(app).post("/local/gate/access-card", headers={"Authorization":"Bearer not-a-reader-token"}, json={"reader_id":"GATE01","credential_type":"CARD_UID","credential_value":"CARD"})
    assert response.status_code == 401
