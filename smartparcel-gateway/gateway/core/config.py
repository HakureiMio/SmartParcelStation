from __future__ import annotations

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Gateway identity
    gateway_code: str = Field(default="", alias="GATEWAY_CODE")
    gateway_secret: str = Field(default="", alias="GATEWAY_SECRET")
    gateway_device_id: str = Field(default="", alias="GATEWAY_DEVICE_ID")
    gateway_serial: str = Field(default="", alias="GATEWAY_SERIAL")
    station_id: str = Field(default="", alias="STATION_ID")

    # Binding state
    binding_status: str = Field(default="UNBOUND", alias="BINDING_STATUS")
    config_version: int = Field(default=1, alias="CONFIG_VERSION")

    # Server
    server_base_url: str = Field(default="", alias="SERVER_BASE_URL")
    public_server_base_url: str = Field(default="", alias="PUBLIC_SERVER_BASE_URL")

    # MQTT
    mqtt_host: str = Field(default="", alias="MQTT_HOST")
    mqtt_port: int = Field(default=1883, alias="MQTT_PORT")
    mqtt_username: str = Field(default="", alias="MQTT_USERNAME")
    mqtt_password: str = Field(default="", alias="MQTT_PASSWORD")
    mqtt_tls_enabled: bool = Field(default=False, alias="MQTT_TLS_ENABLED")

    # Local database
    sqlite_path: str = Field(default="./data/gateway.db", alias="SQLITE_PATH")

    # Local API
    local_api_host: str = Field(default="0.0.0.0", alias="LOCAL_API_HOST")
    local_api_port: int = Field(default=19000, alias="LOCAL_API_PORT")
    local_api_token: str = Field(default="", alias="LOCAL_API_TOKEN")
    local_api_token_ttl_seconds: int = Field(default=3600, alias="LOCAL_API_TOKEN_TTL_SECONDS")
    gate_reader_auth_enabled: bool = Field(default=True, alias="GATE_READER_AUTH_ENABLED")
    gate_reader_id: str = Field(default="GATE01", alias="GATE_READER_ID")
    gate_reader_token: str = Field(default="change-this-reader-token", alias="GATE_READER_TOKEN")
    gate_qr_ttl_seconds: int = Field(default=60, alias="GATE_QR_TTL_SECONDS")
    gate_auth_result_ttl_seconds: int = Field(default=15, alias="GATE_AUTH_RESULT_TTL_SECONDS")
    gate_nfc_tag_id: str = Field(default="GATE-NFC-001", alias="GATE_NFC_TAG_ID")

    # Provisioning API
    provisioning_enabled: bool = Field(default=True, alias="PROVISIONING_ENABLED")
    provisioning_host: str = Field(default="0.0.0.0", alias="PROVISIONING_HOST")
    provisioning_port: int = Field(default=19000, alias="PROVISIONING_PORT")
    provisioning_pairing_code: str = Field(default="", alias="PROVISIONING_PAIRING_CODE")
    provisioning_token_ttl_seconds: int = Field(default=600, alias="PROVISIONING_TOKEN_TTL_SECONDS")

    # Wi-Fi AP provisioning
    wifi_ap_enabled: bool = Field(default=True, alias="WIFI_AP_ENABLED")
    wifi_ap_ssid_prefix: str = Field(default="SmartParcel-GW", alias="WIFI_AP_SSID_PREFIX")
    wifi_ap_password: str = Field(default="", alias="WIFI_AP_PASSWORD")
    wifi_ap_interface: str = Field(default="wlan0", alias="WIFI_AP_INTERFACE")
    wifi_ap_address: str = Field(default="192.168.4.1", alias="WIFI_AP_ADDRESS")
    wifi_ap_dhcp_range_start: str = Field(default="192.168.4.50", alias="WIFI_AP_DHCP_RANGE_START")
    wifi_ap_dhcp_range_end: str = Field(default="192.168.4.150", alias="WIFI_AP_DHCP_RANGE_END")

    # Runtime
    ble_backend: str = Field(default="real", alias="BLE_BACKEND")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    sync_pull_interval_seconds: int = Field(default=30, alias="SYNC_PULL_INTERVAL_SECONDS")
    sync_push_interval_seconds: int = Field(default=15, alias="SYNC_PUSH_INTERVAL_SECONDS")
    heartbeat_interval_seconds: int = Field(default=20, alias="HEARTBEAT_INTERVAL_SECONDS")

    # Development options
    allow_dev_http: bool = Field(default=False, alias="ALLOW_DEV_HTTP")
    allow_unsafe_dev_autoregister: bool = Field(default=False, alias="ALLOW_UNSAFE_DEV_AUTOREGISTER")

    @property
    def is_bound(self) -> bool:
        return self.binding_status.upper() == "BOUND" and bool(self.gateway_secret)

    @property
    def is_unbound(self) -> bool:
        return not self.is_bound

    @property
    def sqlite_url(self) -> str:
        path = Path(self.sqlite_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"

    @property
    def effective_server_base_url(self) -> str:
        """Return the server URL to use (public if set, otherwise configured)."""
        return self.public_server_base_url or self.server_base_url


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
