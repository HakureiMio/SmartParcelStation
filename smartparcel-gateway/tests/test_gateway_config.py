"""Test gateway configuration: .env loading, defaults, binding status."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from gateway.core.config import Settings, get_settings, reload_settings


class TestSettingsDefaults:
    """Verify new config defaults."""

    def test_default_ble_backend_is_real(self):
        settings = Settings()
        assert settings.ble_backend == "real"

    def test_default_binding_status_is_unbound(self, monkeypatch):
        monkeypatch.delenv("BINDING_STATUS", raising=False)
        monkeypatch.delenv("GATEWAY_SECRET", raising=False)
        monkeypatch.delenv("GATEWAY_CODE", raising=False)
        settings = Settings()
        assert settings.binding_status == "UNBOUND"

    def test_is_bound_false_when_unbound(self, monkeypatch):
        monkeypatch.delenv("BINDING_STATUS", raising=False)
        monkeypatch.delenv("GATEWAY_SECRET", raising=False)
        monkeypatch.delenv("GATEWAY_CODE", raising=False)
        settings = Settings()
        assert settings.is_unbound is True
        assert settings.is_bound is False

    def test_is_bound_true_when_bound_with_secret(self):
        settings = Settings(
            GATEWAY_CODE="GW001",
            GATEWAY_SECRET="test-secret",
            BINDING_STATUS="BOUND",
        )
        assert settings.is_bound is True
        assert settings.is_unbound is False

    def test_is_bound_false_when_bound_but_no_secret(self):
        settings = Settings(
            GATEWAY_CODE="GW001",
            GATEWAY_SECRET="",
            BINDING_STATUS="BOUND",
        )
        assert settings.is_bound is False

    def test_allow_dev_http_defaults_false(self, monkeypatch):
        monkeypatch.delenv("ALLOW_DEV_HTTP", raising=False)
        settings = Settings()
        assert settings.allow_dev_http is False

    def test_allow_unsafe_dev_autoregister_defaults_false(self):
        settings = Settings()
        assert settings.allow_unsafe_dev_autoregister is False

    def test_provisioning_enabled_defaults_true(self):
        settings = Settings()
        assert settings.provisioning_enabled is True

    def test_effective_server_base_url(self):
        settings = Settings(
            SERVER_BASE_URL="http://127.0.0.1:18000",
            PUBLIC_SERVER_BASE_URL="https://api.example.com",
        )
        assert settings.effective_server_base_url == "https://api.example.com"

    def test_effective_server_base_url_fallback(self):
        settings = Settings(
            SERVER_BASE_URL="http://127.0.0.1:18000",
            PUBLIC_SERVER_BASE_URL="",
        )
        assert settings.effective_server_base_url == "http://127.0.0.1:18000"

    def test_no_mock_config_fields(self):
        """Verify mock config fields are gone."""
        settings = Settings()
        assert not hasattr(settings, "mock_nfc_enabled")
        assert not hasattr(settings, "mock_ble_enabled")

    def test_sqlite_url_is_absolute(self, tmp_path):
        db_path = tmp_path / "test.db"
        settings = Settings(SQLITE_PATH=str(db_path))
        url = settings.sqlite_url
        assert url.startswith("sqlite:///")
        assert "test.db" in url

    def test_wifi_ap_defaults(self):
        settings = Settings()
        assert settings.wifi_ap_enabled is True
        assert settings.wifi_ap_ssid_prefix == "SmartParcel-GW"
        assert settings.wifi_ap_address == "192.168.4.1"
        assert settings.wifi_ap_interface == "wlan0"

    def test_local_api_defaults(self):
        settings = Settings()
        assert settings.local_api_host == "0.0.0.0"
        assert settings.local_api_port == 19000
        assert settings.local_api_token_ttl_seconds == 3600

    def test_reload_settings_returns_new_instance(self):
        s1 = get_settings()
        s2 = reload_settings()
        assert s1 is not s2


class TestEnvLoading:
    """Verify settings load from env vars."""

    def test_settings_load_from_env(self, monkeypatch):
        monkeypatch.setenv("GATEWAY_CODE", "GW-ENV-TEST")
        monkeypatch.setenv("GATEWAY_DEVICE_ID", "DEV-ENV-001")
        monkeypatch.setenv("BINDING_STATUS", "BOUND")
        monkeypatch.setenv("GATEWAY_SECRET", "env-secret")
        s = Settings()
        assert s.gateway_code == "GW-ENV-TEST"
        assert s.gateway_device_id == "DEV-ENV-001"
        assert s.binding_status == "BOUND"
        assert s.gateway_secret == "env-secret"  # not exposed in API, internal only
