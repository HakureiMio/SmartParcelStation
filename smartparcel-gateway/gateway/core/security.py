from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any


def serialize_json_body(payload: dict[str, Any] | list[Any] | None) -> bytes:
    if payload is None:
        return b""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def body_hash(payload: dict[str, Any] | list[Any] | None) -> str:
    return hashlib.sha256(serialize_json_body(payload)).hexdigest()


def raw_body_hash(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def signing_content(method: str, path: str, timestamp: str, nonce: str, body_sha256: str) -> bytes:
    return f"{method.upper()}\n{path}\n{timestamp}\n{nonce}\n{body_sha256}".encode("utf-8")


def generate_signature(secret: str, method: str, path: str, timestamp: str, nonce: str, body_sha256: str) -> str:
    return hmac.new(secret.encode("utf-8"), signing_content(method, path, timestamp, nonce, body_sha256), hashlib.sha256).hexdigest()


def build_gateway_headers(secret: str, gateway_code: str, method: str, path: str, payload: dict[str, Any] | list[Any] | None = None) -> dict[str, str]:
    ts = str(int(time.time()))
    nonce = uuid.uuid4().hex
    b_hash = body_hash(payload)
    sig = generate_signature(secret, method, path, ts, nonce, b_hash)
    return {
        "X-Gateway-Code": gateway_code,
        "X-Gateway-Timestamp": ts,
        "X-Gateway-Nonce": nonce,
        "X-Gateway-Body-SHA256": b_hash,
        "X-Gateway-Signature": sig,
        "Content-Type": "application/json",
    }
