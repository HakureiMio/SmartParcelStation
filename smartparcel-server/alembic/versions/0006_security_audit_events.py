"""security_audit_events

Revision ID: 0006
Revises: 0005
Create Date: 2025-06-30

"""

from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'security_audit_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('source_ip', sa.String(45), nullable=True),
        sa.Column('gateway_code', sa.String(64), nullable=True, index=True),
        sa.Column('request_path', sa.String(512), nullable=True),
        sa.Column('reason', sa.String(128), nullable=True),
        sa.Column('detail_json', sa.JSON(), nullable=False, server_default=sa.text("('{}')")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('security_audit_events')
