from app.main import app


def test_gate_auth_routes_require_bearer_dependency():
    paths = {route.path for route in app.routes}
    assert '/api/v1/gate/auth/nfc-confirm' in paths
    assert '/api/v1/gate/auth/qr-confirm' in paths
