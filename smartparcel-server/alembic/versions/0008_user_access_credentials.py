"""user access credentials

Revision ID: 0008_user_access_credentials
Revises: 0007_gateway_provisioning
Create Date: 2026-07-01
"""

from alembic import op
import sqlalchemy as sa


revision = '0008_user_access_credentials'
down_revision = '0007_gateway_provisioning'
branch_labels = None
depends_on = None


def upgrade() -> None:
    credential_type = sa.Enum('CARD_UID', 'PHONE_HCE', 'GATE_NFC_TAG', 'GATE_QR', name='accesscredentialtype')
    credential_status = sa.Enum('ACTIVE', 'LOST', 'REPLACED', 'DISABLED', 'EXPIRED', name='accesscredentialstatus')
    op.create_table(
        'user_access_credentials',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('station_id', sa.Integer(), sa.ForeignKey('stations.id'), nullable=False, index=True),
        sa.Column('credential_type', credential_type, nullable=False),
        sa.Column('credential_value', sa.String(255), nullable=False, unique=True),
        sa.Column('credential_hash', sa.String(255), nullable=True),
        sa.Column('status', credential_status, nullable=False, server_default='ACTIVE'),
        sa.Column('replaced_by_id', sa.Integer(), sa.ForeignKey('user_access_credentials.id'), nullable=True),
        sa.Column('lost_reported_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('replaced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('disabled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reason', sa.String(255), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_by_admin_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('user_access_credentials')
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('DROP TYPE IF EXISTS accesscredentialstatus')
        op.execute('DROP TYPE IF EXISTS accesscredentialtype')
