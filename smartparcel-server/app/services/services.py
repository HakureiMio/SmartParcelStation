import re
import uuid
import hashlib
import secrets
import hmac
import base64
import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, _record_security_audit
from app.models.enums import (
    EventSource,
    GatewayFactoryDeviceStatus,
    GatewayRegistrationTokenStatus,
    NotificationStatus,
    NotificationType,
    ParcelOrigin,
    ParcelStatus,
    ParcelSyncStatus,
    ParcelTagBindingStatus,
    PickupEventType,
    SyncDirection,
    SyncStatus,
    UserRole,
)
from app.models.models import (
    Gateway,
    GatewayFactoryDevice,
    GatewayRegistrationToken,
    GatewaySyncEvent,
    Notification,
    Parcel,
    ParcelTagBinding,
    PickupEvent,
    SecurityAuditEvent,
    Station,
    Tag,
    User,
)

logger = logging.getLogger(__name__)


def _not_found(name: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'{name} not found')

def hash_password(password: str, salt: str | None = None) -> str:
    effective_salt = salt or secrets.token_urlsafe(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), effective_salt.encode('utf-8'), 120_000)
    return f'pbkdf2_sha256$120000${effective_salt}${base64.b64encode(digest).decode("ascii")}'


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        algorithm, iterations_text, salt, expected = password_hash.split('$', 3)
        if algorithm != 'pbkdf2_sha256':
            return False
        digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), int(iterations_text))
        return hmac.compare_digest(base64.b64encode(digest).decode('ascii'), expected)
    except (ValueError, TypeError):
        return False


def normalize_login_role(role: str) -> UserRole:
    normalized = role.strip().upper()
    if normalized == 'CLIENT':
        return UserRole.USER
    if normalized == 'STAFF':
        return UserRole.STAFF
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='账号或密码错误')


def public_role(role: UserRole) -> str:
    if role == UserRole.USER:
        return 'client'
    if role == UserRole.STAFF:
        return 'staff'
    return role.value.lower()


async def login_with_password(db: AsyncSession, role: str, username: str, password: str) -> dict:
    expected_role = normalize_login_role(role)
    result = await db.execute(select(User).where(User.username == username.strip()))
    user = result.scalar_one_or_none()
    if not user or user.role != expected_role or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='账号或密码错误')
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='账号已停用')
    token = create_access_token(user_id=user.id, role=public_role(user.role), station_id=user.station_id)
    return {
        'token': token,
        'user_id': str(user.id),
        'role': public_role(user.role),
        'display_name': user.display_name,
        'station_id': str(user.station_id) if user.station_id is not None else None,
    }


async def create_station(db: AsyncSession, data: dict) -> Station:
    station = Station(**data)
    db.add(station)
    await db.commit()
    await db.refresh(station)
    return station


async def list_stations(db: AsyncSession) -> list[Station]:
    result = await db.execute(select(Station).order_by(Station.id.desc()))
    return list(result.scalars().all())


async def create_user(db: AsyncSession, data: dict) -> User:
    user = User(**data)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def list_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).order_by(User.id.desc()))
    return list(result.scalars().all())


async def patch_user(db: AsyncSession, user_id: int, data: dict) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise _not_found('user')
    for key, value in data.items():
        if value is not None:
            setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return user


async def ensure_default_users(db: AsyncSession) -> list[User]:
    """Initialize demo station + 2 real accounts for graduation project demo.

    Creates:
      - station_admin001 / STAFF  — miniprogram staff portal & gateway binding
      - demo_user001 / USER       — miniprogram user demo
    Old default accounts (admin001, user001, staff001, gateway001) are deactivated
    if they exist; they are no longer created.
    """
    settings = get_settings()

    # Ensure demo station exists
    default_station = await db.get(Station, 1)
    if not default_station:
        db.add(Station(id=1, station_code='ST001', name='主站点', address='示例路1号', status='ACTIVE'))
        await db.flush()

    # Deactivate legacy default accounts
    legacy_usernames = ['admin001', 'user001', 'staff001', 'gateway001']
    legacy_result = await db.execute(select(User).where(User.username.in_(legacy_usernames)))
    for u in legacy_result.scalars().all():
        if u.username not in {settings.default_station_admin_username, settings.default_demo_user_username}:
            u.is_active = False

    accounts = [
        {
            'username': settings.default_station_admin_username,
            'password': settings.default_station_admin_password,
            'display_name': '站点管理员',
            'phone': '18800000001',
            'role': UserRole.STAFF,
            'station_id': 1,
        },
        {
            'username': settings.default_demo_user_username,
            'password': settings.default_demo_user_password,
            'display_name': '演示用户',
            'phone': '18800000002',
            'role': UserRole.USER,
            'station_id': 1,
        },
    ]
    users: list[User] = []
    for item in accounts:
        username = item.pop('username')
        password = item.pop('password')
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user:
            user.display_name = item['display_name']
            user.phone = item['phone']
            user.role = item['role']
            user.station_id = item['station_id']
            user.is_active = True
            if not user.password_hash or user.password_hash != hash_password(password):
                user.password_hash = hash_password(password)
        else:
            user = User(username=username, password_hash=hash_password(password), is_active=True, **item)
            db.add(user)
        users.append(user)
    await db.commit()
    for user in users:
        await db.refresh(user)
    return users


