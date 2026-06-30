"""Test real account initialization and Bearer token authentication.

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

from app.core.security import _verify_access_token_internal, create_access_token  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
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


# ── Tests ──

def test_register_returns_not_open():
    resp = client.post('/api/v1/auth/register', json={
        'role': 'client', 'username': 'test', 'phone': '18800000099',
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data['ok'] is False
    assert '暂未开放' in data['message']


def test_ensure_default_users_creates_only_two_accounts():
    resp = client.post(
        '/api/v1/dev/default-users',
        headers={'X-Admin-Bootstrap-Token': 'change-me-local-only'},
    )
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) == 2

    display_names = {u['display_name'] for u in users}
    assert '站点管理员' in display_names
    assert '演示用户' in display_names


def test_station_admin_can_login_with_real_token():
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
    data = resp.json()
    assert 'token' in data
    token = data['token']
    assert not token.startswith('demo-token-')
    assert token.startswith('sps1.')


def test_demo_user_can_login_with_real_token():
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
    data = resp.json()
    assert data['token'].startswith('sps1.')


def test_wrong_password_rejected():
    client.post(
        '/api/v1/dev/default-users',
        headers={'X-Admin-Bootstrap-Token': 'change-me-local-only'},
    )
    resp = client.post('/api/v1/auth/login', json={
        'role': 'staff',
        'username': 'station_admin001',
        'password': 'wrong-password',
    })
    assert resp.status_code == 401


def test_nonexistent_user_rejected():
    resp = client.post('/api/v1/auth/login', json={
        'role': 'staff',
        'username': 'nonexistent_user',
        'password': '123456',
    })
    assert resp.status_code == 401


def test_token_verify_roundtrip():
    token = create_access_token(user_id=1, role='staff', station_id=1)
    assert token.startswith('sps1.')
    payload = _verify_access_token_internal(token)
    assert payload is not None
    assert payload['user_id'] == 1
    assert payload['role'] == 'staff'
    assert payload['station_id'] == 1
    assert payload['exp'] > int(time.time())


def test_expired_token_rejected():
    payload = json.dumps({'user_id': 1, 'role': 'staff', 'station_id': None, 'exp': 1000000})
    encoded = b64mod.urlsafe_b64encode(payload.encode('utf-8')).rstrip(b'=').decode('ascii')
    sig = hmac.new(b'test-auth-token-secret', encoded.encode('utf-8'), hashlib.sha256).hexdigest()
    token = f'sps1.{encoded}.{sig}'
    assert _verify_access_token_internal(token) is None


def test_tampered_token_rejected():
    token = create_access_token(user_id=1, role='staff', station_id=1)
    parts = token.split('.')
    tampered = parts[0] + '.tamperedpayload.' + parts[2]
    assert _verify_access_token_internal(tampered) is None
