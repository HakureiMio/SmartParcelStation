import os

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

os.environ['MQTT_ENABLED'] = 'false'
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///./test.db'

from app.main import app  # noqa: E402
from app.schemas.schemas import ParcelCreate  # noqa: E402


client = TestClient(app)


def test_health():
    response = client.get('/api/v1/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_version():
    response = client.get('/api/v1/version')
    assert response.status_code == 200
    assert response.json()['app'] == 'smartparcel-server'


def test_create_parcel_rejects_blank_parcel_code():
    with pytest.raises(ValidationError):
        ParcelCreate(parcel_code='   ', station_id=1, receiver_user_id=2)
