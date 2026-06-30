"""
Local security audit service for network security demonstration.

Records security-relevant events to the gateway_security_audit table.
- Never logs secrets, plaintext tokens, or full sensitive request bodies.
- Credential values and tokens are stored as SHA-256 hashes only.
- Audit write failures are logged but never propagated to the caller.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from gateway.models.entities import GatewaySecurityAudit


def _hash_value(value: str) -> str:
    """SHA-256 hash a value for safe audit storage."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_detail(payload: dict[str, Any] | None) -> str | None:
    """Serialize a payload to JSON, stripping known sensitive keys."""
    if payload is None:
        return None
    safe = {}
    sensitive_keys = {
        "gateway_secret", "secret", "password", "token", "registration_token",
        "pairing_code", "session_token", "local_api_token", "one_time_binding_token",
        "credential_value", "card_uid",
    }
    for key, value in payload.items():
        if key in sensitive_keys:
            safe[key] = "[REDACTED]"
        elif isinstance(value, str) and len(value) > 64:
            safe[key] = _hash_value(value)[:16] + "..."
        else:
            safe[key] = value
    try:
        return json.dumps(safe, ensure_ascii=False, default=str)
    except Exception:
        return None


class SecurityAuditService:
    """Non-critical audit logger. Write failures are swallowed."""

    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        event_type: str,
        source_ip: str | None = None,
        actor_type: str | None = None,
        actor_id: str | None = None,
        request_path: str | None = None,
        reason: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Record a security audit event. Never raises."""
        try:
            row = GatewaySecurityAudit(
                event_type=event_type,
                source_ip=source_ip,
                actor_type=actor_type,
                actor_id=_hash_value(actor_id) if actor_id else None,
                request_path=request_path,
                reason=reason,
                detail_json=_safe_detail(detail),
                created_at=datetime.utcnow(),
            )
            self.db.add(row)
            self.db.commit()
        except Exception as exc:
            logger.warning("security_audit write failed (non-fatal): {}", exc)
            try:
                self.db.rollback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Convenience methods for known event types
    # ------------------------------------------------------------------

    def provisioning_started(self, source_ip: str | None = None) -> None:
        self.record("provisioning_started", source_ip=source_ip)

    def provisioning_bind_attempt(self, source_ip: str | None = None, detail: dict | None = None) -> None:
        self.record("provisioning_bind_attempt", source_ip=source_ip, detail=detail)

    def provisioning_bind_success(self, source_ip: str | None = None, detail: dict | None = None) -> None:
        self.record("provisioning_bind_success", source_ip=source_ip, detail=detail)

    def provisioning_bind_failed(self, reason: str, source_ip: str | None = None, detail: dict | None = None) -> None:
        self.record("provisioning_bind_failed", source_ip=source_ip, reason=reason, detail=detail)

    def local_auth_success(self, source_ip: str | None = None, actor_type: str = "local-api", actor_id: str | None = None) -> None:
        self.record("local_auth_success", source_ip=source_ip, actor_type=actor_type, actor_id=actor_id)

    def local_auth_failed(self, reason: str, source_ip: str | None = None, request_path: str | None = None) -> None:
        self.record("local_auth_failed", source_ip=source_ip, reason=reason, request_path=request_path)

    def local_api_unauthorized(self, request_path: str, source_ip: str | None = None) -> None:
        self.record("local_api_unauthorized", source_ip=source_ip, request_path=request_path,
                    reason="unbound_gateway_blocked_business_endpoint")

    def heartbeat_success(self) -> None:
        self.record("heartbeat_success")

    def heartbeat_failed(self, reason: str | None = None) -> None:
        self.record("heartbeat_failed", reason=reason)

    def server_signature_rejected(self, reason: str | None = None) -> None:
        self.record("server_signature_rejected", reason=reason)

    def replay_detected(self, source_ip: str | None = None, detail: dict | None = None) -> None:
        self.record("replay_detected", source_ip=source_ip, detail=detail)

    def suspicious_request(self, reason: str, source_ip: str | None = None, request_path: str | None = None, detail: dict | None = None) -> None:
        self.record("suspicious_request", source_ip=source_ip, reason=reason, request_path=request_path, detail=detail)
