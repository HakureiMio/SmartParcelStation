import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("GATEWAY_CODE", "gw-test")
os.environ.setdefault("GATEWAY_SECRET", "secret-test")
os.environ.setdefault("STATION_ID", "station-test")
os.environ.setdefault("SERVER_BASE_URL", "http://127.0.0.1:8000")
os.environ.setdefault("MQTT_HOST", "127.0.0.1")
os.environ.setdefault("MQTT_PORT", "1883")
os.environ.setdefault("MQTT_USERNAME", "")
os.environ.setdefault("MQTT_PASSWORD", "")
os.environ.setdefault("SQLITE_PATH", str(Path(tempfile.gettempdir()) / "smartparcel_gateway_test.db"))
os.environ.setdefault("MOCK_NFC_ENABLED", "true")
os.environ.setdefault("MOCK_BLE_ENABLED", "true")
os.environ.setdefault("LOG_LEVEL", "INFO")
