from __future__ import annotations

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gateway_code: str = Field(alias="GATEWAY_CODE")
    gateway_secret: str = Field(alias="GATEWAY_SECRET")
    station_id: str = Field(alias="STATION_ID")

    server_base_url: str = Field(alias="SERVER_BASE_URL")

    mqtt_host: str = Field(alias="MQTT_HOST")
    mqtt_port: int = Field(default=1883, alias="MQTT_PORT")
    mqtt_username: str = Field(default="", alias="MQTT_USERNAME")
    mqtt_password: str = Field(default="", alias="MQTT_PASSWORD")

    sqlite_path: str = Field(alias="SQLITE_PATH")
    mock_nfc_enabled: bool = Field(default=True, alias="MOCK_NFC_ENABLED")
    mock_ble_enabled: bool = Field(default=True, alias="MOCK_BLE_ENABLED")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    sync_pull_interval_seconds: int = Field(default=30, alias="SYNC_PULL_INTERVAL_SECONDS")
    sync_push_interval_seconds: int = Field(default=15, alias="SYNC_PUSH_INTERVAL_SECONDS")
    heartbeat_interval_seconds: int = Field(default=20, alias="HEARTBEAT_INTERVAL_SECONDS")

    @property
    def sqlite_url(self) -> str:
        path = Path(self.sqlite_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    global _settings
    _settings = Settings()
    return _settings
