from fastapi.testclient import TestClient
from gateway.local_api import app


def test_qr_session_requires_reader_token_and_generates_payload():
    client = TestClient(app)
    assert client.get("/local/gate/qr-session?reader_id=GATE01").status_code == 401
    response = client.get("/local/gate/qr-session?reader_id=GATE01", headers={"X-Gate-Reader-Id":"GATE01","X-Gate-Reader-Token":"change-this-reader-token"})
    assert response.status_code == 200 and response.json()["qr_payload"].startswith("sps://gate-qr?")
