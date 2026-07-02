from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    AccessCredentialStatus,
    AccessCredentialType,
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
    TagStatus,
    UserRole,
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    openid: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER, nullable=False)
    station_id: Mapped[int | None] = mapped_column(ForeignKey('stations.id'), nullable=True)
    pickup_level: Mapped[str] = mapped_column(String(32), default='NORMAL', nullable=False)
    trusted_pickup_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UserAccessCredential(Base, TimestampMixin):
    __tablename__ = 'user_access_credentials'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), nullable=False, index=True)
    credential_type: Mapped[AccessCredentialType] = mapped_column(Enum(AccessCredentialType), nullable=False)
    credential_value: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    credential_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[AccessCredentialStatus] = mapped_column(
        Enum(AccessCredentialStatus), default=AccessCredentialStatus.ACTIVE, nullable=False
    )
    replaced_by_id: Mapped[int | None] = mapped_column(ForeignKey('user_access_credentials.id'), nullable=True)
    lost_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)


class Station(Base, TimestampMixin):
    __tablename__ = 'stations'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default='ACTIVE', nullable=False)


class Gateway(Base, TimestampMixin):
    __tablename__ = 'gateways'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gateway_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), nullable=False)
    # TODO: rename device_secret_hash to gateway_secret_encrypted or store encrypted secret.
    # Currently stores gateway_secret plaintext used for HMAC verification.
    device_secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default='ACTIVE', nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gateway_factory_code: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    gateway_device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gateway_serial: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GatewayNonce(Base):
    __tablename__ = 'gateway_nonces'
    __table_args__ = (UniqueConstraint('gateway_id', 'nonce', name='uq_gateway_nonces_gateway_nonce'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gateway_id: Mapped[int] = mapped_column(ForeignKey('gateways.id'), nullable=False)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    timestamp: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GatewayRegistrationToken(Base, TimestampMixin):
    __tablename__ = 'gateway_registration_tokens'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    gateway_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[GatewayRegistrationTokenStatus] = mapped_column(
        Enum(GatewayRegistrationTokenStatus), default=GatewayRegistrationTokenStatus.PENDING, nullable=False
    )
    created_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    gateway_factory_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    gateway_device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gateway_serial: Mapped[str | None] = mapped_column(String(128), nullable=True)


class Parcel(Base, TimestampMixin):
    __tablename__ = 'parcels'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parcel_code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    pickup_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    receiver_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    receiver_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    receiver_name_masked: Mapped[str | None] = mapped_column(String(128), nullable=True)
    shelf_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), nullable=False)
    status: Mapped[ParcelStatus] = mapped_column(Enum(ParcelStatus), default=ParcelStatus.CREATED, nullable=False)
    origin: Mapped[ParcelOrigin] = mapped_column(Enum(ParcelOrigin), default=ParcelOrigin.SERVER_MANUAL, nullable=False)
    sync_status: Mapped[ParcelSyncStatus] = mapped_column(Enum(ParcelSyncStatus), default=ParcelSyncStatus.SERVER_ONLY, nullable=False)
    created_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)


class Tag(Base, TimestampMixin):
    __tablename__ = 'tags'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    encrypted_token: Mapped[str] = mapped_column(String(255), nullable=False)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), nullable=False)
    status: Mapped[TagStatus] = mapped_column(Enum(TagStatus), default=TagStatus.IDLE, nullable=False)
    battery_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ParcelTagBinding(Base, TimestampMixin):
    __tablename__ = 'parcel_tag_bindings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pickup_binding_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    parcel_id: Mapped[int] = mapped_column(ForeignKey('parcels.id'), nullable=False)
    tag_id: Mapped[int] = mapped_column(ForeignKey('tags.id'), nullable=False)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), nullable=False)
    status: Mapped[ParcelTagBindingStatus] = mapped_column(
        Enum(ParcelTagBindingStatus), default=ParcelTagBindingStatus.ACTIVE, nullable=False
    )


class PickupEvent(Base):
    __tablename__ = 'pickup_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    parcel_id: Mapped[int] = mapped_column(ForeignKey('parcels.id'), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), nullable=False)
    gateway_id: Mapped[int | None] = mapped_column(ForeignKey('gateways.id'), nullable=True)
    event_type: Mapped[PickupEventType] = mapped_column(Enum(PickupEventType), nullable=False)
    source: Mapped[EventSource] = mapped_column(Enum(EventSource), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GatewaySyncEvent(Base, TimestampMixin):
    __tablename__ = 'gateway_sync_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    gateway_id: Mapped[int] = mapped_column(ForeignKey('gateways.id'), nullable=False)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[SyncDirection] = mapped_column(Enum(SyncDirection), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[SyncStatus] = mapped_column(Enum(SyncStatus), default=SyncStatus.PENDING, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Notification(Base, TimestampMixin):
    __tablename__ = 'notifications'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    parcel_id: Mapped[int | None] = mapped_column(ForeignKey('parcels.id'), nullable=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType), default=NotificationType.IN_APP, nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus), default=NotificationStatus.PENDING, nullable=False
    )


class SecurityAuditEvent(Base):
    """Lightweight security audit log for gateway auth failures and other security events.

    Fields are deliberately kept minimal — no secrets, no full request bodies.
    """

    __tablename__ = 'security_audit_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    gateway_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    request_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GatewayFactoryDevice(Base, TimestampMixin):
    """Physical gateway device identified by unique factory code.

    A factory code identifies a specific hardware unit. It is NOT a secret or credential.
    Only gateways that complete bootstrap + HMAC heartbeat become trusted (ONLINE).
    """

    __tablename__ = 'gateway_factory_devices'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gateway_factory_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    gateway_device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gateway_serial: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gateway_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    station_id: Mapped[int | None] = mapped_column(ForeignKey('stations.id'), nullable=True)
    bound_gateway_id: Mapped[int | None] = mapped_column(ForeignKey('gateways.id'), nullable=True)
    status: Mapped[GatewayFactoryDeviceStatus] = mapped_column(
        Enum(GatewayFactoryDeviceStatus), default=GatewayFactoryDeviceStatus.UNKNOWN_SEEN, nullable=False
    )
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bind_requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    bind_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disabled_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
