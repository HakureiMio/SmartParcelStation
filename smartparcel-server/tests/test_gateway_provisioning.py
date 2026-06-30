"""Test gateway provisioning: prepare, activate, heartbeat, confirm.

Uses the same in-memory SQLite pattern as test_gateway_auth.py.
"""

import asyncio
import hashlib
import hmac
import json
import os
import time
import base64 as b64mod

os.environ['MQTT_ENABLED'] = 'false'
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite://'
os.environ['AUTH_TOKEN_SECRET'] = 'test-auth-token-secret'
os.environ['AUTH_TOKEN_TTL_SECONDS'] = '3600'
os.environ['GATEWAY_FACTORY_CODE_PATTERN'] = r'^SPS-GW-[A-Z0-9-]{6,32}$'

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.security import create_access_token  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import UserRole, GatewayFactoryDeviceStatus  # noqa: E402
from app.models.models import Station, User  # noqa: E402

test_engine = create_async_engine(
    'sqlite+aiosqlite://',
    connect_args={'check_same_thread': False},
    poolclass=StaticPool,
)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


async def reset_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def setup_function():
    asyncio.run(reset_db())


def _init_and_get_staff_token() -> str:
    """Initialize accounts and return a staff Bearer token."""
    client.post(
        '/api/v1/dev/default-users',
        headers={'X-Admin-Bootstrap-Token': 'change-me-local-only'},
    )
    resp = client.post('/api/v1/auth/login', json={
        'role': 'staff',
        'username': 'station_admin001',
        'password': '123456',
    })
    assert resp.status_code == 200
    return resp.json()['token']


def _init_and_get_user_token() -> str:
    """Initialize accounts and return a demo user Bearer token."""
    client.post(
        '/api/v1/dev/default-users',
        headers={'X-Admin-Bootstrap-Token': 'change-me-local-only'},
    )
    resp = client.post('/api/v1/auth/login', json={
        'role': 'client',
        'username': 'demo_user001',
        'password': '123456',
    })
    assert resp.status_code == 200
    return resp.json()['token']


# ── Role authorization ──

def test_unauthenticated_prepare_rejected():
    resp = client.post('/api/v1/gateways/provisioning/prepare', json={
        'gateway_factory_code': 'SPS-GW-TEST01', 'station_id': 1,
    })
    assert resp.status_code == 401


