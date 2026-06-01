from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    EventSource,
    NotificationStatus,
    NotificationType,
    ParcelStatus,
    ParcelTagBindingStatus,
    PickupEventType,
    SyncDirection,
    SyncStatus,
    TagStatus,
    UserRole,
)


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthOut(BaseModel):
    status: str


class VersionOut(BaseModel):
    app: str
    version: str


class StationCreate(BaseModel):
    station_code: str
    name: str
    address: str
    status: str = 'ACTIVE'


class StationOut(ORMBase):
    id: int
    station_code: str
    name: str
    address: str
    status: str
    created_at: datetime
    updated_at: datetime


class GatewayRegisterIn(BaseModel):
    gateway_code: str
    station_id: int
    device_secret_hash: str
    status: str = 'ACTIVE'


class GatewayHeartbeatIn(BaseModel):
    gateway_code: str
    status: str = 'ONLINE'


class GatewayOut(ORMBase):
    id: int
    gateway_code: str
    station_id: int
    status: str
    last_seen_at: datetime | None


class ParcelCreate(BaseModel):
    parcel_code: str
    pickup_code: str | None = None
    receiver_user_id: int | None = None
    receiver_phone: str | None = None
    station_id: int


class ParcelStatusPatch(BaseModel):
    status: ParcelStatus


class ParcelOut(ORMBase):
    id: int
    parcel_code: str
    pickup_code: str | None
    receiver_user_id: int | None
    receiver_phone: str | None
    station_id: int
    status: ParcelStatus
    created_by_admin_id: int
    created_at: datetime
    updated_at: datetime


class TagCreate(BaseModel):
    tag_id: str
    encrypted_token: str
    station_id: int
    status: TagStatus = TagStatus.IDLE


class TagOut(ORMBase):
    id: int
    tag_id: str
    encrypted_token: str
    station_id: int
    status: TagStatus
    battery_level: int | None
    last_seen_at: datetime | None


class TagBindIn(BaseModel):
    parcel_id: int
    tag_id: str
    station_id: int


class TagReleaseIn(BaseModel):
    pickup_binding_id: str


class TagStatusReportIn(BaseModel):
    tag_id: str
    status: TagStatus
    battery_level: int | None = None


class ParcelTagBindingOut(ORMBase):
    id: int
    pickup_binding_id: str
    parcel_id: int
    tag_id: int
    station_id: int
    status: ParcelTagBindingStatus
    created_at: datetime
    updated_at: datetime


class SyncPushItem(BaseModel):
    event_id: str
    event_type: str
    payload_json: dict[str, Any] = Field(default_factory=dict)


class GatewaySyncPullOut(BaseModel):
    events: list[dict[str, Any]]


class GatewayEventIn(BaseModel):
    event_id: str
    event_type: str
    payload_json: dict[str, Any] = Field(default_factory=dict)


class PickupConfirmIn(BaseModel):
    event_id: str
    tag_id: str
    encrypted_token: str
    pickup_binding_id: str


class PickupEventOut(ORMBase):
    id: int
    event_id: str
    parcel_id: int
    user_id: int | None
    station_id: int
    gateway_id: int | None
    event_type: PickupEventType
    source: EventSource
    payload_json: dict[str, Any]
    created_at: datetime


class NotificationOut(ORMBase):
    id: int
    user_id: int
    parcel_id: int | None
    title: str
    content: str
    type: NotificationType
    status: NotificationStatus
    created_at: datetime
    updated_at: datetime


class GatewaySyncEventOut(ORMBase):
    id: int
    event_id: str
    gateway_id: int
    station_id: int
    event_type: str
    direction: SyncDirection
    payload_json: dict[str, Any]
    status: SyncStatus
    retry_count: int
    created_at: datetime
    updated_at: datetime
