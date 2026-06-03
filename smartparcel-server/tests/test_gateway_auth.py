import asyncio
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

os.environ['MQTT_ENABLED'] = 'false'
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite://'
os.environ['GATEWAY_SIGNATURE_TOLERANCE_SECONDS'] = '300'

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.security import generate_gateway_signature, raw_body_hash, validate_gateway_timestamp  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import GatewayRegistrationTokenStatus, ParcelOrigin, ParcelStatus, ParcelSyncStatus, UserRole  # noqa: E402
from app.models.models import Gateway, GatewayRegistrationToken, GatewaySyncEvent, Notification, Parcel, PickupEvent, Station, Tag, User  # noqa: E402
from app.services.services import hash_registration_token  # noqa: E402


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
SECRET = 'test-gateway-secret'
GATEWAY_CODE = 'GWTEST'


def stable_body(payload) -> bytes:
    if payload is None:
        return b''
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def signed_headers(
    method: str,
    path: str,
    payload=None,
    secret: str = SECRET,
    timestamp: int | None = None,
    nonce: str | None = None,
    gateway_code: str = GATEWAY_CODE,
):
    raw = stable_body(payload)
    body_sha = raw_body_hash(raw)
    ts = str(timestamp if timestamp is not None else int(time.time()))
    nonce_value = nonce or uuid.uuid4().hex
    return {
        'Content-Type': 'application/json',
        'X-Gateway-Code': gateway_code,
        'X-Gateway-Timestamp': ts,
        'X-Gateway-Nonce': nonce_value,
        'X-Gateway-Body-SHA256': body_sha,
        'X-Gateway-Signature': generate_gateway_signature(secret, method, path, ts, nonce_value, body_sha),
    }, raw


async def reset_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with TestSessionLocal() as db:
        station = Station(id=1, station_code='STAUTH', name='Auth Test', address='Local', status='ACTIVE')
        admin = User(id=1, display_name='Admin', phone='18800000001', role=UserRole.SERVER_ADMIN, is_active=True)
        staff = User(id=3, display_name='Staff', phone='18800000003', role=UserRole.STAFF, station_id=1, is_active=True)
        gateway = Gateway(gateway_code=GATEWAY_CODE, station_id=1, device_secret_hash=SECRET, status='ACTIVE')
        db.add(station)
        db.add(admin)
        db.add(staff)
        db.add(gateway)
        await db.commit()


def setup_function():
    asyncio.run(reset_db())


def test_gateway_and_server_signature_vector():
    body_sha = hashlib.sha256(b'{"a":1}').hexdigest()
    sig = generate_gateway_signature('secret', 'POST', '/api/v1/x', '100', 'nonce', body_sha)
    assert sig == generate_gateway_signature('secret', 'post', '/api/v1/x', '100', 'nonce', body_sha)
    assert len(sig) == 64


def test_timestamp_expired_fails():
    try:
        validate_gateway_timestamp(str(int(time.time()) - 9999), 300)
    except Exception as exc:
        assert getattr(exc, 'status_code', None) == 401
    else:
        raise AssertionError('expired timestamp should fail')


def test_health_remains_public():
    response = client.get('/api/v1/health')
    assert response.status_code == 200


def test_sync_push_requires_signature():
    response = client.post(f'/api/v1/gateways/{GATEWAY_CODE}/sync/push', json=[])
    assert response.status_code == 401


def test_sync_push_accepts_valid_signature_and_rejects_replay():
    path = f'/api/v1/gateways/{GATEWAY_CODE}/sync/push'
    headers, raw = signed_headers('POST', path, [])
    response = client.post(path, headers=headers, content=raw)
    assert response.status_code == 200

    replay = client.post(path, headers=headers, content=raw)
    assert replay.status_code == 401


