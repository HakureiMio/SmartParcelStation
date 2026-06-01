from gateway.core.config import reload_settings


def test_config_loads():
    s = reload_settings()
    assert s.gateway_code == "gw-test"
    assert s.sqlite_url.startswith("sqlite:///")
