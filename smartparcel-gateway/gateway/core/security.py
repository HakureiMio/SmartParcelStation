from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any


def body_hash(payload: dict[str, Any] | list[Any] | None) -> str:
    if payload is None:
        raw = b""
    else:
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def generate_signature(secret: str, method: str, path: str, timestamp: str, nonce: str, body_sha256: str) -> str:
    signing_content = f"{method.upper()}{path}{timestamp}{nonce}{body_sha256}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), signing_content, hashlib.sha256).hexdigest()


def build_gateway_headers(secret: str, gateway_code: str, method: str, path: str, payload: dict[str, Any] | list[Any] | None = None) -> dict[str, str]:
    ts = str(int(time.time()))
    nonce = uuid.uuid4().hex
    b_hash = body_hash(payload)
    sig = generate_signature(secret, method, path, ts, nonce, b_hash)
    return {
        "X-Gateway-Code": gateway_code,
        "X-Gateway-Timestamp": ts,
        "X-Gateway-Nonce": nonce,
        "X-Gateway-Signature": sig,
        "Content-Type": "application/json",
    }
