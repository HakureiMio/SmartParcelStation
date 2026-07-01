from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    AccessCredentialStatus,
    AccessCredentialType,
    EventSource,
    GatewayFactoryDeviceStatus,
    GateAuthMethod,
    GatewayRegistrationTokenStatus,
    NotificationStatus,
    NotificationType,
    ParcelOrigin,
    ParcelStatus,
    ParcelSyncStatus,
    PickupEventType,
    SyncDirection,
    SyncStatus,
    UserRole,
)


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthOut(BaseModel):
    status: str


class VersionOut(BaseModel):
    app: str
    version: str


class AuthLoginIn(BaseModel):
    role: str
    username: str
    password: str


class AuthSessionOut(BaseModel):
    token: str
    user_id: str
    role: str
    display_name: str
    station_id: str | None = None


class AuthPlaceholderIn(BaseModel):
    role: str | None = None
    username: str | None = None
    phone: str | None = None


class AuthPlaceholderOut(BaseModel):
    ok: bool
    message: str


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


class GatewayRegistrationTokenCreate(BaseModel):
    gateway_code: str
    station_id: int
    ttl_seconds: int | None = None


class GatewayRegistrationTokenCreateOut(BaseModel):
    id: int
    token_id: str
    gateway_code: str
    station_id: int
    registration_token: str
    expires_at: datetime
    message: str


class GatewayRegistrationTokenOut(ORMBase):
    id: int
    token_id: str
    gateway_code: str
    station_id: int
    status: GatewayRegistrationTokenStatus
    expires_at: datetime
    used_at: datetime | None
    created_by_admin_id: int | None
    created_at: datetime
    updated_at: datetime


class GatewayBootstrapActivateIn(BaseModel):
    gateway_code: str
    station_id: int
    registration_token: str
    device_info: dict[str, Any] = Field(default_factory=dict)


class GatewayBootstrapActivateOut(BaseModel):
    gateway_code: str
    station_id: int
    gateway_secret: str
    server_base_url: str
    message: str


class UserCreate(BaseModel):
    display_name: str
    phone: str | None = None
    openid: str | None = None
    role: UserRole = UserRole.USER
    station_id: int | None = None
    pickup_level: str = 'NORMAL'
    trusted_pickup_enabled: bool = False
    is_active: bool = True


class UserPatch(BaseModel):
    display_name: str | None = None
    phone: str | None = None
    role: UserRole | None = None
    station_id: int | None = None
    pickup_level: str | None = None
    trusted_pickup_enabled: bool | None = None
    is_active: bool | None = None


class UserOut(ORMBase):
    id: int
    openid: str | None
    phone: str | None
    display_name: str
    role: UserRole
    station_id: int | None
    pickup_level: str
    trusted_pickup_enabled: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ParcelCreate(BaseModel):
    parcel_code: str
    pickup_code: str | None = None
    receiver_user_id: int | None = None
    receiver_phone: str | None = None
    receiver_name_masked: str | None = None
    station_id: int
    status: ParcelStatus = ParcelStatus.PRE_REGISTERED
    origin: ParcelOrigin = ParcelOrigin.SERVER_MANUAL
    sync_status: ParcelSyncStatus = ParcelSyncStatus.SERVER_ONLY

    @field_validator('parcel_code')
    @classmethod
    def validate_parcel_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('parcel_code is required')
        return normalized


class ParcelStatusPatch(BaseModel):
    status: ParcelStatus


class ParcelOut(ORMBase):
    id: int
    parcel_code: str
    pickup_code: str | None
    receiver_user_id: int | None
    receiver_phone: str | None
    receiver_name_masked: str | None
    station_id: int
    status: ParcelStatus
    origin: ParcelOrigin
    sync_status: ParcelSyncStatus
    created_by_admin_id: int | None
    created_at: datetime
    updated_at: datetime


class ParcelQueryOut(BaseModel):
    id: int
    parcel_code: str
    pickup_code: str | None
    receiver_user_id: int | None
    receiver_phone_masked: str | None
    receiver_name_masked: str | None
    station_id: int
    status: ParcelStatus
    origin: ParcelOrigin
    sync_status: ParcelSyncStatus


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


