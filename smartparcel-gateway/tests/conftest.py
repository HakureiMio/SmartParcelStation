import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Test defaults — BLE_BACKEND=real, no mock fallbacks
os.environ.setdefault("GATEWAY_CODE", "gw-test")
os.environ.setdefault("GATEWAY_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("GATEWAY_DEVICE_ID", "GWDEV-TEST-0001")
os.environ.setdefault("GATEWAY_SERIAL", "SPS-GW-TEST-0001")
os.environ.setdefault("STATION_ID", "station-test")
os.environ.setdefault("BINDING_STATUS", "BOUND")
os.environ.setdefault("SERVER_BASE_URL", "http://127.0.0.1:8000")
os.environ.setdefault("PUBLIC_SERVER_BASE_URL", "")
os.environ.setdefault("MQTT_HOST", "127.0.0.1")
os.environ.setdefault("MQTT_PORT", "1883")
os.environ.setdefault("MQTT_USERNAME", "")
os.environ.setdefault("MQTT_PASSWORD", "")
os.environ.setdefault("MQTT_TLS_ENABLED", "false")
os.environ.setdefault("SQLITE_PATH", str(Path(tempfile.gettempdir()) / "smartparcel_gateway_test.db"))
os.environ.setdefault("BLE_BACKEND", "real")
os.environ.setdefault("LOG_LEVEL", "INFO")
os.environ.setdefault("ALLOW_DEV_HTTP", "true")
os.environ.setdefault("ALLOW_UNSAFE_DEV_AUTOREGISTER", "false")
os.environ.setdefault("PROVISIONING_ENABLED", "true")
os.environ.setdefault("LOCAL_API_TOKEN_TTL_SECONDS", "3600")
os.environ.setdefault("PROVISIONING_TOKEN_TTL_SECONDS", "600")