def test_heartbeat_accepts_valid_signature():
    path = '/api/v1/gateways/heartbeat'
    payload = {'gateway_code': GATEWAY_CODE, 'status': 'ONLINE'}
    headers, raw = signed_headers('POST', path, payload)
    response = client.post(path, headers=headers, content=raw)
    assert response.status_code == 200
    assert response.json()['gateway_code'] == GATEWAY_CODE


def test_sync_pull_accepts_valid_signature():
    path = f'/api/v1/gateways/{GATEWAY_CODE}/sync/pull'
    headers, raw = signed_headers('GET', path, None)
    response = client.request('GET', path, headers=headers, content=raw)
    assert response.status_code == 200
    assert response.json()['events'] == []


def test_events_accept_valid_signature():
    path = f'/api/v1/gateways/{GATEWAY_CODE}/events'
    payload = {'event_id': uuid.uuid4().hex, 'event_type': 'PING', 'payload_json': {}}
    headers, raw = signed_headers('POST', path, payload)
    response = client.post(path, headers=headers, content=raw)
    assert response.status_code == 200
    assert response.json()['status'] == 'accepted'


def test_sync_push_rejects_bad_signature():
    path = f'/api/v1/gateways/{GATEWAY_CODE}/sync/push'
    headers, raw = signed_headers('POST', path, [])
    headers['X-Gateway-Signature'] = '0' * 64
    response = client.post(path, headers=headers, content=raw)
    assert response.status_code == 401


def test_core_gateway_routes_require_auth():
    assert client.post('/api/v1/gateways/heartbeat', json={'gateway_code': GATEWAY_CODE, 'status': 'ONLINE'}).status_code == 401
    assert client.get(f'/api/v1/gateways/{GATEWAY_CODE}/sync/pull').status_code == 401
    assert client.post(f'/api/v1/gateways/{GATEWAY_CODE}/events', json={'event_id': 'e1', 'event_type': 'PING', 'payload_json': {}}).status_code == 401


def sync_push(items):
    path = f'/api/v1/gateways/{GATEWAY_CODE}/sync/push'
    headers, raw = signed_headers('POST', path, items)
    return client.post(path, headers=headers, content=raw)


def test_server_tag_management_routes_are_removed_from_openapi_and_return_404():
    openapi = client.get('/api/v1/openapi.json')
    if openapi.status_code == 404:
        openapi = client.get('/openapi.json')
    assert openapi.status_code == 200
    paths = openapi.json()['paths']
    removed_paths = [
        '/api/v1/tags',
        '/api/v1/tags/{tag_id}',
        '/api/v1/tags/bind',
        '/api/v1/tags/release',
        '/api/v1/tags/status-report',
    ]
    for path in removed_paths:
        assert path not in paths

    assert client.post('/api/v1/tags', json={}).status_code == 404
    assert client.get('/api/v1/tags').status_code == 404
    assert client.get('/api/v1/tags/1').status_code == 404
    assert client.post('/api/v1/tags/bind', json={}).status_code == 404
    assert client.post('/api/v1/tags/release', json={}).status_code == 404
    assert client.post('/api/v1/tags/status-report', json={}).status_code == 404


def test_tag_exception_reported_sync_creates_staff_notification_without_tag_state():
    item = {
        'event_id': uuid.uuid4().hex,
        'event_type': 'TAG_EXCEPTION_REPORTED',
        'payload_json': {
            'gateway_code': GATEWAY_CODE,
            'station_id': 1,
            'tag_ref': 'TAG001',
            'exception_type': 'LOW_BATTERY',
            'severity': 'WARNING',
            'message': '智能寻物标签电量过低',
            'occurred_at': '2026-06-03T10:00:00Z',
        },
    }
    response = sync_push([item])
    assert response.status_code == 200

    async def check_db():
        async with TestSessionLocal() as db:
            notifications = (await db.execute(select(Notification))).scalars().all()
            sync_events = (await db.execute(select(GatewaySyncEvent))).scalars().all()
            tags = (await db.execute(select(Tag))).scalars().all()
            assert len(notifications) == 1
            assert 'LOW_BATTERY' in notifications[0].content
            assert len(sync_events) == 1
            assert sync_events[0].event_type == 'TAG_EXCEPTION_REPORTED'
            assert tags == []

    asyncio.run(check_db())


