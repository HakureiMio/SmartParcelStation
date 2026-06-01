from enum import Enum


class UserRole(str, Enum):
    USER = 'USER'
    LOCAL_ADMIN = 'LOCAL_ADMIN'
    SERVER_ADMIN = 'SERVER_ADMIN'


class ParcelStatus(str, Enum):
    CREATED = 'CREATED'
    STORED = 'STORED'
    WAITING_PICKUP = 'WAITING_PICKUP'
    PICKED_UP = 'PICKED_UP'
    EXCEPTION = 'EXCEPTION'
    CANCELLED = 'CANCELLED'


class TagStatus(str, Enum):
    IDLE = 'IDLE'
    ONLINE = 'ONLINE'
    OFFLINE = 'OFFLINE'
    RUNNING = 'RUNNING'
    LOW_BATTERY = 'LOW_BATTERY'
    ERROR = 'ERROR'
    TAMPER = 'TAMPER'
    DISABLED = 'DISABLED'


class ParcelTagBindingStatus(str, Enum):
    ACTIVE = 'ACTIVE'
    RELEASED = 'RELEASED'
    CANCELLED = 'CANCELLED'


class PickupEventType(str, Enum):
    NOTIFIED = 'NOTIFIED'
    NFC_ACCESS = 'NFC_ACCESS'
    TAG_WAKE = 'TAG_WAKE'
    PICKUP_CONFIRMED = 'PICKUP_CONFIRMED'
    PICKUP_SYNCED = 'PICKUP_SYNCED'
    OFFLINE_PICKUP = 'OFFLINE_PICKUP'


class EventSource(str, Enum):
    SERVER = 'SERVER'
    GATEWAY = 'GATEWAY'
    MINIPROGRAM = 'MINIPROGRAM'


class SyncDirection(str, Enum):
    GATEWAY_TO_SERVER = 'GATEWAY_TO_SERVER'
    SERVER_TO_GATEWAY = 'SERVER_TO_GATEWAY'


class SyncStatus(str, Enum):
    PENDING = 'PENDING'
    SENT = 'SENT'
    ACKED = 'ACKED'
    FAILED = 'FAILED'


class NotificationType(str, Enum):
    IN_APP = 'IN_APP'
    WECHAT_SUBSCRIBE = 'WECHAT_SUBSCRIBE'


class NotificationStatus(str, Enum):
    PENDING = 'PENDING'
    SENT = 'SENT'
    READ = 'READ'
    FAILED = 'FAILED'
