from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import get_current_user_dev, verify_gateway_request
from app.db.session import get_db
from app.schemas.schemas import (
    GatewayEventIn,
    GatewayHeartbeatIn,
    GatewayOut,
    GatewayRegisterIn,
    GatewaySyncPullOut,
    HealthOut,
    NotificationOut,
    ParcelCreate,
    ParcelOut,
    ParcelStatusPatch,
    ParcelTagBindingOut,
    PickupConfirmIn,
    PickupEventOut,
    StationCreate,
    StationOut,
    SyncPushItem,
    TagBindIn,
    TagCreate,
    TagOut,
    TagReleaseIn,
    TagStatusReportIn,
    VersionOut,
)
from app.services import services

router = APIRouter()
settings = get_settings()


@router.get('/health', response_model=HealthOut)
async def health() -> HealthOut:
    return HealthOut(status='ok')


@router.get('/version', response_model=VersionOut)
async def version() -> VersionOut:
    return VersionOut(app=settings.app_name, version=settings.app_version)


@router.post('/stations', response_model=StationOut)
async def create_station(payload: StationCreate, _: object = Depends(get_current_user_dev), db: AsyncSession = Depends(get_db)):
    return await services.create_station(db, payload.model_dump())


@router.get('/stations', response_model=list[StationOut])
async def list_stations(db: AsyncSession = Depends(get_db)):
    return await services.list_stations(db)


@router.get('/stations/{station_id}', response_model=StationOut)
async def get_station(station_id: int, db: AsyncSession = Depends(get_db)):
    return await services.get_station(db, station_id)


@router.post('/gateways/register', response_model=GatewayOut)
async def register_gateway(payload: GatewayRegisterIn, db: AsyncSession = Depends(get_db)):
    return await services.register_gateway(db, payload.model_dump())


@router.post('/gateways/heartbeat', response_model=GatewayOut)
async def gateway_heartbeat(payload: GatewayHeartbeatIn, db: AsyncSession = Depends(get_db)):
    return await services.gateway_heartbeat(db, payload.gateway_code, payload.status)


@router.get('/gateways/{gateway_code}/sync/pull', response_model=GatewaySyncPullOut)
async def gateway_pull_sync(gateway_code: str, db: AsyncSession = Depends(get_db)):
    gateway = await services.get_gateway_by_code(db, gateway_code)
    events = await services.gateway_pull_sync(db, gateway.id)
    return GatewaySyncPullOut(events=[{'id': e.id, 'event_id': e.event_id, 'event_type': e.event_type, 'payload_json': e.payload_json} for e in events])


@router.post('/gateways/{gateway_code}/sync/push')
async def gateway_push_sync(gateway_code: str, items: list[SyncPushItem], db: AsyncSession = Depends(get_db)):
    gateway = await services.get_gateway_by_code(db, gateway_code)
    result = await services.gateway_push_sync(db, gateway.id, station_id=gateway.station_id, items=[i.model_dump() for i in items])
    return result


@router.post('/gateways/{gateway_code}/events')
async def gateway_events(
    gateway_code: str,
    payload: GatewayEventIn,
    request: Request,
    x_gateway_code: str | None = Header(default=None, alias='X-Gateway-Code'),
    x_gateway_signature: str | None = Header(default=None, alias='X-Gateway-Signature'),
    db: AsyncSession = Depends(get_db),
):
    gateway = await verify_gateway_request(
        payload=(await request.body()),
        x_gateway_code=x_gateway_code,
        x_gateway_signature=x_gateway_signature,
        db=db,
        fallback_secret=settings.default_gateway_secret,
    )
    if gateway.gateway_code != gateway_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='gateway code mismatch between path and headers')
    return await services.create_gateway_event(
        db,
        gateway_id=gateway.id,
        station_id=gateway.station_id,
        event_id=payload.event_id,
        event_type=payload.event_type,
        payload=payload.payload_json,
    )


@router.post('/parcels', response_model=ParcelOut)
async def create_parcel(payload: ParcelCreate, current_user=Depends(get_current_user_dev), db: AsyncSession = Depends(get_db)):
    return await services.create_parcel(db, payload.model_dump(), admin_id=current_user.id)


@router.get('/parcels', response_model=list[ParcelOut])
async def list_parcels(db: AsyncSession = Depends(get_db)):
    return await services.list_parcels(db)


@router.get('/parcels/{parcel_id}', response_model=ParcelOut)
async def get_parcel(parcel_id: int, db: AsyncSession = Depends(get_db)):
    return await services.get_parcel(db, parcel_id)


@router.patch('/parcels/{parcel_id}/status', response_model=ParcelOut)
async def patch_parcel_status(parcel_id: int, payload: ParcelStatusPatch, _: object = Depends(get_current_user_dev), db: AsyncSession = Depends(get_db)):
    return await services.patch_parcel_status(db, parcel_id, payload.status)


@router.post('/tags', response_model=TagOut)
async def create_tag(payload: TagCreate, _: object = Depends(get_current_user_dev), db: AsyncSession = Depends(get_db)):
    return await services.create_tag(db, payload.model_dump())


@router.get('/tags', response_model=list[TagOut])
async def list_tags(db: AsyncSession = Depends(get_db)):
    return await services.list_tags(db)


@router.get('/tags/{tag_id}', response_model=TagOut)
async def get_tag(tag_id: int, db: AsyncSession = Depends(get_db)):
    return await services.get_tag_by_pk(db, tag_id)


@router.post('/tags/bind', response_model=ParcelTagBindingOut)
async def bind_tag(payload: TagBindIn, _: object = Depends(get_current_user_dev), db: AsyncSession = Depends(get_db)):
    return await services.bind_tag_to_parcel(db, payload.parcel_id, payload.tag_id, payload.station_id)


@router.post('/tags/release', response_model=ParcelTagBindingOut)
async def release_tag(payload: TagReleaseIn, _: object = Depends(get_current_user_dev), db: AsyncSession = Depends(get_db)):
    return await services.release_binding(db, payload.pickup_binding_id)


@router.post('/tags/status-report', response_model=TagOut)
async def tag_status_report(payload: TagStatusReportIn, db: AsyncSession = Depends(get_db)):
    return await services.report_tag_status(db, payload.tag_id, payload.status, payload.battery_level)


@router.post('/pickup/confirm', response_model=PickupEventOut)
async def pickup_confirm(payload: PickupConfirmIn, current_user=Depends(get_current_user_dev), db: AsyncSession = Depends(get_db)):
    _, event, _ = await services.pickup_confirm(
        db,
        user_id=current_user.id,
        event_id=payload.event_id,
        tag_id=payload.tag_id,
        encrypted_token=payload.encrypted_token,
        pickup_binding_id=payload.pickup_binding_id,
    )
    return event


@router.get('/users/{user_id}/pickup-list', response_model=list[ParcelOut])
async def user_pickup_list(user_id: int, db: AsyncSession = Depends(get_db)):
    return await services.list_user_pickup_list(db, user_id)


@router.get('/users/{user_id}/pickup-history', response_model=list[ParcelOut])
async def user_pickup_history(user_id: int, db: AsyncSession = Depends(get_db)):
    return await services.list_user_pickup_history(db, user_id)


@router.get('/users/{user_id}/notifications', response_model=list[NotificationOut])
async def user_notifications(user_id: int, db: AsyncSession = Depends(get_db)):
    return await services.list_user_notifications(db, user_id)


@router.post('/notifications/{notification_id}/read', response_model=NotificationOut)
async def read_notification(notification_id: int, db: AsyncSession = Depends(get_db)):
    return await services.mark_notification_read(db, notification_id)

