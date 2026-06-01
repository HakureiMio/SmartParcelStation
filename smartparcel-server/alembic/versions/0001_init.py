"""init core tables

Revision ID: 0001_init
Revises:
Create Date: 2026-05-28 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001_init'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


user_role = sa.Enum('USER', 'LOCAL_ADMIN', 'SERVER_ADMIN', name='userrole')
parcel_status = sa.Enum('CREATED', 'STORED', 'WAITING_PICKUP', 'PICKED_UP', 'EXCEPTION', 'CANCELLED', name='parcelstatus')
tag_status = sa.Enum('IDLE', 'ONLINE', 'OFFLINE', 'RUNNING', 'LOW_BATTERY', 'ERROR', 'TAMPER', 'DISABLED', name='tagstatus')
binding_status = sa.Enum('ACTIVE', 'RELEASED', 'CANCELLED', name='parceltagbindingstatus')
pickup_event_type = sa.Enum(
    'NOTIFIED', 'NFC_ACCESS', 'TAG_WAKE', 'PICKUP_CONFIRMED', 'PICKUP_SYNCED', 'OFFLINE_PICKUP', name='pickupeventtype'
)
event_source = sa.Enum('SERVER', 'GATEWAY', 'MINIPROGRAM', name='eventsource')
sync_direction = sa.Enum('GATEWAY_TO_SERVER', 'SERVER_TO_GATEWAY', name='syncdirection')
sync_status = sa.Enum('PENDING', 'SENT', 'ACKED', 'FAILED', name='syncstatus')
notification_type = sa.Enum('IN_APP', 'WECHAT_SUBSCRIBE', name='notificationtype')
notification_status = sa.Enum('PENDING', 'SENT', 'READ', 'FAILED', name='notificationstatus')


def upgrade() -> None:
    op.create_table(
        'stations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('station_code', sa.String(length=64), nullable=False, unique=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('openid', sa.String(length=128), nullable=True, unique=True),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('display_name', sa.String(length=128), nullable=False),
        sa.Column('role', user_role, nullable=False),
        sa.Column('station_id', sa.Integer(), sa.ForeignKey('stations.id'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_users_phone', 'users', ['phone'])

    op.create_table(
        'gateways',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('gateway_code', sa.String(length=64), nullable=False, unique=True),
        sa.Column('station_id', sa.Integer(), sa.ForeignKey('stations.id'), nullable=False),
        sa.Column('device_secret_hash', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'parcels',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('parcel_code', sa.String(length=128), nullable=False, unique=True),
        sa.Column('pickup_code', sa.String(length=64), nullable=True),
        sa.Column('receiver_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('receiver_phone', sa.String(length=32), nullable=True),
        sa.Column('station_id', sa.Integer(), sa.ForeignKey('stations.id'), nullable=False),
        sa.Column('status', parcel_status, nullable=False),
        sa.Column('created_by_admin_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tag_id', sa.String(length=128), nullable=False, unique=True),
        sa.Column('encrypted_token', sa.String(length=255), nullable=False),
        sa.Column('station_id', sa.Integer(), sa.ForeignKey('stations.id'), nullable=False),
        sa.Column('status', tag_status, nullable=False),
        sa.Column('battery_level', sa.Integer(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'parcel_tag_bindings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('pickup_binding_id', sa.String(length=64), nullable=False, unique=True),
        sa.Column('parcel_id', sa.Integer(), sa.ForeignKey('parcels.id'), nullable=False),
        sa.Column('tag_id', sa.Integer(), sa.ForeignKey('tags.id'), nullable=False),
        sa.Column('station_id', sa.Integer(), sa.ForeignKey('stations.id'), nullable=False),
        sa.Column('status', binding_status, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'pickup_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_id', sa.String(length=128), nullable=False, unique=True),
        sa.Column('parcel_id', sa.Integer(), sa.ForeignKey('parcels.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('station_id', sa.Integer(), sa.ForeignKey('stations.id'), nullable=False),
        sa.Column('gateway_id', sa.Integer(), sa.ForeignKey('gateways.id'), nullable=True),
        sa.Column('event_type', pickup_event_type, nullable=False),
        sa.Column('source', event_source, nullable=False),
        sa.Column('payload_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'gateway_sync_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_id', sa.String(length=128), nullable=False, unique=True),
        sa.Column('gateway_id', sa.Integer(), sa.ForeignKey('gateways.id'), nullable=False),
        sa.Column('station_id', sa.Integer(), sa.ForeignKey('stations.id'), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('direction', sync_direction, nullable=False),
        sa.Column('payload_json', sa.JSON(), nullable=False),
        sa.Column('status', sync_status, nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('parcel_id', sa.Integer(), sa.ForeignKey('parcels.id'), nullable=True),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('type', notification_type, nullable=False),
        sa.Column('status', notification_status, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('notifications')
    op.drop_table('gateway_sync_events')
    op.drop_table('pickup_events')
    op.drop_table('parcel_tag_bindings')
    op.drop_table('tags')
    op.drop_table('parcels')
    op.drop_table('gateways')
    op.drop_index('ix_users_phone', table_name='users')
    op.drop_table('users')
    op.drop_table('stations')

    notification_status.drop(op.get_bind(), checkfirst=True)
    notification_type.drop(op.get_bind(), checkfirst=True)
    sync_status.drop(op.get_bind(), checkfirst=True)
    sync_direction.drop(op.get_bind(), checkfirst=True)
    event_source.drop(op.get_bind(), checkfirst=True)
    pickup_event_type.drop(op.get_bind(), checkfirst=True)
    binding_status.drop(op.get_bind(), checkfirst=True)
    tag_status.drop(op.get_bind(), checkfirst=True)
    parcel_status.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)
