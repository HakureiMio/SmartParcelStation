"""gateway_factory_provisioning

Revision ID: 0007_gateway_factory_provisioning
Revises: 0006_security_audit_events
Create Date: 2026-06-30

Adds:
  - gateway_factory_devices table
  - New columns on gateways: gateway_factory_code, gateway_device_id, gateway_serial, bound_at
  - New columns on gateway_registration_tokens: gateway_factory_code, gateway_device_id, gateway_serial, created_by_user_id
"""

from alembic import op
import sqlalchemy as sa


revision = '0007_gateway_factory_provisioning'
down_revision = '0006_security_audit_events'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── gateway_factory_devices ──
    op.create_table(
        'gateway_factory_devices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('gateway_factory_code', sa.String(64), unique=True, nullable=False),
        sa.Column('gateway_device_id', sa.String(128), nullable=True),
        sa.Column('gateway_serial', sa.String(128), nullable=True),
        sa.Column('gateway_code', sa.String(64), nullable=True, index=True),
        sa.Column('station_id', sa.Integer(), sa.ForeignKey('stations.id'), nullable=True),
        sa.Column('bound_gateway_id', sa.Integer(), sa.ForeignKey('gateways.id'), nullable=True),
        sa.Column(
            'status',
            sa.Enum('UNKNOWN_SEEN', 'PENDING_BIND', 'BOUND', 'ONLINE', 'DISABLED', 'REVOKED', name='gatewayfactorydevicestatus'),
            nullable=False,
            server_default='UNKNOWN_SEEN',
        ),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('bind_requested_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('bind_requested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('bound_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('disabled_reason', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── gateways: new columns ──
    op.add_column('gateways', sa.Column('gateway_factory_code', sa.String(64), nullable=True, index=True, unique=True))
    op.add_column('gateways', sa.Column('gateway_device_id', sa.String(128), nullable=True))
    op.add_column('gateways', sa.Column('gateway_serial', sa.String(128), nullable=True))
    op.add_column('gateways', sa.Column('bound_at', sa.DateTime(timezone=True), nullable=True))

    # ── gateway_registration_tokens: new columns ──
    op.add_column('gateway_registration_tokens', sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('gateway_registration_tokens', sa.Column('gateway_factory_code', sa.String(64), nullable=True, index=True))
    op.add_column('gateway_registration_tokens', sa.Column('gateway_device_id', sa.String(128), nullable=True))
    op.add_column('gateway_registration_tokens', sa.Column('gateway_serial', sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column('gateway_registration_tokens', 'gateway_serial')
    op.drop_column('gateway_registration_tokens', 'gateway_device_id')
    op.drop_column('gateway_registration_tokens', 'gateway_factory_code')
    op.drop_column('gateway_registration_tokens', 'created_by_user_id')

    op.drop_column('gateways', 'bound_at')
    op.drop_column('gateways', 'gateway_serial')
    op.drop_column('gateways', 'gateway_device_id')
    op.drop_column('gateways', 'gateway_factory_code')

    op.drop_table('gateway_factory_devices')
    op.execute("DROP TYPE IF EXISTS gatewayfactorydevicestatus")
