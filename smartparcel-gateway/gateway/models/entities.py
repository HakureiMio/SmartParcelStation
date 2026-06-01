from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from gateway.db.base import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class ParcelStatus(str, enum.Enum):
    CREATED = "CREATED"
    STORED = "STORED"
    WAITING_PICKUP = "WAITING_PICKUP"
    PICKED_UP = "PICKED_UP"
    EXCEPTION = "EXCEPTION"
    CANCELLED = "CANCELLED"


class TagStatus(str, enum.Enum):
    IDLE = "IDLE"
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    RUNNING = "RUNNING"
    LOW_BATTERY = "LOW_BATTERY"
    ERROR = "ERROR"
    TAMPER = "TAMPER"
    DISABLED = "DISABLED"


class BindingStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    CANCELLED = "CANCELLED"


class CredentialType(str, enum.Enum):
    CARD_UID = "CARD_UID"
    PHONE_HCE = "PHONE_HCE"
    TOKEN = "TOKEN"


class CredentialStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    EXPIRED = "EXPIRED"


class PickupEventType(str, enum.Enum):
    NFC_ACCESS = "NFC_ACCESS"
    TAG_WAKE = "TAG_WAKE"
    PICKUP_CONFIRMED = "PICKUP_CONFIRMED"
    OFFLINE_PICKUP = "OFFLINE_PICKUP"


class EventSource(str, enum.Enum):
    GATEWAY = "GATEWAY"
    SERVER = "SERVER"


class EventSyncStatus(str, enum.Enum):
    LOCAL_ONLY = "LOCAL_ONLY"
    PENDING_UPLOAD = "PENDING_UPLOAD"
    UPLOADED = "UPLOADED"
    FAILED = "FAILED"


class TaskType(str, enum.Enum):
    SYNC_PULL = "SYNC_PULL"
    SYNC_PUSH = "SYNC_PUSH"
    TAG_WAKE = "TAG_WAKE"
    TAG_STOP = "TAG_STOP"
    TAG_STATUS_QUERY = "TAG_STATUS_QUERY"
    NFC_ACCESS_CHECK = "NFC_ACCESS_CHECK"
    SERVER_COMMAND = "SERVER_COMMAND"


class TaskTargetType(str, enum.Enum):
    SERVER = "SERVER"
    TAG = "TAG"
    NFC = "NFC"
    LOCAL = "LOCAL"


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SyncDirection(str, enum.Enum):
    UPLOAD = "UPLOAD"
    DOWNLOAD = "DOWNLOAD"


class SyncQueueStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    ACKED = "ACKED"
    FAILED = "FAILED"


class LocalParcel(Base):
    __tablename__ = "local_parcels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_parcel_id: Mapped[str] = mapped_column(String(64), index=True)
    parcel_code: Mapped[str] = mapped_column(String(64), index=True)
    pickup_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    receiver_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    receiver_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    station_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[ParcelStatus] = mapped_column(Enum(ParcelStatus), default=ParcelStatus.CREATED)
    server_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    local_updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (UniqueConstraint("server_parcel_id", name="uq_local_parcels_server_parcel_id"),)


class LocalTag(Base):
    __tablename__ = "local_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_tag_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tag_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    encrypted_token: Mapped[str] = mapped_column(String(256))
    station_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[TagStatus] = mapped_column(Enum(TagStatus), default=TagStatus.IDLE)
    battery_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LocalParcelTagBinding(Base):
    __tablename__ = "local_parcel_tag_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_binding_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pickup_binding_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    server_parcel_id: Mapped[str] = mapped_column(String(64), index=True)
    tag_id: Mapped[str] = mapped_column(String(64), index=True)
    station_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[BindingStatus] = mapped_column(Enum(BindingStatus), default=BindingStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LocalNfcCredential(Base):
    __tablename__ = "local_nfc_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    credential_type: Mapped[CredentialType] = mapped_column(Enum(CredentialType))
    credential_value: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    station_id: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[CredentialStatus] = mapped_column(Enum(CredentialStatus), default=CredentialStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LocalPickupEvent(Base):
    __tablename__ = "local_pickup_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    server_parcel_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    station_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[PickupEventType] = mapped_column(Enum(PickupEventType))
    source: Mapped[EventSource] = mapped_column(Enum(EventSource))
    payload_json: Mapped[str] = mapped_column(Text)
    sync_status: Mapped[EventSyncStatus] = mapped_column(Enum(EventSyncStatus), default=EventSyncStatus.PENDING_UPLOAD)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class GatewayTask(Base):
    __tablename__ = "gateway_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType))
    target_type: Mapped[TaskTargetType] = mapped_column(Enum(TaskTargetType))
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SyncQueue(Base):
    __tablename__ = "sync_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    direction: Mapped[SyncDirection] = mapped_column(Enum(SyncDirection))
    payload_json: Mapped[str] = mapped_column(Text)
    status: Mapped[SyncQueueStatus] = mapped_column(Enum(SyncQueueStatus), default=SyncQueueStatus.PENDING)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
