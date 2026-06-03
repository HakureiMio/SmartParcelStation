"""user password auth fields

Revision ID: 0005_user_password_auth
Revises: 0004_gateway_registration_tokens
Create Date: 2026-06-04 00:00:00
"""

from typing import Sequence, Union
import base64
import hashlib

from alembic import op
import sqlalchemy as sa


revision: str = '0005_user_password_auth'
down_revision: Union[str, None] = '0004_gateway_registration_tokens'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 120_000)
    return f'pbkdf2_sha256$120000${salt}${base64.b64encode(digest).decode("ascii")}'


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column['name'] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _columns('users')
    if 'username' not in columns:
        op.add_column('users', sa.Column('username', sa.String(length=64), nullable=True))
        op.create_index('ix_users_username', 'users', ['username'], unique=True)
    if 'password_hash' not in columns:
        op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=True))

    conn = op.get_bind()
    station = conn.execute(sa.text('SELECT id FROM stations WHERE id = 1')).first()
    if not station:
        conn.execute(
            sa.text(
                'INSERT INTO stations (id, station_code, name, address, status) '
                'VALUES (1, :station_code, :name, :address, :status)'
            ),
            {'station_code': 'ST001', 'name': '主站点', 'address': '示例路1号', 'status': 'ACTIVE'},
        )

    demo_rows = [
        (1, 'admin001', '系统管理员', '18800000001', 'SERVER_ADMIN', None, 'sps-admin-demo-salt'),
        (2, 'user001', '用户 002', '18800000002', 'USER', 1, 'sps-user-demo-salt'),
        (3, 'staff001', '员工 001', '18800000003', 'STAFF', 1, 'sps-staff-demo-salt'),
        (4, 'gateway001', '网关管理员', '18800000004', 'GATEWAY_ADMIN', 1, 'sps-gateway-demo-salt'),
    ]
    for user_id, username, display_name, phone, role, station_id, salt in demo_rows:
        password_hash = _hash_password('123456', salt)
        existing = conn.execute(sa.text('SELECT id FROM users WHERE id = :id'), {'id': user_id}).first()
        if existing:
            conn.execute(
                sa.text(
                    'UPDATE users SET username=:username, password_hash=COALESCE(password_hash, :password_hash), '
                    'display_name=:display_name, phone=:phone, role=:role, station_id=:station_id, is_active=1 WHERE id=:id'
                ),
                {
                    'id': user_id,
                    'username': username,
                    'password_hash': password_hash,
                    'display_name': display_name,
                    'phone': phone,
                    'role': role,
                    'station_id': station_id,
                },
            )
        else:
            conn.execute(
                sa.text(
                    'INSERT INTO users (id, username, password_hash, display_name, phone, role, station_id, is_active, pickup_level, trusted_pickup_enabled) '
                    'VALUES (:id, :username, :password_hash, :display_name, :phone, :role, :station_id, 1, "NORMAL", 0)'
                ),
                {
                    'id': user_id,
                    'username': username,
                    'password_hash': password_hash,
                    'display_name': display_name,
                    'phone': phone,
                    'role': role,
                    'station_id': station_id,
                },
            )


def downgrade() -> None:
    columns = _columns('users')
    if 'password_hash' in columns:
        op.drop_column('users', 'password_hash')
    if 'username' in columns:
        op.drop_index('ix_users_username', table_name='users')
        op.drop_column('users', 'username')