def test_normal_user_cannot_prepare():
    token = _init_and_get_user_token()
    resp = client.post(
        '/api/v1/gateways/provisioning/prepare',
        json={'gateway_factory_code': 'SPS-GW-TEST01', 'station_id': 1},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == 403


def test_staff_can_prepare():
    token = _init_and_get_staff_token()
    resp = client.post(
        '/api/v1/gateways/provisioning/prepare',
        json={'gateway_factory_code': 'SPS-GW-TEST01', 'station_id': 1},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['ok'] is True
    assert 'registration_token' in data
    assert 'gateway_secret' not in data


def test_staff_cannot_prepare_for_other_station():
    token = _init_and_get_staff_token()
    # Create a second station so we get 403 (forbidden) rather than 404 (not found)
    async def seed_station2():
        async with TestSessionLocal() as db:
            from app.models.models import Station
            db.add(Station(id=2, station_code='ST002', name='其他站点', address='其他地址', status='ACTIVE'))
            await db.commit()
    asyncio.run(seed_station2())

    resp = client.post(
        '/api/v1/gateways/provisioning/prepare',
        json={'gateway_factory_code': 'SPS-GW-TEST02', 'station_id': 2},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == 403


def test_invalid_factory_code_format_rejected():
    token = _init_and_get_staff_token()
    resp = client.post(
        '/api/v1/gateways/provisioning/prepare',
        json={'gateway_factory_code': 'BAD-FORMAT', 'station_id': 1},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == 400


def test_prepare_does_not_return_secret():
    token = _init_and_get_staff_token()
    resp = client.post(
        '/api/v1/gateways/provisioning/prepare',
        json={'gateway_factory_code': 'SPS-GW-SECRET-TEST', 'station_id': 1},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == 200
    data = resp.json()
    for key in data:
        assert 'secret' not in key.lower()


# ── Confirm ──

def test_confirm_before_activate_returns_pending():
    token = _init_and_get_staff_token()
    prep = client.post(
        '/api/v1/gateways/provisioning/prepare',
        json={'gateway_factory_code': 'SPS-GW-CONFIRM1', 'station_id': 1, 'requested_gateway_code': 'GW-CONFIRM1'},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert prep.status_code == 200
    prep_data = prep.json()

    resp = client.post(
        '/api/v1/gateways/provisioning/confirm',
        json={
            'gateway_factory_code': 'SPS-GW-CONFIRM1',
            'gateway_code': prep_data['gateway_code'],
            'station_id': 1,
        },
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert 'gateway_secret' not in data


def test_confirm_nonexistent_returns_unknown():
    token = _init_and_get_staff_token()
    resp = client.post(
        '/api/v1/gateways/provisioning/confirm',
        json={'gateway_factory_code': 'SPS-GW-NONEXIST', 'gateway_code': 'GW-NOPE', 'station_id': 1},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert 'gateway_secret' not in data


# ── Bootstrap activate with factory code ──

def test_bootstrap_activate_with_factory_code():
    token = _init_and_get_staff_token()
    prep = client.post(
        '/api/v1/gateways/provisioning/prepare',
        json={
            'gateway_factory_code': 'SPS-GW-ACTIVATE1',
            'station_id': 1,
            'requested_gateway_code': 'GW-ACT1',
            'gateway_device_id': 'DEV-ACT1',
            'gateway_serial': 'SPS-GW-ACTIVATE1',
        },
        headers={'Authorization': f'Bearer {token}'},
    )
    assert prep.status_code == 200
    prep_data = prep.json()
    reg_token = prep_data['registration_token']

    activate = client.post('/api/v1/gateways/bootstrap/activate', json={
        'gateway_code': prep_data['gateway_code'],
        'station_id': 1,
        'registration_token': reg_token,
        'device_info': {
            'gateway_factory_code': 'SPS-GW-ACTIVATE1',
            'gateway_device_id': 'DEV-ACT1',
            'gateway_serial': 'SPS-GW-ACTIVATE1',
            'source': 'test',
            'version': '0.2.0',
        },
    })
    assert activate.status_code == 200
    act_data = activate.json()
    assert 'gateway_secret' in act_data
    assert act_data['gateway_code'] == prep_data['gateway_code']


def test_bootstrap_activate_wrong_factory_code_rejected():
    token = _init_and_get_staff_token()
    prep = client.post(
        '/api/v1/gateways/provisioning/prepare',
        json={'gateway_factory_code': 'SPS-GW-BADFACT', 'station_id': 1, 'requested_gateway_code': 'GW-BADFACT'},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert prep.status_code == 200
    prep_data = prep.json()

    activate = client.post('/api/v1/gateways/bootstrap/activate', json={
        'gateway_code': prep_data['gateway_code'],
        'station_id': 1,
        'registration_token': prep_data['registration_token'],
        'device_info': {'gateway_factory_code': 'SPS-GW-WRONGFACT'},
    })
    assert activate.status_code == 401


def test_bootstrap_activate_invalid_token_rejected():
    resp = client.post('/api/v1/gateways/bootstrap/activate', json={
        'gateway_code': 'GW-FAKE',
        'station_id': 1,
        'registration_token': 'INVALID-TOKEN-XXXX',
    })
    assert resp.status_code == 401


# ── Expired Bearer token ──

def test_expired_bearer_token_rejected():
    _init_and_get_staff_token()  # ensure accounts exist
    payload = json.dumps({'user_id': 1, 'role': 'staff', 'station_id': 1, 'exp': int(time.time()) - 3600})
    encoded = b64mod.urlsafe_b64encode(payload.encode('utf-8')).rstrip(b'=').decode('ascii')
    sig = hmac.new(b'test-auth-token-secret', encoded.encode('utf-8'), hashlib.sha256).hexdigest()
    expired_token = f'sps1.{encoded}.{sig}'

    resp = client.post(
        '/api/v1/gateways/provisioning/prepare',
        json={'gateway_factory_code': 'SPS-GW-EXPIRED1', 'station_id': 1},
        headers={'Authorization': f'Bearer {expired_token}'},
    )
    assert resp.status_code == 401
