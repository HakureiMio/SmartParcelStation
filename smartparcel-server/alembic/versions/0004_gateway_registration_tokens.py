"""gateway registration tokens

Revision ID: 0004_gateway_registration_tokens
Revises: 0003_gateway_nonce_replay
Create Date: 2026-06-02 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004_gateway_registration_tokens'
down_revision: Union[str, None] = '0003_gateway_nonce_replay'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


token_status = sa.Enum('PENDING', 'USED', 'EXPIRED', 'REVOKED', name='gatewayregistrationtokenstatus')


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'gateway_registration_tokens' in inspector.get_table_names():
        return
    op.create_table(
        'gateway_registration_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('token_id', sa.String(length=64), nullable=False),
        sa.Column('gateway_code', sa.String(length=64), nullable=False),
        sa.Column('station_id', sa.Integer(), sa.ForeignKey('stations.id'), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', token_status, nullable=False, server_default='PENDING'),
        sa.Column('created_by_admin_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('token_id', name='uq_gateway_registration_tokens_token_id'),
        sa.UniqueConstraint('token_hash', name='uq_gateway_registration_tokens_token_hash'),
    )
    op.create_index('ix_gateway_registration_tokens_gateway_code', 'gateway_registration_tokens', ['gateway_code'])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'gateway_registration_tokens' in inspector.get_table_names():
        indexes = {index['name'] for index in inspector.get_indexes('gateway_registration_tokens')}
        if 'ix_gateway_registration_tokens_gateway_code' in indexes:
            op.drop_index('ix_gateway_registration_tokens_gateway_code', table_name='gateway_registration_tokens')
        op.drop_table('gateway_registration_tokens')
    token_status.drop(op.get_bind(), checkfirst=True)
