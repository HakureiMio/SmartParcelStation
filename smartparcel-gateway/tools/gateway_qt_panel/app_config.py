from __future__ import annotations

import platform
import sys
from dataclasses import dataclass
from pathlib import Path


LOCAL_API_BASE_URL = "http://127.0.0.1:19000"
SERVER_HEALTH_PATH = "/api/v1/health"

FIRST_BOOT_KEYS = [
    "GATEWAY_CODE",
    "STATION_ID",
    "SERVER_BASE_URL",
    "SQLITE_PATH",
    "BLE_BACKEND",
    "MQTT_HOST",
    "MQTT_PORT",
    "MQTT_USERNAME",
    "MQTT_PASSWORD",
    "LOG_LEVEL",
    "SYNC_PULL_INTERVAL_SECONDS",
    "SYNC_PUSH_INTERVAL_SECONDS",
    "HEARTBEAT_INTERVAL_SECONDS",
]

CONFIG_ALLOWED_KEYS = [
    "GATEWAY_CODE",
    "STATION_ID",
    "SERVER_BASE_URL",
    "SQLITE_PATH",
    "BLE_BACKEND",
    "LOG_LEVEL",
    "MOCK_NFC_ENABLED",
    "MOCK_BLE_ENABLED",
    "MQTT_HOST",
    "MQTT_PORT",
    "MQTT_USERNAME",
    "MQTT_PASSWORD",
    "SYNC_PULL_INTERVAL_SECONDS",
    "SYNC_PUSH_INTERVAL_SECONDS",
    "HEARTBEAT_INTERVAL_SECONDS",
]

SECRET_KEYS = {"GATEWAY_SECRET", "MQTT_PASSWORD", "REGISTRATION_TOKEN", "DEBUG_TOKEN"}

DB_TABLE_WHITELIST = [
    "local_parcels",
    "local_tags",
    "local_parcel_tag_bindings",
    "local_nfc_credentials",
    "local_pickup_events",
    "local_pickup_sessions",
    "gateway_tasks",
    "sync_queue",
]


@dataclass(frozen=True)
class GatewayPaths:
    gateway_dir: Path
    env_path: Path
    env_example_path: Path
    default_sqlite_path: Path


def find_gateway_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if (candidate / "gateway" / "main.py").exists() and (candidate / ".env.example").exists():
            return candidate
    raise RuntimeError("无法定位 smartparcel-gateway 根目录")


def get_paths() -> GatewayPaths:
    gateway_dir = find_gateway_root()
    return GatewayPaths(
        gateway_dir=gateway_dir,
        env_path=gateway_dir / ".env",
        env_example_path=gateway_dir / ".env.example",
        default_sqlite_path=gateway_dir / "data" / "gateway.db",
    )


def resolve_gateway_path(gateway_dir: Path, value: str | None) -> Path:
    if not value:
        return gateway_dir / "data" / "gateway.db"
    path = Path(value)
    if not path.is_absolute():
        path = gateway_dir / path
    return path


def bool_to_env(value: bool) -> str:
    return "true" if value else "false"


def env_to_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    return "********"


def system_summary(gateway_dir: Path) -> dict[str, str]:
    return {
        "系统平台": platform.platform(),
        "工作目录": str(gateway_dir),
        "Python 版本": sys.version.split()[0],
    }
