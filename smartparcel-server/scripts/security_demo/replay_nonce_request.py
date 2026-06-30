#!/usr/bin/env python3
"""Demonstrate nonce replay detection.

Sends the same (timestamp, nonce) pair twice.
Expected result: first request 200, second 401 "Replay gateway nonce".

Usage:
    export SERVER_BASE_URL=http://127.0.0.1:18000
    export GATEWAY_CODE=GW-DEV-001
    export GATEWAY_SECRET=<secret>
    python replay_nonce_request.py
"""

import hashlib
import hmac
import json
import os
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


def send_request(server_base_url: str, gateway_code: str, gateway_secret: str, timestamp: str, nonce: str, label: str):
    path: str = "/api/v1/gateways/heartbeat"
    body: dict = {"gateway_code": gateway_code, "status": "ONLINE"}
    body_bytes: bytes = json.dumps(body, separators=(",", ":")).encode("utf-8")

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

    with httpx.Client(timeout=15.0) as client:
        resp = client.post(f"{server_base_url}{path}", headers=headers, content=body_bytes)

    print(f"[{label}] Status: {resp.status_code}")
    detail = resp.json().get("detail", "") if resp.status_code != 200 else ""
    if detail:
        print(f"[{label}] Detail: {detail}")
    return resp


def main():
    server_base_url: str = os.environ.get("SERVER_BASE_URL", "http://127.0.0.1:18000").rstrip("/")
    gateway_code: str = os.environ.get("GATEWAY_CODE", "GW-DEV-001")
    gateway_secret: str = os.environ.get("GATEWAY_SECRET", "")

    if not gateway_secret:
        print("[ERROR] GATEWAY_SECRET environment variable is required.")
        return

    # Use the same timestamp and nonce for both requests
    timestamp: str = str(int(time.time()))
    nonce: str = "replay-demo-nonce-001"

    print(f"Server:     {server_base_url}")
    print(f"Gateway:    {gateway_code}")
    print(f"Timestamp:  {timestamp}")
    print(f"Nonce:      {nonce}")
    print()

    # First request — should succeed
    resp1 = send_request(server_base_url, gateway_code, gateway_secret, timestamp, nonce, "1st")

    # Second request — same nonce, should fail
    resp2 = send_request(server_base_url, gateway_code, gateway_secret, timestamp, nonce, "2nd")

    print()
    if resp1.status_code == 200 and resp2.status_code == 401 and "replay" in resp2.text.lower():
        print("[✓] Replay attack detected — second request rejected as replay.")
    elif resp1.status_code == 200 and resp2.status_code == 200:
        print("[✗] Both requests succeeded — nonce replay protection may not be active.")
    else:
        print("[~] Check the responses above for details.")


if __name__ == "__main__":
    main()
