"""sps stage a flow fields

Revision ID: 0002_sps_stage_a_flow
Revises: 0001_init
Create Date: 2026-06-02 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002_sps_stage_a_flow'
down_revision: Union[str, None] = '0001_init'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


parcel_origin = sa.Enum('EXPRESS_COMPANY', 'SERVER_MANUAL', 'GATEWAY_INBOUND', 'GATEWAY_CORRECTION', name='parcelorigin')
parcel_sync_status = sa.Enum('SERVER_ONLY', 'LOCAL_ONLY', 'SYNC_PENDING', 'SYNCED', 'MERGED', 'CONFLICT', name='parcelsyncstatus')


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'mysql':
        op.execute(
            "ALTER TABLE users MODIFY role ENUM('USER','STAFF','LOCAL_ADMIN','GATEWAY_ADMIN','SERVER_ADMIN') NOT NULL"
        )
        op.execute(
            "ALTER TABLE parcels MODIFY status ENUM('CREATED','PRE_REGISTERED','ARRIVED_AT_STATION','STORED','WAITING_PICKUP','FINDING','PICKUP_VERIFYING','PICKED_UP','EXCEPTION','CANCELLED') NOT NULL"
        )

    op.add_column('users', sa.Column('pickup_level', sa.String(length=32), nullable=False, server_default='NORMAL'))
    op.add_column('users', sa.Column('trusted_pickup_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('parcels', sa.Column('receiver_name_masked', sa.String(length=128), nullable=True))
    op.add_column('parcels', sa.Column('origin', parcel_origin, nullable=False, server_default='SERVER_MANUAL'))
    op.add_column('parcels', sa.Column('sync_status', parcel_sync_status, nullable=False, server_default='SERVER_ONLY'))
    op.alter_column('parcels', 'created_by_admin_id', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column('parcels', 'created_by_admin_id', existing_type=sa.Integer(), nullable=False)
    op.drop_column('parcels', 'sync_status')
    op.drop_column('parcels', 'origin')
    op.drop_column('parcels', 'receiver_name_masked')
    op.drop_column('users', 'trusted_pickup_enabled')
    op.drop_column('users', 'pickup_level')

    bind = op.get_bind()
    if bind.dialect.name == 'mysql':
        op.execute("ALTER TABLE users MODIFY role ENUM('USER','LOCAL_ADMIN','SERVER_ADMIN') NOT NULL")
        op.execute(
            "ALTER TABLE parcels MODIFY status ENUM('CREATED','STORED','WAITING_PICKUP','PICKED_UP','EXCEPTION','CANCELLED') NOT NULL"
        )

    parcel_sync_status.drop(bind, checkfirst=True)
    parcel_origin.drop(bind, checkfirst=True)
