"""add parcel shelf code

Revision ID: 0009_parcel_shelf_code
Revises: 0008_user_access_credentials
Create Date: 2026-07-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '0009_parcel_shelf_code'
down_revision = '0008_user_access_credentials'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    columns = inspect(op.get_bind()).get_columns(table_name)
    return any(column['name'] == column_name for column in columns)


def upgrade() -> None:
    if not _column_exists('parcels', 'shelf_code'):
        op.add_column('parcels', sa.Column('shelf_code', sa.String(64), nullable=True))


def downgrade() -> None:
    if _column_exists('parcels', 'shelf_code'):
        op.drop_column('parcels', 'shelf_code')
