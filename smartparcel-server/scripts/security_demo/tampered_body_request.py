#!/usr/bin/env python3
"""Demonstrate tampered body detection.

Signs the request with body-A's hash, but sends body-B.
Expected result: 401 "Invalid gateway body hash".

Usage:
    export SERVER_BASE_URL=http://127.0.0.1:18000
    export GATEWAY_CODE=GW-DEV-001
    export GATEWAY_SECRET=<secret>
    python tampered_body_request.py
"""

import hashlib
import hmac
import json
import os
import random
import string
import time

import httpx


def signing_content(method: str, path: str, timestamp: str, nonce: str, body_sha256: str) -> bytes:
    return f"{method.upper()}\n{path}\n{timestamp}\n{nonce}\n{body_sha256}".encode("utf-8")


def generate_signature(secret: str, method: str, path: str, timestamp: str, nonce: str, body_sha256: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        signing_content(method, path, timestamp, nonce, body_sha256),
        hashlib.sha256,
    ).hexdigest()


def random_nonce(length: int = 16) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def main():
    server_base_url: str = os.environ.get("SERVER_BASE_URL", "http://127.0.0.1:18000").rstrip("/")
    gateway_code: str = os.environ.get("GATEWAY_CODE", "GW-DEV-001")
    gateway_secret: str = os.environ.get("GATEWAY_SECRET", "")

    if not gateway_secret:
        print("[ERROR] GATEWAY_SECRET environment variable is required.")
        return

    path: str = "/api/v1/gateways/heartbeat"

    # Body that will actually be sent (tampered)
    body_actual: dict = {"gateway_code": gateway_code, "status": "OFFLINE"}
    body_actual_bytes: bytes = json.dumps(body_actual, separators=(",", ":")).encode("utf-8")

    # Body that the signature is computed against (the "honest" body)
    body_signed: dict = {"gateway_code": gateway_code, "status": "ONLINE"}
    body_signed_bytes: bytes = json.dumps(body_signed, separators=(",", ":")).encode("utf-8")

    timestamp: str = str(int(time.time()))
    nonce: str = random_nonce()

    # Compute body hash and signature against body_signed, but send body_actual
    body_sha256: str = hashlib.sha256(body_signed_bytes).hexdigest()
    signature: str = generate_signature(gateway_secret, "POST", path, timestamp, nonce, body_sha256)

    headers: dict = {
        "Content-Type": "application/json",
        "X-Gateway-Code": gateway_code,
        "X-Gateway-Timestamp": timestamp,
        "X-Gateway-Nonce": nonce,
        "X-Gateway-Body-SHA256": body_sha256,
        "X-Gateway-Signature": signature,
    }

    print(f"Server:          {server_base_url}")
    print(f"Path:            POST {path}")
    print(f"Body signed:     {json.dumps(body_signed)}")
    print(f"Body sent:       {json.dumps(body_actual)}")
    print(f"Body-SHA256:     {body_sha256[:16]}... (hash of signed body)")
    print()

    with httpx.Client(timeout=15.0) as client:
        # Send the tampered body, not the one that was signed
        resp = client.post(f"{server_base_url}{path}", headers=headers, content=body_actual_bytes)

    print(f"Status:  {resp.status_code}")
    print(f"Detail:  {resp.json().get('detail', resp.text) if resp.status_code != 200 else resp.text}")

    if resp.status_code == 401 and "body hash" in resp.text.lower():
        print("\n[✓] Tampering detected — server correctly rejected the mismatched body.")
    elif resp.status_code == 401:
        print("\n[~] Got 401 but for a different reason — check the detail above.")
    else:
        print("\n[✗] Expected 401 'Invalid gateway body hash' but got a different response.")


if __name__ == "__main__":
    main()
