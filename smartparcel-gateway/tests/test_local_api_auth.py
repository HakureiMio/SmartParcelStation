"""Test local API authentication: unbound blocking, token validation, audit logging."""

import hashlib
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from gateway.core.config import Settings
from gateway.db.init_db import init_db
from gateway.db.session import SessionLocal
from gateway.local_api import app
from gateway.local_api_auth import generate_local_session_token, validate_local_session
from gateway.models.entities import LocalApiSession


@pytest.fixture(autouse=True)
def _init_test_db(monkeypatch, tmp_path):
    """Ensure a fresh test DB for each test."""
    db_path = tmp_path / "test_auth.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    # Reload settings so DB path takes effect
    from gateway.core.config import reload_settings
    reload_settings()
    init_db()


def make_client() -> TestClient:
    return TestClient(app)


class TestUnboundGatewayBlocksBusinessEndpoints:
    """When unbound, only /local/health and /local/provisioning/* are allowed."""

    def test_health_always_allowed(self, monkeypatch):
        monkeypatch.setenv("BINDING_STATUS", "UNBOUND")
        monkeypatch.setenv("GATEWAY_SECRET", "")
        monkeypatch.setenv("GATEWAY_CODE", "")
        from gateway.core.config import reload_settings
        reload_settings()

        client = make_client()
        resp = client.get("/local/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_tags_scan_blocked_when_unbound(self, monkeypatch):
        monkeypatch.setenv("BINDING_STATUS", "UNBOUND")
        monkeypatch.setenv("GATEWAY_SECRET", "")
        monkeypatch.setenv("GATEWAY_CODE", "")
        from gateway.core.config import reload_settings
        reload_settings()

        client = make_client()
        resp = client.post("/local/tags/scan", json={"timeout_sec": 1.0})
        assert resp.status_code == 403
        assert "unbound" in resp.json()["detail"].lower()

    def test_tags_list_blocked_when_unbound(self, monkeypatch):
        monkeypatch.setenv("BINDING_STATUS", "UNBOUND")
        monkeypatch.setenv("GATEWAY_SECRET", "")
        from gateway.core.config import reload_settings
        reload_settings()

        client = make_client()
        resp = client.get("/local/tags")
        assert resp.status_code == 403

    def test_gate_access_blocked_when_unbound(self, monkeypatch):
        monkeypatch.setenv("BINDING_STATUS", "UNBOUND")
        monkeypatch.setenv("GATEWAY_SECRET", "")
        from gateway.core.config import reload_settings
        reload_settings()

        client = make_client()
        resp = client.post("/local/gate/access-card", json={
            "reader_id": "G01",
            "credential_type": "CARD_UID",
            "credential_value": "test123",
        })
        assert resp.status_code == 403


class TestBoundGatewayRequiresAuth:
    """When bound, business endpoints require Bearer token."""

    def test_no_token_returns_401(self, monkeypatch):
        monkeypatch.setenv("BINDING_STATUS", "BOUND")
        monkeypatch.setenv("GATEWAY_SECRET", "test-secret")
        monkeypatch.setenv("GATEWAY_CODE", "GW001")
        monkeypatch.setenv("STATION_ID", "1")
        from gateway.core.config import reload_settings
        reload_settings()

        client = make_client()
        resp = client.get("/local/tags")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, monkeypatch):
        monkeypatch.setenv("BINDING_STATUS", "BOUND")
        monkeypatch.setenv("GATEWAY_SECRET", "test-secret")
        monkeypatch.setenv("GATEWAY_CODE", "GW001")
        monkeypatch.setenv("STATION_ID", "1")
        from gateway.core.config import reload_settings
        reload_settings()

        client = make_client()
        resp = client.get("/local/tags", headers={"Authorization": "Bearer invalid-token-12345"})
        assert resp.status_code == 401

    def test_valid_token_allows_access(self, monkeypatch):
        monkeypatch.setenv("BINDING_STATUS", "BOUND")
        monkeypatch.setenv("GATEWAY_SECRET", "test-secret")
        monkeypatch.setenv("GATEWAY_CODE", "GW001")
        monkeypatch.setenv("STATION_ID", "1")
        monkeypatch.setenv("LOCAL_API_TOKEN_TTL_SECONDS", "3600")
        from gateway.core.config import reload_settings
        reload_settings()

        # Generate a valid session token
        token = generate_local_session_token(role="gateway-operator", source_ip="127.0.0.1")

        client = make_client()
        resp = client.get("/local/tags", headers={"Authorization": f"Bearer {token}"})
        # Should be 200 (tags list, possibly empty)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_expired_token_returns_401(self, monkeypatch):
        monkeypatch.setenv("BINDING_STATUS", "BOUND")
        monkeypatch.setenv("GATEWAY_SECRET", "test-secret")
        monkeypatch.setenv("GATEWAY_CODE", "GW001")
        monkeypatch.setenv("STATION_ID", "1")
        monkeypatch.setenv("LOCAL_API_TOKEN_TTL_SECONDS", "1")  # 1 second TTL
        from gateway.core.config import reload_settings
        reload_settings()

        token = generate_local_session_token(source_ip="127.0.0.1")

        # Manually expire the session
        db = SessionLocal()
        try:
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            session = db.query(LocalApiSession).filter(
                LocalApiSession.session_token_hash == token_hash
            ).first()
            if session:
                session.expires_at = datetime.utcnow() - timedelta(seconds=10)
                db.commit()
        finally:
            db.close()

        client = make_client()
        resp = client.get("/local/tags", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401


class TestSecurityAuditOnAuthFailure:
    """Auth failures should write to gateway_security_audit."""

    def test_failed_auth_writes_audit(self, monkeypatch):
        monkeypatch.setenv("BINDING_STATUS", "BOUND")
        monkeypatch.setenv("GATEWAY_SECRET", "test-secret")
        monkeypatch.setenv("GATEWAY_CODE", "GW001")
        monkeypatch.setenv("STATION_ID", "1")
        from gateway.core.config import reload_settings
        reload_settings()

        client = make_client()
        resp = client.get("/local/tags")  # No auth header
        assert resp.status_code == 401

        # Check audit table
        db = SessionLocal()
        try:
            from gateway.models.entities import GatewaySecurityAudit
            audits = db.query(GatewaySecurityAudit).filter(
                GatewaySecurityAudit.event_type == "local_auth_failed"
            ).all()
            assert len(audits) >= 1
        finally:
            db.close()
