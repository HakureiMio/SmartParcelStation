from app.main import app


def test_bearer_pickup_routes_exist():
    paths = {route.path for route in app.routes}
    assert '/api/v1/users/me/parcels' in paths
    assert '/api/v1/pickup/manual-confirm' in paths
    assert '/api/v1/pickup/nfc-confirm' in paths
