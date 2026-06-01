import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    EventSource,
    NotificationStatus,
    NotificationType,
    ParcelStatus,
    ParcelTagBindingStatus,
    PickupEventType,
    SyncDirection,
    SyncStatus,
)
from app.models.models import Gateway, GatewaySyncEvent, Notification, Parcel, ParcelTagBinding, PickupEvent, Station, Tag, User


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


async def create_parcel(db: AsyncSession, data: dict, admin_id: int) -> Parcel:
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
        accepted += 1
    await db.commit()
    return {'accepted': accepted, 'duplicate': duplicate}


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


async def mark_notification_read(db: AsyncSession, notification_id: int) -> Notification:
    notification = await db.get(Notification, notification_id)
    if not notification:
        raise _not_found('notification')
    notification.status = NotificationStatus.READ
    await db.commit()
    await db.refresh(notification)
    return notification
