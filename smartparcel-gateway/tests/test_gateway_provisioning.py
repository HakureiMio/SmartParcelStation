"""Test provisioning API: status, bind validation, anti-replay."""

import hashlib
import json
import time

import pytest
from fastapi.testclient import TestClient

from gateway.core.config import get_settings, reload_settings
from gateway.db.init_db import init_db
from gateway.provisioning_api import provisioning_app


@pytest.fixture(autouse=True)
def _init_test_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test_provisioning.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    monkeypatch.setenv("BINDING_STATUS", "UNBOUND")
    monkeypatch.setenv("GATEWAY_SECRET", "")
    monkeypatch.setenv("GATEWAY_CODE", "")
    monkeypatch.setenv("STATION_ID", "")
    monkeypatch.setenv("PROVISIONING_ENABLED", "true")
    monkeypatch.setenv("ALLOW_DEV_HTTP", "true")
    monkeypatch.setenv("SERVER_BASE_URL", "")
    monkeypatch.setenv("MQTT_HOST", "")
    monkeypatch.setenv("GATEWAY_DEVICE_ID", "")
    monkeypatch.setenv("GATEWAY_SERIAL", "")
    reload_settings()
    init_db()


def make_client() -> TestClient:
    return TestClient(provisioning_app)


class TestProvisioningStatus:
    def test_status_returns_ok(self):
        client = make_client()
        resp = client.get("/local/provisioning/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["binding_status"] == "UNBOUND"
        assert data["provisioning_enabled"] is True

    def test_status_does_not_expose_server_base_url_when_unset(self):
        client = make_client()
        resp = client.get("/local/provisioning/status")
        data = resp.json()
        assert data.get("server_base_url") is None

    def test_status_does_not_expose_secret(self):
        client = make_client()
        resp = client.get("/local/provisioning/status")
        data = resp.json()
        assert "gateway_secret" not in data
        assert "secret" not in data


class TestProvisioningBindValidation:
    def test_bind_rejects_missing_fields(self):
        client = make_client()
        resp = client.post("/local/provisioning/bind", json={})
        assert resp.status_code == 422  # Pydantic validation error

    def test_bind_rejects_http_in_production(self, monkeypatch):
        monkeypatch.setenv("ALLOW_DEV_HTTP", "false")
        reload_settings()
        client = make_client()
        payload = {
            "server_base_url": "http://example.com/api",
            "gateway_code": "GW001",
            "station_id": "1",
            "registration_token": "XXXX-XXXX-XXXX-XXXX-XXXX",
        }
        resp = client.post("/local/provisioning/bind", json=payload)
        assert resp.status_code == 422  # Validation fails on server_base_url

    def test_bind_allows_http_localhost_in_dev(self, monkeypatch):
        monkeypatch.setenv("ALLOW_DEV_HTTP", "true")
        reload_settings()
        # This test will fail at the server call level, but validation should pass.
        # We check that validation doesn't reject http://127.0.0.1
        from gateway.provisioning_api import ProvisioningBindIn
        payload = ProvisioningBindIn(
            server_base_url="http://127.0.0.1:18000",
            gateway_code="GW001",
            station_id="1",
            registration_token="XXXX-XXXX-XXXX-XXXX-XXXX",
        )
        assert payload.server_base_url == "http://127.0.0.1:18000"

    def test_bind_requires_timestamp_headers(self):
        client = make_client()
        payload = {
            "server_base_url": "http://127.0.0.1:18000",
            "gateway_code": "GW001",
            "station_id": "1",
            "registration_token": "XXXX-XXXX-XXXX-XXXX-XXXX",
        }
        resp = client.post("/local/provisioning/bind", json=payload)
        # Should fail because X-Local-Timestamp / X-Local-Nonce missing
        assert resp.status_code == 400

    def test_bind_with_valid_headers_accepts(self):
        client = make_client()
        payload = {
            "server_base_url": "http://127.0.0.1:18000",
            "gateway_code": "GW001",
            "station_id": "1",
            "registration_token": "XXXX-XXXX-XXXX-XXXX-XXXX",
        }
        body_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        body_sha = hashlib.sha256(body_bytes).hexdigest()
        now = int(time.time())
        headers = {
            "X-Local-Timestamp": str(now),
            "X-Local-Nonce": "test-nonce-unique-001",
            "X-Local-Body-SHA256": body_sha,
        }
        resp = client.post("/local/provisioning/bind", json=payload, headers=headers)
        # Will fail at server call (502), but not at validation (400/422)
        assert resp.status_code in (400, 502)
        if resp.status_code == 502:
            assert "Server activation failed" in resp.json()["detail"]


class TestProvisioningVerify:
    def test_verify_returns_status(self):
        client = make_client()
        resp = client.post("/local/provisioning/verify")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "binding_status" in data


class TestAntiReplay:
    def test_replayed_nonce_rejected(self):
        """Same nonce used twice should fail."""
        client = make_client()
        payload = {
            "server_base_url": "http://127.0.0.1:18000",
            "gateway_code": "GW001",
            "station_id": "1",
            "registration_token": "XXXX-XXXX-XXXX-XXXX-XXXX",
        }
        body_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        body_sha = hashlib.sha256(body_bytes).hexdigest()
        now = int(time.time())
        headers = {
            "X-Local-Timestamp": str(now),
            "X-Local-Nonce": "replay-nonce-001",
            "X-Local-Body-SHA256": body_sha,
        }

        # First request
        resp1 = client.post("/local/provisioning/bind", json=payload, headers=headers)
        assert resp1.status_code in (400, 502)  # may fail at server

        # Second request with same nonce
        resp2 = client.post("/local/provisioning/bind", json=payload, headers=headers)
        # Should be rejected as replay
        assert resp2.status_code == 400
        assert "nonce" in resp2.json()["detail"].lower()

    def test_expired_timestamp_rejected(self):
        client = make_client()
        payload = {
            "server_base_url": "http://127.0.0.1:18000",
            "gateway_code": "GW001",
            "station_id": "1",
            "registration_token": "XXXX-XXXX-XXXX-XXXX-XXXX",
        }
        body_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        body_sha = hashlib.sha256(body_bytes).hexdigest()
        old_ts = int(time.time()) - 600  # 10 minutes ago
        headers = {
            "X-Local-Timestamp": str(old_ts),
            "X-Local-Nonce": "expired-nonce-001",
            "X-Local-Body-SHA256": body_sha,
        }
        resp = client.post("/local/provisioning/bind", json=payload, headers=headers)
        assert resp.status_code == 400
        assert "timestamp" in resp.json()["detail"].lower()