def test_tag_nfc_fast_pickup_method_is_kept_in_pickup_audit_payload():
    async def seed_parcel():
        async with TestSessionLocal() as db:
            db.add(
                Parcel(
                    parcel_code='P-TAG-NFC',
                    pickup_code='123456',
                    receiver_user_id=None,
                    receiver_phone='18800000002',
                    station_id=1,
                    status=ParcelStatus.WAITING_PICKUP,
                    origin=ParcelOrigin.GATEWAY_INBOUND,
                    sync_status=ParcelSyncStatus.MERGED,
                )
            )
            await db.commit()

    asyncio.run(seed_parcel())

    item = {
        'event_id': uuid.uuid4().hex,
        'event_type': 'OFFLINE_PICKUP',
        'payload_json': {
            'parcel_code': 'P-TAG-NFC',
            'pickup_method': 'TAG_NFC_FAST',
        },
    }
    response = sync_push([item])
    assert response.status_code == 200

    async def check_db():
        async with TestSessionLocal() as db:
            event = (await db.execute(select(PickupEvent))).scalar_one()
            parcel = (await db.execute(select(Parcel).where(Parcel.parcel_code == 'P-TAG-NFC'))).scalar_one()
            assert event.payload_json['pickup_method'] == 'TAG_NFC_FAST'
            assert parcel.status == ParcelStatus.PICKED_UP

    asyncio.run(check_db())


def test_tag_status_report_sync_is_audit_only_and_does_not_create_tag():
    item = {
        'event_id': uuid.uuid4().hex,
        'event_type': 'TAG_STATUS_REPORT',
        'payload_json': {
            'tag_id': 'TAG001',
            'status': 'LOW_BATTERY',
            'battery_level': 5,
        },
    }
    response = sync_push([item])
    assert response.status_code == 200

    async def check_db():
        async with TestSessionLocal() as db:
            sync_event = (await db.execute(select(GatewaySyncEvent))).scalar_one()
            tags = (await db.execute(select(Tag))).scalars().all()
            assert sync_event.event_type == 'TAG_STATUS_REPORT'
            assert sync_event.payload_json['status'] == 'LOW_BATTERY'
            assert tags == []

    asyncio.run(check_db())


def test_gate_access_and_tag_wake_sync_events_are_audit_only():
    items = [
        {
            'event_id': uuid.uuid4().hex,
            'event_type': 'NFC_ACCESS_GRANTED',
            'payload_json': {'reader_id': 'GATE01', 'pickup_session_id': 'sess_1', 'session_color': 'BLUE'},
        },
        {
            'event_id': uuid.uuid4().hex,
            'event_type': 'NFC_ACCESS_DENIED',
            'payload_json': {'reader_id': 'GATE01', 'reason': 'CREDENTIAL_NOT_FOUND'},
        },
        {
            'event_id': uuid.uuid4().hex,
            'event_type': 'TAG_WAKE_STARTED',
            'payload_json': {'pickup_session_id': 'sess_1', 'tag_refs': ['TAG001'], 'session_color': 'BLUE'},
        },
    ]
    response = sync_push(items)
    assert response.status_code == 200

    async def check_db():
        async with TestSessionLocal() as db:
            sync_events = (await db.execute(select(GatewaySyncEvent))).scalars().all()
            tags = (await db.execute(select(Tag))).scalars().all()
            assert {event.event_type for event in sync_events} == {'NFC_ACCESS_GRANTED', 'NFC_ACCESS_DENIED', 'TAG_WAKE_STARTED'}
            assert tags == []

    asyncio.run(check_db())


def admin_headers():
    return {'X-Dev-User-Id': '1', 'X-Dev-Role': 'SERVER_ADMIN'}