async def get_station(db: AsyncSession, station_id: int) -> Station:
    station = await db.get(Station, station_id)
    if not station:
        raise _not_found('station')
    return station


async def register_gateway(db: AsyncSession, data: dict) -> Gateway:
    existing = await db.execute(select(Gateway).where(Gateway.gateway_code == data['gateway_code']))
    gateway = existing.scalar_one_or_none()
    if gateway:
        for key, value in data.items():
            setattr(gateway, key, value)
        gateway.last_seen_at = datetime.now(timezone.utc)
    else:
        gateway = Gateway(**data, last_seen_at=datetime.now(timezone.utc))
        db.add(gateway)
    await db.commit()
    await db.refresh(gateway)
    return gateway


async def gateway_heartbeat(db: AsyncSession, gateway_code: str, status_value: str) -> Gateway:
    result = await db.execute(select(Gateway).where(Gateway.gateway_code == gateway_code))
    gateway = result.scalar_one_or_none()
    if not gateway:
        raise _not_found('gateway')
    now = datetime.now(timezone.utc)
    gateway.status = status_value
    gateway.last_seen_at = now

    # Sync factory device status to ONLINE on successful heartbeat
    if gateway.gateway_factory_code and status_value in ('ONLINE',):
        factory_result = await db.execute(
            select(GatewayFactoryDevice).where(
                GatewayFactoryDevice.gateway_factory_code == gateway.gateway_factory_code
            )
        )
        factory_device = factory_result.scalar_one_or_none()
        if factory_device:
            factory_device.status = GatewayFactoryDeviceStatus.ONLINE
            factory_device.last_seen_at = now
            factory_device.bound_gateway_id = gateway.id
            factory_device.gateway_code = gateway_code

    await db.commit()
    await db.refresh(gateway)
    return gateway


async def get_gateway_by_code(db: AsyncSession, gateway_code: str) -> Gateway:
    result = await db.execute(select(Gateway).where(Gateway.gateway_code == gateway_code))
    gateway = result.scalar_one_or_none()
    if not gateway:
        raise _not_found('gateway')
    return gateway


async def list_gateways(db: AsyncSession) -> list[Gateway]:
    result = await db.execute(select(Gateway).order_by(Gateway.id.desc()))
    return list(result.scalars().all())


def generate_registration_token(byte_count: int) -> str:
    raw = secrets.token_urlsafe(byte_count).replace('_', '').replace('-', '').upper()
    token = raw[:20]
    return '-'.join(token[index : index + 4] for index in range(0, len(token), 4))


def hash_registration_token(token: str) -> str:
    return hashlib.sha256(token.strip().encode('utf-8')).hexdigest()


def generate_gateway_secret(byte_count: int) -> str:
    return secrets.token_urlsafe(byte_count)


def is_expired(expires_at: datetime, now: datetime) -> bool:
    if expires_at.tzinfo is None:
        return expires_at <= now.replace(tzinfo=None)
    return expires_at <= now


async def create_gateway_registration_token(
    db: AsyncSession,
    gateway_code: str,
    station_id: int,
    ttl_seconds: int | None,
    created_by_admin_id: int | None,
    gateway_factory_code: str | None = None,
    gateway_device_id: str | None = None,
    gateway_serial: str | None = None,
    created_by_user_id: int | None = None,
) -> tuple[GatewayRegistrationToken, str]:
    await get_station(db, station_id)
    settings = get_settings()
    effective_ttl = ttl_seconds or settings.gateway_registration_token_ttl_seconds
    if effective_ttl <= 0:
        raise HTTPException(status_code=400, detail='ttl_seconds must be positive')

    plain_token = generate_registration_token(settings.gateway_registration_token_bytes)
    row = GatewayRegistrationToken(
        token_id=uuid.uuid4().hex[:12],
        gateway_code=gateway_code,
        station_id=station_id,
        token_hash=hash_registration_token(plain_token),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=effective_ttl),
        status=GatewayRegistrationTokenStatus.PENDING,
        created_by_admin_id=created_by_admin_id,
        created_by_user_id=created_by_user_id,
        gateway_factory_code=gateway_factory_code,
        gateway_device_id=gateway_device_id,
        gateway_serial=gateway_serial,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row, plain_token