class AccessCredentialBindIn(BaseModel):
    station_id: int
    credential_type: AccessCredentialType = AccessCredentialType.CARD_UID
    credential_value: str = Field(min_length=1, max_length=255)
    reason: str | None = Field(default=None, max_length=255)

    @field_validator('credential_value')
    @classmethod
    def normalize_credential_value(cls, value: str) -> str:
        return value.strip().upper()


class AccessCredentialOut(ORMBase):
    id: int
    user_id: int
    station_id: int
    credential_type: AccessCredentialType
    credential_value: str
    status: AccessCredentialStatus
    replaced_by_id: int | None
    lost_reported_at: datetime | None
    replaced_at: datetime | None
    disabled_at: datetime | None
    reason: str | None
    created_at: datetime
    updated_at: datetime


class AccessCredentialDisableIn(BaseModel):
    reason: str = Field(default='DISABLED_BY_STAFF', max_length=255)


class AccessCredentialReportLostIn(BaseModel):
    card_id: int
    reason: str = Field(default='USER_REPORTED_LOST', max_length=255)


class CardBindOut(BaseModel):
    ok: bool = True
    user_id: int
    new_card: AccessCredentialOut
    replaced_card: AccessCredentialOut | None = None


class GateNfcConfirmIn(BaseModel):
    auth_method: GateAuthMethod
    gateway_code: str = Field(pattern=r'^[A-Za-z0-9_-]{2,64}$')
    reader_id: str = Field(pattern=r'^[A-Za-z0-9_-]{2,64}$')
    station_id: int
    gate_nfc_tag_id: str = Field(min_length=1, max_length=128)


class GateQrConfirmIn(BaseModel):
    auth_method: GateAuthMethod
    gateway_code: str = Field(pattern=r'^[A-Za-z0-9_-]{2,64}$')
    reader_id: str = Field(pattern=r'^[A-Za-z0-9_-]{2,64}$')
    station_id: int
    session_id: str = Field(min_length=1, max_length=128)
    nonce: str = Field(min_length=1, max_length=128)
    expires_at: int
    signature: str = Field(min_length=1, max_length=512)


class GateAuthConfirmOut(BaseModel):
    ok: bool = True
    request_id: str
    status: str = 'PENDING_GATEWAY_DECISION'
    message: str = '认证已提交，请查看门禁屏幕'


class DemoDataOut(BaseModel):
    ok: bool = True
    station_id: int
    staff_username: str
    user_username: str
    credential_values: list[str]
    parcel_ids: list[int]
    gateway_code: str | None = None


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


# ── Gateway Provisioning ──

class ProvisioningPrepareIn(BaseModel):
    gateway_factory_code: str
    gateway_device_id: str | None = None
    gateway_serial: str | None = None
    station_id: int
    requested_gateway_code: str | None = None


class ProvisioningPrepareOut(BaseModel):
    ok: bool = True
    server_base_url: str
    gateway_code: str
    station_id: str
    gateway_factory_code: str
    registration_token: str
    mqtt_host: str | None = None
    mqtt_port: int | None = None
    mqtt_tls_enabled: bool = False
    config_version: int = 1
    expires_at: datetime


class ProvisioningConfirmIn(BaseModel):
    gateway_factory_code: str
    gateway_code: str
    station_id: int


class ProvisioningConfirmOut(BaseModel):
    ok: bool
    binding_status: str
    gateway_online: bool | None = None
    gateway_code: str | None = None
    station_id: str | None = None
    gateway_factory_code: str | None = None
    last_seen_at: datetime | None = None
    message: str


class GatewayFactoryDeviceOut(ORMBase):
    id: int
    gateway_factory_code: str
    gateway_device_id: str | None
    gateway_serial: str | None
    gateway_code: str | None
    station_id: int | None
    bound_gateway_id: int | None
    status: GatewayFactoryDeviceStatus
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    bind_requested_by_user_id: int | None
    bind_requested_at: datetime | None
    bound_at: datetime | None
    disabled_reason: str | None
    created_at: datetime


class GatewayOutExtended(GatewayOut):
    gateway_factory_code: str | None = None
    gateway_device_id: str | None = None
    gateway_serial: str | None = None
    bound_at: datetime | None = None
