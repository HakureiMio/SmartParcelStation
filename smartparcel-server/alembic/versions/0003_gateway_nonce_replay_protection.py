"""gateway nonce replay protection

Revision ID: 0003_gateway_nonce_replay
Revises: 0002_sps_stage_a_flow
Create Date: 2026-06-02 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003_gateway_nonce_replay'
down_revision: Union[str, None] = '0002_sps_stage_a_flow'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'gateway_nonces' in inspector.get_table_names():
        return
    op.create_table(
        'gateway_nonces',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('gateway_id', sa.Integer(), sa.ForeignKey('gateways.id'), nullable=False),
        sa.Column('nonce', sa.String(length=128), nullable=False),
        sa.Column('timestamp', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('gateway_id', 'nonce', name='uq_gateway_nonces_gateway_nonce'),
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'gateway_nonces' in inspector.get_table_names():
        op.drop_table('gateway_nonces')
