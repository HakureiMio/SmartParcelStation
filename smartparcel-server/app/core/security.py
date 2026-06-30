import hashlib
import hmac
import logging
import time
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.models import Gateway, GatewayNonce, SecurityAuditEvent, User

logger = logging.getLogger(__name__)


def _raise_auth(detail: str = 'Unauthorized') -> None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _log_gateway_auth_failure(gateway_code: str | None, path: str, reason: str) -> None:
    logger.warning('gateway auth failed gateway_code=%s path=%s reason=%s', gateway_code or '-', path, reason)


async def _record_security_audit(
    db: AsyncSession,
    event_type: str,
    source_ip: str | None,
    gateway_code: str | None,
    request_path: str | None,
    reason: str | None,
    detail: dict | None = None,
) -> None:
    """Record a security audit event. Never raises — falls back to logging on DB write failure."""
    try:
        audit = SecurityAuditEvent(
            event_type=event_type,
            source_ip=source_ip,
            gateway_code=gateway_code,
            request_path=request_path,
            reason=reason,
            detail_json=detail or {},
        )
        db.add(audit)
        await db.flush()
    except Exception:
        logger.warning(
            'security_audit_db_write_failed event_type=%s gateway_code=%s reason=%s',
            event_type,
            gateway_code or '-',
            reason or '-',
        )


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


async def get_current_server_admin(current_user: User = Depends(get_current_user_dev)) -> User:
    if current_user.role != UserRole.SERVER_ADMIN:
        _raise_auth('Admin role required')
    return current_user


async def get_current_server_admin_or_bootstrap(
    x_admin_bootstrap_token: Optional[str] = Header(default=None, alias='X-Admin-Bootstrap-Token'),
    x_dev_user_id: Optional[int] = Header(default=None, alias='X-Dev-User-Id'),
    x_dev_role: Optional[str] = Header(default=None, alias='X-Dev-Role'),
    db: AsyncSession = Depends(get_db),
) -> object:
    settings = get_settings()
    if x_admin_bootstrap_token and hmac.compare_digest(x_admin_bootstrap_token, settings.admin_bootstrap_token):
        return {'auth': 'bootstrap'}
    user = await get_current_user_dev(x_dev_user_id=x_dev_user_id, x_dev_role=x_dev_role, db=db)
    if user.role != UserRole.SERVER_ADMIN:
        _raise_auth('Admin role required')
    return user


