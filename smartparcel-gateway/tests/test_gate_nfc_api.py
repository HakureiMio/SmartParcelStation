from fastapi.testclient import TestClient
from gateway.local_api import app


def test_nfc_payload_generated_for_reader():
    response = TestClient(app).get("/local/gate/nfc-payload?reader_id=GATE01", headers={"X-Gate-Reader-Id":"GATE01","X-Gate-Reader-Token":"change-this-reader-token"})
    assert response.status_code == 200
    assert response.json()["nfc_payload"].startswith("sps://gate-nfc?")