async def list_gateway_registration_tokens(db: AsyncSession) -> list[GatewayRegistrationToken]:
    now = datetime.now(timezone.utc)
    result = await db.execute(select(GatewayRegistrationToken).order_by(GatewayRegistrationToken.id.desc()).limit(100))
    rows = list(result.scalars().all())
    changed = False
    for row in rows:
        if row.status == GatewayRegistrationTokenStatus.PENDING and is_expired(row.expires_at, now):
            row.status = GatewayRegistrationTokenStatus.EXPIRED
            changed = True
    if changed:
        await db.commit()
    return rows


async def revoke_gateway_registration_token(db: AsyncSession, token_id: int) -> GatewayRegistrationToken:
    row = await db.get(GatewayRegistrationToken, token_id)
    if not row:
        raise _not_found('gateway registration token')
    if row.status == GatewayRegistrationTokenStatus.PENDING:
        row.status = GatewayRegistrationTokenStatus.REVOKED
        await db.commit()
        await db.refresh(row)
    return row


async def activate_gateway_registration(
    db: AsyncSession,
    gateway_code: str,
    station_id: int,
    registration_token: str,
    device_info: dict | None = None,
) -> tuple[Gateway, str]:
    await get_station(db, station_id)
    result = await db.execute(
        select(GatewayRegistrationToken).where(GatewayRegistrationToken.token_hash == hash_registration_token(registration_token))
    )
    token_row = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if not token_row:
        raise HTTPException(status_code=401, detail='Invalid registration token')
    if token_row.gateway_code != gateway_code or token_row.station_id != station_id:
        raise HTTPException(status_code=401, detail='Registration token does not match gateway')
    if token_row.status == GatewayRegistrationTokenStatus.REVOKED:
        raise HTTPException(status_code=401, detail='Registration token revoked')
    if token_row.status == GatewayRegistrationTokenStatus.USED:
        raise HTTPException(status_code=401, detail='Registration token already used')
    if token_row.status == GatewayRegistrationTokenStatus.EXPIRED or is_expired(token_row.expires_at, now):
        token_row.status = GatewayRegistrationTokenStatus.EXPIRED
        await db.commit()
        raise HTTPException(status_code=401, detail='Registration token expired')

    device_info = device_info or {}
    factory_code_from_token = token_row.gateway_factory_code
    factory_code_from_device = device_info.get('gateway_factory_code', '')
    device_id_from_token = token_row.gateway_device_id
    device_id_from_device = device_info.get('gateway_device_id', '')

    # Validate factory code match if token was created with one
    if factory_code_from_token:
        if not factory_code_from_device:
            raise HTTPException(status_code=401, detail='gateway_factory_code required in device_info')
        if factory_code_from_token.upper() != factory_code_from_device.upper():
            raise HTTPException(status_code=401, detail='gateway_factory_code does not match registration token')
    if device_id_from_token and device_id_from_device:
        if device_id_from_token != device_id_from_device:
            raise HTTPException(status_code=401, detail='gateway_device_id does not match registration token')

    # Check factory device is not DISABLED/REVOKED
    effective_factory_code = factory_code_from_token or factory_code_from_device or None
    if effective_factory_code:
        factory_result = await db.execute(
            select(GatewayFactoryDevice).where(
                GatewayFactoryDevice.gateway_factory_code == effective_factory_code
            )
        )
        factory_device = factory_result.scalar_one_or_none()
        if factory_device and factory_device.status in {GatewayFactoryDeviceStatus.DISABLED, GatewayFactoryDeviceStatus.REVOKED}:
            raise HTTPException(status_code=401, detail='Gateway factory device is disabled or revoked')

    settings = get_settings()
    gateway_secret = generate_gateway_secret(settings.gateway_secret_bytes)

    # Create or update gateway record
    existing_result = await db.execute(select(Gateway).where(Gateway.gateway_code == gateway_code))
    gateway = existing_result.scalar_one_or_none()
    gateway_device_id = device_info.get('gateway_device_id', '') or token_row.gateway_device_id or None
    gateway_serial = device_info.get('gateway_serial', '') or token_row.gateway_serial or None

    if gateway:
        gateway.station_id = station_id
        gateway.device_secret_hash = gateway_secret
        gateway.status = 'ACTIVE'
        gateway.gateway_factory_code = effective_factory_code
        gateway.gateway_device_id = gateway_device_id
        gateway.gateway_serial = gateway_serial
        gateway.bound_at = now
        gateway.last_seen_at = now
    else:
        gateway = Gateway(
            gateway_code=gateway_code,
            station_id=station_id,
            device_secret_hash=gateway_secret,
            status='ACTIVE',
            gateway_factory_code=effective_factory_code,
            gateway_device_id=gateway_device_id,
            gateway_serial=gateway_serial,
            bound_at=now,
            last_seen_at=now,
        )
        db.add(gateway)
        await db.flush()

    # Update factory device status
    if effective_factory_code and factory_device:
        factory_device.status = GatewayFactoryDeviceStatus.BOUND
        factory_device.bound_gateway_id = gateway.id
        factory_device.gateway_code = gateway_code
        factory_device.station_id = station_id
        factory_device.bound_at = now
        factory_device.last_seen_at = now

    # Mark token as used
    token_row.status = GatewayRegistrationTokenStatus.USED
    token_row.used_at = now
    await db.commit()
    await db.refresh(gateway)

    # Security audit
    await _record_security_audit(
        db, 'gateway_bootstrap_activate_success',
        None, gateway_code, '/api/v1/gateways/bootstrap/activate',
        None, {'gateway_factory_code': effective_factory_code, 'token_id': token_row.token_id},
    )

    return gateway, gateway_secret