def raw_body_hash(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def signing_content(method: str, path: str, timestamp: str, nonce: str, body_sha256: str) -> bytes:
    return f'{method.upper()}\n{path}\n{timestamp}\n{nonce}\n{body_sha256}'.encode('utf-8')


def generate_gateway_signature(secret: str, method: str, path: str, timestamp: str, nonce: str, body_sha256: str) -> str:
    return hmac.new(secret.encode('utf-8'), signing_content(method, path, timestamp, nonce, body_sha256), hashlib.sha256).hexdigest()


def verify_gateway_signature(secret: str, method: str, path: str, timestamp: str, nonce: str, body_sha256: str, signature: str) -> bool:
    expected = generate_gateway_signature(secret, method, path, timestamp, nonce, body_sha256)
    return hmac.compare_digest(expected, signature)


def validate_gateway_timestamp(timestamp: str, tolerance_seconds: int) -> int:
    try:
        value = int(timestamp)
    except (TypeError, ValueError):
        _raise_auth('Invalid gateway timestamp')
    now = int(time.time())
    if abs(now - value) > tolerance_seconds:
        _raise_auth('Expired gateway timestamp')
    return value


async def remember_gateway_nonce(db: AsyncSession, gateway_id: int, nonce: str, timestamp: int, tolerance_seconds: int) -> None:
    cutoff = int(time.time()) - tolerance_seconds
    await db.execute(GatewayNonce.__table__.delete().where(GatewayNonce.timestamp < cutoff))
    db.add(GatewayNonce(gateway_id=gateway_id, nonce=nonce, timestamp=timestamp))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        _raise_auth('Replay gateway nonce')


async def verify_gateway_request(
    request: Request,
    payload: bytes | None,
    x_gateway_code: Optional[str],
    x_gateway_timestamp: Optional[str],
    x_gateway_nonce: Optional[str],
    x_gateway_body_sha256: Optional[str],
    x_gateway_signature: Optional[str],
    db: AsyncSession,
    expected_gateway_code: str | None = None,
) -> Gateway:
    path = request.url.path
    source_ip = request.client.host if request.client else None
    settings = get_settings()
    if not all([x_gateway_code, x_gateway_timestamp, x_gateway_nonce, x_gateway_body_sha256, x_gateway_signature]):
        _log_gateway_auth_failure(x_gateway_code, path, 'missing_header')
        await _record_security_audit(db, 'gateway_auth_failure', source_ip, x_gateway_code, path, 'missing_header')
        _raise_auth('Missing gateway headers')

    result = await db.execute(select(Gateway).where(Gateway.gateway_code == x_gateway_code))
    gateway = result.scalar_one_or_none()
    if not gateway:
        _log_gateway_auth_failure(x_gateway_code, path, 'unknown_gateway')
        await _record_security_audit(db, 'gateway_auth_failure', source_ip, x_gateway_code, path, 'unknown_gateway')
        _raise_auth('Gateway not found')
    if expected_gateway_code and gateway.gateway_code != expected_gateway_code:
        _log_gateway_auth_failure(x_gateway_code, path, 'gateway_code_mismatch')
        await _record_security_audit(db, 'gateway_auth_failure', source_ip, x_gateway_code, path, 'gateway_code_mismatch')
        _raise_auth('Gateway code mismatch')
    if gateway.status not in {'ACTIVE', 'ONLINE'}:
        _log_gateway_auth_failure(x_gateway_code, path, 'gateway_disabled')
        await _record_security_audit(db, 'gateway_auth_failure', source_ip, x_gateway_code, path, 'gateway_disabled')
        _raise_auth('Gateway disabled')

    try:
        timestamp = validate_gateway_timestamp(x_gateway_timestamp or '', settings.gateway_signature_tolerance_seconds)
    except HTTPException:
        _log_gateway_auth_failure(x_gateway_code, path, 'expired_timestamp')
        await _record_security_audit(db, 'gateway_auth_failure', source_ip, x_gateway_code, path, 'expired_timestamp')
        raise

    raw_payload = payload if payload is not None else await request.body()
    actual_body_hash = raw_body_hash(raw_payload)
    if not hmac.compare_digest(actual_body_hash, x_gateway_body_sha256 or ''):
        _log_gateway_auth_failure(x_gateway_code, path, 'invalid_body_hash')
        await _record_security_audit(db, 'gateway_auth_failure', source_ip, x_gateway_code, path, 'invalid_body_hash')
        _raise_auth('Invalid gateway body hash')

    if not verify_gateway_signature(
        gateway.device_secret_hash,
        request.method,
        path,
        x_gateway_timestamp or '',
        x_gateway_nonce or '',
        actual_body_hash,
        x_gateway_signature or '',
    ):
        _log_gateway_auth_failure(x_gateway_code, path, 'invalid_signature')
        await _record_security_audit(db, 'gateway_auth_failure', source_ip, x_gateway_code, path, 'invalid_signature')
        _raise_auth('Invalid gateway signature')

    try:
        await remember_gateway_nonce(db, gateway.id, x_gateway_nonce or '', timestamp, settings.gateway_signature_tolerance_seconds)
    except HTTPException:
        _log_gateway_auth_failure(x_gateway_code, path, 'replay_nonce')
        await _record_security_audit(db, 'gateway_auth_failure', source_ip, x_gateway_code, path, 'replay_nonce')
        raise

    return gateway


async def get_current_gateway(
    request: Request,
    x_gateway_code: Optional[str] = Header(default=None, alias='X-Gateway-Code'),
    x_gateway_timestamp: Optional[str] = Header(default=None, alias='X-Gateway-Timestamp'),
    x_gateway_nonce: Optional[str] = Header(default=None, alias='X-Gateway-Nonce'),
    x_gateway_body_sha256: Optional[str] = Header(default=None, alias='X-Gateway-Body-SHA256'),
    x_gateway_signature: Optional[str] = Header(default=None, alias='X-Gateway-Signature'),
    db: AsyncSession = Depends(get_db),
) -> Gateway:
    return await verify_gateway_request(
        request=request,
        payload=await request.body(),
        x_gateway_code=x_gateway_code,
        x_gateway_timestamp=x_gateway_timestamp,
        x_gateway_nonce=x_gateway_nonce,
        x_gateway_body_sha256=x_gateway_body_sha256,
        x_gateway_signature=x_gateway_signature,
        db=db,
    )
