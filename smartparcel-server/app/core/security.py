import hashlib
import hmac
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.models import Gateway, User


def _raise_auth(detail: str = 'Unauthorized') -> None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


async def get_current_user_dev(
    x_dev_user_id: Optional[int] = Header(default=None, alias='X-Dev-User-Id'),
    x_dev_role: Optional[str] = Header(default=None, alias='X-Dev-Role'),
    db: AsyncSession = Depends(get_db),
) -> User:
    if x_dev_user_id is None or not x_dev_role:
        _raise_auth('Missing development auth headers')

    result = await db.execute(select(User).where(User.id == x_dev_user_id, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if not user:
        _raise_auth('User not found or inactive')

    if user.role.value != x_dev_role:
        _raise_auth('Role mismatch')

    return user


def verify_gateway_signature(gateway_code: str, payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode('utf-8'), gateway_code.encode('utf-8') + b'.' + payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def verify_gateway_request(
    payload: bytes,
    x_gateway_code: Optional[str],
    x_gateway_signature: Optional[str],
    db: AsyncSession,
    fallback_secret: str,
) -> Gateway:
    if not x_gateway_code or not x_gateway_signature:
        _raise_auth('Missing gateway headers')

    result = await db.execute(select(Gateway).where(Gateway.gateway_code == x_gateway_code))
    gateway = result.scalar_one_or_none()
    if not gateway:
        _raise_auth('Gateway not found')

    secret = gateway.device_secret_hash or fallback_secret
    if not verify_gateway_signature(x_gateway_code, payload, x_gateway_signature, secret):
        _raise_auth('Invalid gateway signature')

    return gateway
