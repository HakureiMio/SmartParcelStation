"""
Authentication and authorization for the gateway local API.

- UNBOUND gateway: only /local/health and /local/provisioning/* are allowed.
- BOUND gateway: business endpoints require Authorization: Bearer <session_token>.
- Session tokens are stored as SHA-256 hash in LocalApiSession.
- On auth failure, a GatewaySecurityAudit event is written.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request
from loguru import logger
from sqlalchemy import select

from gateway.core.config import get_settings
from gateway.db.session import SessionLocal
from gateway.models.entities import GatewaySecurityAudit, LocalApiSession


# Paths that are always allowed (even when unbound)
UNBOUND_ALLOWED_PREFIXES = (
    "/local/health",
    "/local/provisioning/",
)

# Paths that require local session auth when bound
AUTH_REQUIRED_PREFIXES = (
    "/local/tags",
    "/local/gate",
)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _write_audit(
    event_type: str,
    source_ip: str | None = None,
    reason: str | None = None,
    request_path: str | None = None,
) -> None:
    """Non-critical audit write."""
    db = SessionLocal()
    try:
        row = GatewaySecurityAudit(
            event_type=event_type,
            source_ip=source_ip,
            reason=reason,
            request_path=request_path,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def generate_local_session_token(role: str = "gateway-operator", source_ip: str | None = None) -> str:
    """Generate a new local session token and persist its hash."""
    plain = secrets.token_urlsafe(32)
    token_hash = _hash_token(plain)
    settings = get_settings()
    db = SessionLocal()
    try:
        session = LocalApiSession(
            session_token_hash=token_hash,
            role=role,
            source_ip=source_ip,
            expires_at=datetime.utcnow() + timedelta(seconds=settings.local_api_token_ttl_seconds),
        )
        db.add(session)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to persist local API session: {}", exc)
        db.rollback()
    finally:
        db.close()
    return plain


def validate_local_session(request: Request) -> dict:
    """FastAPI dependency: validate local session auth for business endpoints.

    Returns a dict with auth info, or raises HTTPException.
    """
    settings = get_settings()
    path = request.url.path
    source_ip = request.client.host if request.client else None

    # --- Always allow unbound provisioning paths ---
    for prefix in UNBOUND_ALLOWED_PREFIXES:
        if path.startswith(prefix):
            return {"authenticated": False, "reason": "unbound_public_path"}

    # --- If unbound, block everything else ---
    if settings.is_unbound:
        _write_audit("local_api_unauthorized", source_ip=source_ip, reason="unbound_gateway_blocked", request_path=path)
        raise HTTPException(
            status_code=403,
            detail="Gateway is unbound. Only /local/health and /local/provisioning/* are available.",
        )

    # --- Check if this path requires auth ---
    requires_auth = any(path.startswith(prefix) for prefix in AUTH_REQUIRED_PREFIXES)
    if not requires_auth:
        return {"authenticated": False, "reason": "public_path"}

    # --- Validate Bearer token ---
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        _write_audit("local_auth_failed", source_ip=source_ip, reason="missing_bearer_token", request_path=path)
        raise HTTPException(status_code=401, detail="Authorization header required: Bearer <token>")

    token = auth_header[len("Bearer "):].strip()
    if not token:
        _write_audit("local_auth_failed", source_ip=source_ip, reason="empty_token", request_path=path)
        raise HTTPException(status_code=401, detail="Empty token")

    token_hash = _hash_token(token)

    db = SessionLocal()
    try:
        session = db.scalar(
            select(LocalApiSession).where(
                LocalApiSession.session_token_hash == token_hash,
            )
        )
        if session is None:
            _write_audit("local_auth_failed", source_ip=source_ip, reason="unknown_token", request_path=path)
            raise HTTPException(status_code=401, detail="Invalid or expired session token")

        if session.revoked_at is not None:
            _write_audit("local_auth_failed", source_ip=source_ip, reason="token_revoked", request_path=path)
            raise HTTPException(status_code=401, detail="Session token has been revoked")

        if session.expires_at and session.expires_at < datetime.utcnow():
            _write_audit("local_auth_failed", source_ip=source_ip, reason="token_expired", request_path=path)
            raise HTTPException(status_code=401, detail="Session token has expired")

        return {"authenticated": True, "role": session.role, "session_id": str(session.id)}
    finally:
        db.close()