def create_registration_token(gateway_code='GWBOOT', station_id=1, ttl_seconds=600):
    response = client.post(
        '/api/v1/gateways/registration-tokens',
        headers=admin_headers(),
        json={'gateway_code': gateway_code, 'station_id': station_id, 'ttl_seconds': ttl_seconds},
    )
    assert response.status_code == 200
    return response.json()


def test_server_admin_can_create_registration_token_and_hash_is_stored():
    data = create_registration_token()
    assert data['registration_token']
    assert data['gateway_code'] == 'GWBOOT'

    async def check_db():
        async with TestSessionLocal() as db:
            row = (await db.execute(select(GatewayRegistrationToken))).scalar_one()
            assert row.token_hash == hash_registration_token(data['registration_token'])
            assert row.token_hash != data['registration_token']

    asyncio.run(check_db())


def test_registration_token_list_does_not_return_plain_token():
    data = create_registration_token()
    response = client.get('/api/v1/gateways/registration-tokens', headers=admin_headers())
    assert response.status_code == 200
    row = response.json()[0]
    assert 'registration_token' not in row
    assert row['gateway_code'] == data['gateway_code']


def test_valid_registration_token_activates_gateway_and_secret_can_heartbeat():
    data = create_registration_token(gateway_code='GWACTIVE')
    response = client.post(
        '/api/v1/gateways/bootstrap/activate',
        json={'gateway_code': 'GWACTIVE', 'station_id': 1, 'registration_token': data['registration_token'], 'device_info': {'model': 'test'}},
    )
    assert response.status_code == 200
    gateway_secret = response.json()['gateway_secret']
    assert gateway_secret

    path = '/api/v1/gateways/heartbeat'
    payload = {'gateway_code': 'GWACTIVE', 'status': 'ONLINE'}
    headers, raw = signed_headers('POST', path, payload, secret=gateway_secret, gateway_code='GWACTIVE')
    heartbeat = client.post(path, headers=headers, content=raw)
    assert heartbeat.status_code == 200
    assert heartbeat.json()['gateway_code'] == 'GWACTIVE'


def test_used_registration_token_cannot_activate_twice():
    data = create_registration_token(gateway_code='GWONCE')
    payload = {'gateway_code': 'GWONCE', 'station_id': 1, 'registration_token': data['registration_token'], 'device_info': {}}
    assert client.post('/api/v1/gateways/bootstrap/activate', json=payload).status_code == 200
    assert client.post('/api/v1/gateways/bootstrap/activate', json=payload).status_code == 401


def test_wrong_registration_token_fails():
    create_registration_token(gateway_code='GWBAD')
    response = client.post(
        '/api/v1/gateways/bootstrap/activate',
        json={'gateway_code': 'GWBAD', 'station_id': 1, 'registration_token': 'WRONG-TOKEN', 'device_info': {}},
    )
    assert response.status_code == 401


def test_expired_registration_token_fails():
    data = create_registration_token(gateway_code='GWEXP')

    async def expire_token():
        async with TestSessionLocal() as db:
            row = await db.get(GatewayRegistrationToken, data['id'])
            row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            await db.commit()

    asyncio.run(expire_token())
    response = client.post(
        '/api/v1/gateways/bootstrap/activate',
        json={'gateway_code': 'GWEXP', 'station_id': 1, 'registration_token': data['registration_token'], 'device_info': {}},
    )
    assert response.status_code == 401


def test_revoked_registration_token_cannot_activate():
    data = create_registration_token(gateway_code='GWREVOKE')
    revoke = client.post(f"/api/v1/gateways/registration-tokens/{data['id']}/revoke", headers=admin_headers())
    assert revoke.status_code == 200
    assert revoke.json()['status'] == GatewayRegistrationTokenStatus.REVOKED
    response = client.post(
        '/api/v1/gateways/bootstrap/activate',
        json={'gateway_code': 'GWREVOKE', 'station_id': 1, 'registration_token': data['registration_token'], 'device_info': {}},
    )
    assert response.status_code == 401
