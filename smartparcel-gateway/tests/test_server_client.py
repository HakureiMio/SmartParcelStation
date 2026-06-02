from pathlib import Path

from gateway.core.config import reload_settings
from gateway.cli import _upsert_env_values
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


def test_bootstrap_env_update_preserves_unrelated_config():
    env_dir = Path("tests/.tmp_env_test")
    env_dir.mkdir(parents=True, exist_ok=True)
    env_path = env_dir / ".env"
    env_path.write_text("MQTT_HOST=127.0.0.1\nGATEWAY_CODE=OLD\nSQLITE_PATH=./data/gateway.db\n", encoding="utf-8")

    _upsert_env_values(
        env_path,
        {
            "GATEWAY_CODE": "GW001",
            "GATEWAY_SECRET": "new-secret",
            "STATION_ID": "1",
            "SERVER_BASE_URL": "http://127.0.0.1:18000",
        },
    )

    content = env_path.read_text(encoding="utf-8")
    assert "MQTT_HOST=127.0.0.1" in content
    assert "SQLITE_PATH=./data/gateway.db" in content
    assert "GATEWAY_CODE=GW001" in content
    assert "GATEWAY_SECRET=new-secret" in content
    assert env_path.with_suffix(env_path.suffix + ".bak").exists()
