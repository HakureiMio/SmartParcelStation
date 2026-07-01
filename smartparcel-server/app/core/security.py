import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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


# ── Bearer Token (HMAC-SHA256) ──

_bearer_scheme = HTTPBearer(auto_error=False)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += '=' * padding
    return base64.urlsafe_b64decode(s)


def create_access_token(user_id: int, role: str, station_id: int | None) -> str:
    """Create a stateless Bearer token: sps1.<base64url payload>.<hmac_signature>"""
    settings = get_settings()
    exp = int((datetime.now(timezone.utc) + timedelta(seconds=settings.auth_token_ttl_seconds)).timestamp())
    payload = json.dumps({'user_id': user_id, 'role': role, 'station_id': station_id, 'exp': exp}, separators=(',', ':'))
    encoded = _b64url_encode(payload.encode('utf-8'))
    sig = hmac.new(settings.auth_token_secret.encode('utf-8'), encoded.encode('utf-8'), hashlib.sha256).hexdigest()
    return f'sps1.{encoded}.{sig}'


def _verify_access_token_internal(token: str) -> dict | None:
    """Verify token and return payload dict, or None."""
    settings = get_settings()
    try:
        parts = token.split('.')
        if len(parts) != 3 or parts[0] != 'sps1':
            return None
        _, encoded, sig = parts
        expected_sig = hmac.new(settings.auth_token_secret.encode('utf-8'), encoded.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, sig):
            return None
        payload = json.loads(_b64url_decode(encoded).decode('utf-8'))
        now = int(time.time())
        if payload.get('exp', 0) < now:
            return None
        return payload
    except Exception:
        return None


async def _load_user_from_token(db: AsyncSession, token: str) -> User | None:
    """Load User from a verified token payload."""
    payload = _verify_access_token_internal(token)
    if not payload:
        return None
    result = await db.execute(select(User).where(User.id == int(payload['user_id']), User.is_active.is_(True)))
    return result.scalar_one_or_none()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract current user from Bearer token. Requires valid token."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Missing authorization token')
    user = await _load_user_from_token(db, credentials.credentials)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or expired token')
    return user


async def get_current_staff_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require STAFF, GATEWAY_ADMIN, or SERVER_ADMIN role."""
    if current_user.role not in {UserRole.STAFF, UserRole.GATEWAY_ADMIN, UserRole.SERVER_ADMIN}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Staff or admin role required')
    return current_user


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
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    x_dev_user_id: Optional[int] = Header(default=None, alias='X-Dev-User-Id'),
    x_dev_role: Optional[str] = Header(default=None, alias='X-Dev-Role'),
    db: AsyncSession = Depends(get_db),
) -> object:
    settings = get_settings()
    if x_admin_bootstrap_token and hmac.compare_digest(x_admin_bootstrap_token, settings.admin_bootstrap_token):
        return {'auth': 'bootstrap'}
    if credentials and credentials.credentials:
        bearer_user = await _load_user_from_token(db, credentials.credentials)
        if bearer_user and bearer_user.role == UserRole.SERVER_ADMIN:
            return bearer_user
        _raise_auth('Admin role required')
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
