import uuid
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import (
    EventSource,
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
    TagStatus,
    UserRole,
)
from app.models.models import Gateway, GatewayRegistrationToken, GatewaySyncEvent, Notification, Parcel, ParcelTagBinding, PickupEvent, Station, Tag, User


def _not_found(name: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'{name} not found')


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
    defaults = [
        {'id': 1, 'display_name': 'Server Admin', 'phone': '18800000001', 'role': UserRole.SERVER_ADMIN},
        {'id': 2, 'display_name': 'Demo User', 'phone': '18800000002', 'role': UserRole.USER},
        {'id': 3, 'display_name': 'Station Staff', 'phone': '18800000003', 'role': UserRole.STAFF},
        {'id': 4, 'display_name': 'Gateway Admin', 'phone': '18800000004', 'role': UserRole.GATEWAY_ADMIN},
    ]
    users: list[User] = []
    for item in defaults:
        user = await db.get(User, item['id'])
        if user:
            user.display_name = item['display_name']
            user.phone = item['phone']
            user.role = item['role']
            user.is_active = True
        else:
            user = User(**item, is_active=True)
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
    gateway.status = status_value
    gateway.last_seen_at = datetime.now(timezone.utc)
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

    settings = get_settings()
    gateway_secret = generate_gateway_secret(settings.gateway_secret_bytes)
    gateway = await register_gateway(
        db,
        {'gateway_code': gateway_code, 'station_id': station_id, 'device_secret_hash': gateway_secret, 'status': 'ACTIVE'},
    )
    token_row.status = GatewayRegistrationTokenStatus.USED
    token_row.used_at = now
    await db.commit()
    await db.refresh(gateway)
    return gateway, gateway_secret


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


async def create_tag(db: AsyncSession, data: dict) -> Tag:
    existing = await db.execute(select(Tag).where(Tag.tag_id == data['tag_id']))
    tag = existing.scalar_one_or_none()
    if tag:
        for key, value in data.items():
            setattr(tag, key, value)
    else:
        tag = Tag(**data)
        db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def list_tags(db: AsyncSession) -> list[Tag]:
    result = await db.execute(select(Tag).order_by(Tag.id.desc()))
    return list(result.scalars().all())


async def get_tag_by_pk(db: AsyncSession, tag_pk: int) -> Tag:
    tag = await db.get(Tag, tag_pk)
    if not tag:
        raise _not_found('tag')
    return tag


async def bind_tag_to_parcel(db: AsyncSession, parcel_id: int, tag_code: str, station_id: int) -> ParcelTagBinding:
    parcel = await get_parcel(db, parcel_id)
    tag_result = await db.execute(select(Tag).where(Tag.tag_id == tag_code))
    tag = tag_result.scalar_one_or_none()
    if not tag:
        raise _not_found('tag')

    binding = ParcelTagBinding(
        pickup_binding_id=uuid.uuid4().hex,
        parcel_id=parcel.id,
        tag_id=tag.id,
        station_id=station_id,
        status=ParcelTagBindingStatus.ACTIVE,
    )
    parcel.status = ParcelStatus.WAITING_PICKUP
    db.add(binding)

    if parcel.receiver_user_id:
        db.add(
            Notification(
                user_id=parcel.receiver_user_id,
                parcel_id=parcel.id,
                title='Parcel ready for pickup',
                content=f'Parcel {parcel.parcel_code} is waiting for pickup.',
                type=NotificationType.IN_APP,
                status=NotificationStatus.PENDING,
            )
        )

    sync = GatewaySyncEvent(
        event_id=uuid.uuid4().hex,
        gateway_id=1,
        station_id=station_id,
        event_type='PARCEL_BIND',
        direction=SyncDirection.SERVER_TO_GATEWAY,
        payload_json={'parcel_id': parcel.id, 'tag_id': tag.tag_id, 'pickup_binding_id': binding.pickup_binding_id},
        status=SyncStatus.PENDING,
        retry_count=0,
    )
    db.add(sync)

    await db.commit()
    await db.refresh(binding)
    return binding


async def release_binding(db: AsyncSession, pickup_binding_id: str) -> ParcelTagBinding:
    result = await db.execute(select(ParcelTagBinding).where(ParcelTagBinding.pickup_binding_id == pickup_binding_id))
    binding = result.scalar_one_or_none()
    if not binding:
        raise _not_found('binding')
    binding.status = ParcelTagBindingStatus.RELEASED
    await db.commit()
    await db.refresh(binding)
    return binding


async def report_tag_status(db: AsyncSession, tag_code: str, status_value, battery_level: int | None) -> Tag:
    result = await db.execute(select(Tag).where(Tag.tag_id == tag_code))
    tag = result.scalar_one_or_none()
    if not tag:
        raise _not_found('tag')
    tag.status = status_value
    tag.battery_level = battery_level
    tag.last_seen_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(tag)
    return tag


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
    elif normalized in {'TAG_BOUND', 'TAG_RELEASED', 'TAG_STATUS_REPORT'}:
        await apply_gateway_tag_event(db, station_id, normalized, payload)
    elif normalized in {'PICKUP_CONFIRMED', 'OFFLINE_PICKUP'}:
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
    tag_code = payload.get('tag_id')
    if not tag_code:
        return
    result = await db.execute(select(Tag).where(Tag.tag_id == tag_code))
    tag = result.scalar_one_or_none()
    if not tag:
        tag = Tag(
            tag_id=tag_code,
            encrypted_token=payload.get('encrypted_token', ''),
            station_id=int(payload.get('station_id') or station_id),
            status=TagStatus.ONLINE,
            battery_level=payload.get('battery_level'),
        )
        db.add(tag)
        await db.flush()

    if event_type == 'TAG_STATUS_REPORT':
        tag.status = payload.get('status') or tag.status
        tag.battery_level = payload.get('battery_level')
        tag.last_seen_at = datetime.now(timezone.utc)
        return

    pickup_binding_id = payload.get('pickup_binding_id')
    parcel_code = payload.get('parcel_code')
    if not pickup_binding_id or not parcel_code:
        return
    parcel_result = await db.execute(select(Parcel).where(Parcel.parcel_code == parcel_code))
    parcel = parcel_result.scalar_one_or_none()
    if not parcel:
        return
    binding_result = await db.execute(select(ParcelTagBinding).where(ParcelTagBinding.pickup_binding_id == pickup_binding_id))
    binding = binding_result.scalar_one_or_none()
    if not binding:
        binding = ParcelTagBinding(
            pickup_binding_id=pickup_binding_id,
            parcel_id=parcel.id,
            tag_id=tag.id,
            station_id=parcel.station_id,
            status=ParcelTagBindingStatus.ACTIVE,
        )
        db.add(binding)
    elif event_type == 'TAG_RELEASED':
        binding.status = ParcelTagBindingStatus.RELEASED


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