# ── Gateway Provisioning ──


def _auto_gateway_code(factory_code: str) -> str:
    """Generate a gateway_code from factory_code suffix, e.g. SPS-GW-20260630-0001 → GW0001."""
    m = re.search(r'([A-Z0-9]{4,8})$', factory_code)
    if m:
        return f'GW{m.group(1)}'
    return f'GW{secrets.token_hex(4).upper()[:8]}'


async def prepare_gateway_provisioning(
    db: AsyncSession,
    gateway_factory_code: str,
    station_id: int,
    requested_gateway_code: str | None,
    gateway_device_id: str | None,
    gateway_serial: str | None,
    current_user: User,
) -> dict:
    """Prepare a provisioning request for a gateway device.

    Records the factory device, creates a short-lived registration token, and
    returns binding parameters to the staff member. Does NOT return gateway_secret.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    normalized_factory_code = gateway_factory_code.strip().upper()

    # Validate format
    pattern = settings.gateway_factory_code_pattern
    if not re.match(pattern, normalized_factory_code):
        raise HTTPException(status_code=400, detail=f'gateway_factory_code must match pattern {pattern}')

    # Validate station
    await get_station(db, station_id)

    # STAFF can only bind to own station
    if current_user.role == UserRole.STAFF and current_user.station_id != station_id:
        raise HTTPException(status_code=403, detail='You can only bind gateways to your own station')

    # Resolve or create factory device
    factory_result = await db.execute(
        select(GatewayFactoryDevice).where(GatewayFactoryDevice.gateway_factory_code == normalized_factory_code)
    )
    factory_device = factory_result.scalar_one_or_none()
    is_new_device = False

    if factory_device:
        if factory_device.status in {GatewayFactoryDeviceStatus.DISABLED, GatewayFactoryDeviceStatus.REVOKED}:
            raise HTTPException(status_code=409, detail=f'Gateway factory device is {factory_device.status.value}')
        # If already bound to a different gateway
        if factory_device.status in {GatewayFactoryDeviceStatus.BOUND, GatewayFactoryDeviceStatus.ONLINE}:
            raise HTTPException(status_code=409, detail='Gateway factory code is already bound')
    else:
        is_new_device = True
        factory_device = GatewayFactoryDevice(
            gateway_factory_code=normalized_factory_code,
            gateway_device_id=gateway_device_id or None,
            gateway_serial=gateway_serial or None,
            status=GatewayFactoryDeviceStatus.PENDING_BIND,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(factory_device)
        await db.flush()

    if is_new_device:
        await _record_security_audit(
            db, 'gateway_factory_device_first_seen',
            None, None, None, None,
            {'gateway_factory_code': normalized_factory_code},
        )

    # Determine gateway_code
    gateway_code = (requested_gateway_code or '').strip()
    if not gateway_code:
        gateway_code = _auto_gateway_code(normalized_factory_code)

    # Check gateway_code not already taken by another active gateway
    existing_gw = await db.execute(
        select(Gateway).where(Gateway.gateway_code == gateway_code, Gateway.status.in_(['ACTIVE', 'ONLINE']))
    )
    if existing_gw.scalar_one_or_none():
        # Auto-generate alternative
        gateway_code = f'{gateway_code}-{secrets.token_hex(2).upper()[:4]}'

    # Create registration token
    token_row, plain_token = await create_gateway_registration_token(
        db,
        gateway_code=gateway_code,
        station_id=station_id,
        ttl_seconds=settings.gateway_registration_token_ttl_seconds,
        created_by_admin_id=None,
        gateway_factory_code=normalized_factory_code,
        gateway_device_id=gateway_device_id or None,
        gateway_serial=gateway_serial or None,
        created_by_user_id=current_user.id,
    )

    # Update factory device
    factory_device.status = GatewayFactoryDeviceStatus.PENDING_BIND
    factory_device.station_id = station_id
    factory_device.gateway_code = gateway_code
    factory_device.bind_requested_by_user_id = current_user.id
    factory_device.bind_requested_at = now
    factory_device.last_seen_at = now
    factory_device.gateway_device_id = gateway_device_id or factory_device.gateway_device_id
    factory_device.gateway_serial = gateway_serial or factory_device.gateway_serial

    await db.commit()
    await db.refresh(token_row)
    await db.refresh(factory_device)

    await _record_security_audit(
        db, 'gateway_provisioning_prepare',
        None, None, '/api/v1/gateways/provisioning/prepare',
        None, {
            'gateway_factory_code': normalized_factory_code,
            'gateway_code': gateway_code,
            'token_id': token_row.token_id,
            'created_by_user_id': current_user.id,
        },
    )

    return {
        'ok': True,
        'server_base_url': settings.public_base_url,
        'gateway_code': gateway_code,
        'station_id': str(station_id),
        'gateway_factory_code': normalized_factory_code,
        'registration_token': plain_token,
        'mqtt_host': settings.mqtt_host if settings.mqtt_enabled else None,
        'mqtt_port': settings.mqtt_port if settings.mqtt_enabled else None,
        'mqtt_tls_enabled': False,
        'config_version': 1,
        'expires_at': token_row.expires_at,
    }


async def confirm_gateway_provisioning(
    db: AsyncSession,
    gateway_factory_code: str,
    gateway_code: str,
    station_id: int,
    current_user: User,
) -> dict:
    """Confirm gateway provisioning status. Does NOT return gateway_secret."""

    # STAFF can only query own station
    if current_user.role == UserRole.STAFF and current_user.station_id != station_id:
        raise HTTPException(status_code=403, detail='You can only query gateways in your own station')

    normalized_factory_code = gateway_factory_code.strip().upper()

    factory_result = await db.execute(
        select(GatewayFactoryDevice).where(GatewayFactoryDevice.gateway_factory_code == normalized_factory_code)
    )
    factory_device = factory_result.scalar_one_or_none()

    gateway_result = await db.execute(
        select(Gateway).where(Gateway.gateway_code == gateway_code, Gateway.station_id == station_id)
    )
    gateway = gateway_result.scalar_one_or_none()

    await _record_security_audit(
        db, 'gateway_provisioning_confirm',
        None, None, '/api/v1/gateways/provisioning/confirm',
        None, {
            'gateway_factory_code': normalized_factory_code,
            'gateway_code': gateway_code,
            'station_id': station_id,
            'queried_by_user_id': current_user.id,
        },
    )

    if not factory_device:
        return {
            'ok': False,
            'binding_status': 'UNKNOWN',
            'message': 'Gateway factory code not found',
        }

    if not gateway:
        return {
            'ok': False,
            'binding_status': factory_device.status.value,
            'message': '网关尚未完成激活',
        }

    if gateway.status in ('ACTIVE', 'BOUND'):
        return {
            'ok': True,
            'binding_status': 'BOUND',
            'gateway_online': False,
            'message': '网关已绑定，等待心跳',
        }

    if gateway.status == 'ONLINE':
        return {
            'ok': True,
            'binding_status': 'ONLINE',
            'gateway_online': True,
            'gateway_code': gateway.gateway_code,
            'station_id': str(gateway.station_id),
            'gateway_factory_code': gateway.gateway_factory_code,
            'last_seen_at': gateway.last_seen_at,
            'message': '网关已绑定且在线',
        }

    return {
        'ok': True,
        'binding_status': gateway.status,
        'message': f'网关状态: {gateway.status}',
    }


async def create_parcel(db: AsyncSession, data: dict, admin_id: int | None) -> Parcel:
    parcel = Parcel(**data, created_by_admin_id=admin_id)
    db.add(parcel)
    await db.commit()
    await db.refresh(parcel)
    return parcel


async def list_parcels(db: AsyncSession) -> list[Parcel]:
    result = await db.execute(select(Parcel).order_by(Parcel.id.desc()))
    return list(result.scalars().all())


async def get_parcel(db: AsyncSession, parcel_id: int) -> Parcel:
    parcel = await db.get(Parcel, parcel_id)
    if not parcel:
        raise _not_found('parcel')
    return parcel


async def get_parcel_by_code(db: AsyncSession, parcel_code: str) -> Parcel:
    result = await db.execute(select(Parcel).where(Parcel.parcel_code == parcel_code))
    parcel = result.scalar_one_or_none()
    if not parcel:
        raise _not_found('parcel')
    return parcel


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    if len(phone) <= 4:
        return '*' * len(phone)
    return f'{phone[:3]}****{phone[-4:]}'


def optional_int(value) -> int | None:
    if value in (None, ''):
        return None
    return int(value)


async def query_parcels(
    db: AsyncSession,
    user_id: int | None = None,
    parcel_code: str | None = None,
    receiver_phone: str | None = None,
    pickup_code: str | None = None,
) -> list[dict]:
    query = select(Parcel)
    if user_id is not None:
        query = query.where(Parcel.receiver_user_id == user_id)
    if parcel_code:
        query = query.where(Parcel.parcel_code == parcel_code)
    if receiver_phone:
        query = query.where(Parcel.receiver_phone == receiver_phone)
    if pickup_code:
        query = query.where(Parcel.pickup_code == pickup_code)
    result = await db.execute(query.order_by(Parcel.id.desc()).limit(100))
    return [
        {
            'id': parcel.id,
            'parcel_code': parcel.parcel_code,
            'pickup_code': parcel.pickup_code,
            'receiver_user_id': parcel.receiver_user_id,
            'receiver_phone_masked': mask_phone(parcel.receiver_phone),
            'receiver_name_masked': parcel.receiver_name_masked,
            'station_id': parcel.station_id,
            'status': parcel.status,
            'origin': parcel.origin,
            'sync_status': parcel.sync_status,
        }
        for parcel in result.scalars().all()
    ]


async def patch_parcel_status(db: AsyncSession, parcel_id: int, status_value: ParcelStatus) -> Parcel:
    parcel = await get_parcel(db, parcel_id)
    parcel.status = status_value
    await db.commit()
    await db.refresh(parcel)
    return parcel


async def gateway_pull_sync(db: AsyncSession, gateway_id: int) -> list[GatewaySyncEvent]:
    result = await db.execute(
        select(GatewaySyncEvent).where(GatewaySyncEvent.gateway_id == gateway_id, GatewaySyncEvent.status == SyncStatus.PENDING)
    )
    events = list(result.scalars().all())
    for event in events:
        event.status = SyncStatus.SENT
    await db.commit()
    return events


async def gateway_push_sync(db: AsyncSession, gateway_id: int, station_id: int, items: list[dict]) -> dict:
    accepted = 0
    duplicate = 0
    for item in items:
        exist = await db.execute(select(GatewaySyncEvent).where(GatewaySyncEvent.event_id == item['event_id']))
        row = exist.scalar_one_or_none()
        if row:
            duplicate += 1
            continue
        db.add(
            GatewaySyncEvent(
                event_id=item['event_id'],
                gateway_id=gateway_id,
                station_id=station_id,
                event_type=item['event_type'],
                direction=SyncDirection.GATEWAY_TO_SERVER,
                payload_json=item.get('payload_json', {}),
                status=SyncStatus.ACKED,
                retry_count=0,
            )
        )
        await apply_gateway_business_event(db, gateway_id, station_id, item['event_type'], item.get('payload_json', {}))
        accepted += 1
    await db.commit()
    return {'accepted': accepted, 'duplicate': duplicate}


async def apply_gateway_business_event(db: AsyncSession, gateway_id: int, station_id: int, event_type: str, payload: dict) -> None:
    normalized = event_type.upper()
    if normalized in {'GATEWAY_INBOUND', 'PARCEL_ARRIVED', 'INBOUND_PARCEL'}:
        await apply_gateway_inbound(db, station_id, payload)
    elif normalized == 'TAG_EXCEPTION_REPORTED':
        await apply_gateway_tag_exception_event(db, station_id, payload)
    elif normalized in {'TAG_BOUND', 'TAG_RELEASED', 'TAG_STATUS_REPORT'}:
        await apply_gateway_tag_event(db, station_id, normalized, payload)
    elif normalized in {'NFC_ACCESS_GRANTED', 'NFC_ACCESS_DENIED', 'TAG_WAKE_STARTED'}:
        return
    elif normalized in {'PICKUP_CONFIRMED', 'OFFLINE_PICKUP', 'NFC_FAST_PICKUP_CONFIRMED'}:
        await apply_gateway_pickup_event(db, gateway_id, station_id, payload)


async def apply_gateway_inbound(db: AsyncSession, station_id: int, payload: dict) -> Parcel:
    parcel_code = payload.get('parcel_code')
    if not parcel_code:
        raise HTTPException(status_code=400, detail='parcel_code is required for inbound event')
    result = await db.execute(select(Parcel).where(Parcel.parcel_code == parcel_code))
    parcel = result.scalar_one_or_none()
    if parcel:
        parcel.pickup_code = payload.get('pickup_code') or parcel.pickup_code
        parcel.receiver_user_id = optional_int(payload.get('receiver_user_id')) or parcel.receiver_user_id
        parcel.receiver_phone = payload.get('receiver_phone') or parcel.receiver_phone
        parcel.receiver_name_masked = payload.get('receiver_name_masked') or parcel.receiver_name_masked
        parcel.station_id = int(payload.get('station_id') or station_id)
        parcel.status = ParcelStatus.WAITING_PICKUP
        parcel.sync_status = ParcelSyncStatus.MERGED
    else:
        parcel = Parcel(
            parcel_code=parcel_code,
            pickup_code=payload.get('pickup_code'),
            receiver_user_id=optional_int(payload.get('receiver_user_id')),
            receiver_phone=payload.get('receiver_phone'),
            receiver_name_masked=payload.get('receiver_name_masked'),
            station_id=int(payload.get('station_id') or station_id),
            status=ParcelStatus.WAITING_PICKUP,
            origin=ParcelOrigin.GATEWAY_INBOUND,
            sync_status=ParcelSyncStatus.SYNCED,
            created_by_admin_id=None,
        )
        db.add(parcel)
        await db.flush()

    if parcel.receiver_user_id:
        db.add(
            Notification(
                user_id=parcel.receiver_user_id,
                parcel_id=parcel.id,
                title='Parcel arrived at station',
                content=f'Parcel {parcel.parcel_code} is waiting for pickup.',
                type=NotificationType.IN_APP,
                status=NotificationStatus.PENDING,
            )
        )
    return parcel


async def apply_gateway_tag_event(db: AsyncSession, station_id: int, event_type: str, payload: dict) -> None:
    # Gateway-local-first smart tag mode:
    # TAG_BOUND/TAG_RELEASED are compatibility audit events only, and
    # TAG_STATUS_REPORT is deprecated for production sync. The server keeps the
    # GatewaySyncEvent audit row created by gateway_push_sync(), but does not
    # create/update Tag or ParcelTagBinding state mirrors here.
    return


async def apply_gateway_tag_exception_event(db: AsyncSession, station_id: int, payload: dict) -> None:
    tag_ref = payload.get('tag_ref') or payload.get('tag_id') or 'UNKNOWN_TAG'
    exception_type = payload.get('exception_type') or 'TAG_EXCEPTION'
    severity = payload.get('severity') or 'WARNING'
    message = payload.get('message') or f'Smart tag {tag_ref} reported {exception_type}.'
    payload_station_id = optional_int(payload.get('station_id')) or station_id

    staff_result = await db.execute(
        select(User).where(
            User.role.in_([UserRole.STAFF, UserRole.GATEWAY_ADMIN]),
            (User.station_id == payload_station_id) | (User.station_id.is_(None)),
        )
    )
    staff_users = list(staff_result.scalars().all())

    for staff in staff_users:
        db.add(
            Notification(
                user_id=staff.id,
                parcel_id=None,
                title=f'智能寻物标签异常：{severity}',
                content=f'{message}（标签：{tag_ref}，类型：{exception_type}）',
                type=NotificationType.IN_APP,
                status=NotificationStatus.PENDING,
            )
        )


async def apply_gateway_pickup_event(db: AsyncSession, gateway_id: int, station_id: int, payload: dict) -> None:
    parcel_code = payload.get('parcel_code')
    parcel = None
    if parcel_code:
        result = await db.execute(select(Parcel).where(Parcel.parcel_code == parcel_code))
        parcel = result.scalar_one_or_none()
    if not parcel and payload.get('server_parcel_id'):
        parcel = await db.get(Parcel, int(payload['server_parcel_id']))
    if not parcel:
        return
    parcel.status = ParcelStatus.PICKED_UP
    db.add(
        PickupEvent(
            event_id=payload.get('pickup_event_id') or uuid.uuid4().hex,
            parcel_id=parcel.id,
            user_id=parcel.receiver_user_id,
            station_id=station_id,
            gateway_id=gateway_id,
            event_type=PickupEventType.OFFLINE_PICKUP,
            source=EventSource.GATEWAY,
            payload_json=payload,
        )
    )


async def create_gateway_event(db: AsyncSession, gateway_id: int, station_id: int, event_id: str, event_type: str, payload: dict) -> dict:
    existing = await db.execute(select(GatewaySyncEvent).where(GatewaySyncEvent.event_id == event_id))
    if existing.scalar_one_or_none():
        return {'event_id': event_id, 'status': 'duplicate'}

    db.add(
        GatewaySyncEvent(
            event_id=event_id,
            gateway_id=gateway_id,
            station_id=station_id,
            event_type=event_type,
            direction=SyncDirection.GATEWAY_TO_SERVER,
            payload_json=payload,
            status=SyncStatus.ACKED,
            retry_count=0,
        )
    )
    await db.commit()
    return {'event_id': event_id, 'status': 'accepted'}


async def pickup_confirm(db: AsyncSession, user_id: int, event_id: str, tag_id: str, encrypted_token: str, pickup_binding_id: str):
    event_exist = await db.execute(select(PickupEvent).where(PickupEvent.event_id == event_id))
    existed_event = event_exist.scalar_one_or_none()
    if existed_event:
        parcel = await db.get(Parcel, existed_event.parcel_id)
        return parcel, existed_event, True

    binding_q = await db.execute(select(ParcelTagBinding).where(ParcelTagBinding.pickup_binding_id == pickup_binding_id))
    binding = binding_q.scalar_one_or_none()
    if not binding or binding.status != ParcelTagBindingStatus.ACTIVE:
        raise HTTPException(status_code=400, detail='Invalid binding')

    tag_q = await db.execute(select(Tag).where(Tag.id == binding.tag_id))
    tag = tag_q.scalar_one_or_none()
    if not tag or tag.tag_id != tag_id or tag.encrypted_token != encrypted_token:
        raise HTTPException(status_code=400, detail='Invalid tag credential')

    parcel = await db.get(Parcel, binding.parcel_id)
    if not parcel:
        raise _not_found('parcel')

    if parcel.status == ParcelStatus.PICKED_UP:
        existing_pickup = await db.execute(
            select(PickupEvent).where(PickupEvent.parcel_id == parcel.id, PickupEvent.event_type == PickupEventType.PICKUP_CONFIRMED)
        )
        event = existing_pickup.scalar_one_or_none()
        return parcel, event, True

    parcel.status = ParcelStatus.PICKED_UP
    binding.status = ParcelTagBindingStatus.RELEASED

    pickup_event = PickupEvent(
        event_id=event_id,
        parcel_id=parcel.id,
        user_id=user_id,
        station_id=parcel.station_id,
        gateway_id=None,
        event_type=PickupEventType.PICKUP_CONFIRMED,
        source=EventSource.MINIPROGRAM,
        payload_json={'tag_id': tag_id, 'pickup_binding_id': pickup_binding_id},
    )
    db.add(pickup_event)

    db.add(
        GatewaySyncEvent(
            event_id=uuid.uuid4().hex,
            gateway_id=1,
            station_id=parcel.station_id,
            event_type='PICKUP_CONFIRMED',
            direction=SyncDirection.SERVER_TO_GATEWAY,
            payload_json={'parcel_id': parcel.id, 'status': ParcelStatus.PICKED_UP.value},
            status=SyncStatus.PENDING,
            retry_count=0,
        )
    )

    await db.commit()
    await db.refresh(parcel)
    await db.refresh(pickup_event)
    return parcel, pickup_event, False


async def list_user_pickup_list(db: AsyncSession, user_id: int) -> list[Parcel]:
    result = await db.execute(
        select(Parcel).where(Parcel.receiver_user_id == user_id, Parcel.status == ParcelStatus.WAITING_PICKUP).order_by(Parcel.id.desc())
    )
    return list(result.scalars().all())


async def list_user_pickup_history(db: AsyncSession, user_id: int) -> list[Parcel]:
    result = await db.execute(
        select(Parcel).where(Parcel.receiver_user_id == user_id, Parcel.status == ParcelStatus.PICKED_UP).order_by(Parcel.id.desc())
    )
    return list(result.scalars().all())


async def list_user_notifications(db: AsyncSession, user_id: int) -> list[Notification]:
    result = await db.execute(select(Notification).where(Notification.user_id == user_id).order_by(Notification.id.desc()))
    return list(result.scalars().all())


async def list_notifications(db: AsyncSession) -> list[Notification]:
    result = await db.execute(select(Notification).order_by(Notification.id.desc()).limit(100))
    return list(result.scalars().all())


async def list_sync_events(
    db: AsyncSession,
    direction: SyncDirection | None = None,
    status_value: SyncStatus | None = None,
    event_type: str | None = None,
) -> list[GatewaySyncEvent]:
    query = select(GatewaySyncEvent)
    if direction:
        query = query.where(GatewaySyncEvent.direction == direction)
    if status_value:
        query = query.where(GatewaySyncEvent.status == status_value)
    if event_type:
        query = query.where(GatewaySyncEvent.event_type == event_type)
    result = await db.execute(query.order_by(GatewaySyncEvent.id.desc()).limit(100))
    return list(result.scalars().all())


async def mark_notification_read(db: AsyncSession, notification_id: int) -> Notification:
    notification = await db.get(Notification, notification_id)
    if not notification:
        raise _not_found('notification')
    notification.status = NotificationStatus.READ
    await db.commit()
    await db.refresh(notification)
    return notification
