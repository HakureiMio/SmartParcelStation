from gateway.core.config import reload_settings
from gateway.services.server_client import ServerClient


def test_server_client_builds_gateway_headers(monkeypatch):
    settings = reload_settings()
    c = ServerClient(settings)

    captured = {}

    class DummyResponse:
        content = b"{}"

        def raise_for_status(self):
            return None

        def json(self):
            return {}

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers):
            captured.update(headers)
            return DummyResponse()

    monkeypatch.setattr("httpx.Client", lambda timeout, trust_env=False: DummyClient())
    c.health()

    assert "X-Gateway-Code" in captured
    assert "X-Gateway-Body-SHA256" in captured
    assert "X-Gateway-Signature" in captured
