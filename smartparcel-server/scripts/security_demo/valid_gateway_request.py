#!/usr/bin/env python3
"""Demonstrate a valid gateway HMAC-signed request.

Constructs the correct HMAC-SHA256 signature for POST /api/v1/gateways/heartbeat
and sends it to the server. Expected result: 200 OK.

Usage:
    export SERVER_BASE_URL=http://127.0.0.1:18000
    export GATEWAY_CODE=GW-DEV-001       # must be registered/active on server
    export GATEWAY_SECRET=<secret>       # the gateway's long-term secret
    python valid_gateway_request.py

Prerequisites:
    The gateway must already exist on the server with status ACTIVE or ONLINE.
    See POST /api/v1/gateways/register or POST /api/v1/gateways/bootstrap/activate
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
        print("Usage: GATEWAY_SECRET=<secret> python valid_gateway_request.py")
        return

    path: str = "/api/v1/gateways/heartbeat"
    body: dict = {"gateway_code": gateway_code, "status": "ONLINE"}
    body_bytes: bytes = json.dumps(body, separators=(",", ":")).encode("utf-8")

    timestamp: str = str(int(time.time()))
    nonce: str = random_nonce()
    body_sha256: str = hashlib.sha256(body_bytes).hexdigest()

    signature: str = generate_signature(gateway_secret, "POST", path, timestamp, nonce, body_sha256)

    headers: dict = {
        "Content-Type": "application/json",
        "X-Gateway-Code": gateway_code,
        "X-Gateway-Timestamp": timestamp,
        "X-Gateway-Nonce": nonce,
        "X-Gateway-Body-SHA256": body_sha256,
        "X-Gateway-Signature": signature,
    }

    print(f"Server:  {server_base_url}")
    print(f"Path:    POST {path}")
    print(f"Gateway: {gateway_code}")
    print(f"Body:    {json.dumps(body)}")
    print(f"Nonce:   {nonce}")
    print(f"Sig:     {signature[:16]}...")
    print()

    with httpx.Client(timeout=15.0) as client:
        resp = client.post(f"{server_base_url}{path}", headers=headers, content=body_bytes)

    print(f"Status:  {resp.status_code}")
    try:
        print(f"Body:    {json.dumps(resp.json(), ensure_ascii=False)}")
    except Exception:
        print(f"Body:    {resp.text}")

    if resp.status_code == 200:
        print("\n[✓] Valid request — server accepted the heartbeat.")
    elif resp.status_code == 401:
        print("\n[✗] Got 401 — check GATEWAY_CODE, GATEWAY_SECRET, and gateway status.")
    else:
        print(f"\n[?] Unexpected status {resp.status_code}")


if __name__ == "__main__":
    main()
