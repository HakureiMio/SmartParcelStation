"""Test gateway HMAC security: signing, header building, hash consistency."""

import hashlib
import hmac
import json

import pytest

from gateway.core.security import (
    body_hash,
    build_gateway_headers,
    generate_signature,
    raw_body_hash,
    serialize_json_body,
    signing_content,
)


class TestBodySerialization:
    def test_serialize_none_returns_empty(self):
        assert serialize_json_body(None) == b""

    def test_serialize_sorted_keys(self):
        payload = {"z": 1, "a": 2, "m": 3}
        result = serialize_json_body(payload)
        decoded = json.loads(result)
        keys = list(decoded.keys())
        assert keys == ["a", "m", "z"]

    def test_serialize_no_whitespace(self):
        payload = {"key": "value"}
        result = serialize_json_body(payload).decode("utf-8")
        assert " " not in result

    def test_body_hash_deterministic(self):
        payload = {"c": 3, "a": 1, "b": 2}
        h1 = body_hash(payload)
        h2 = body_hash({"a": 1, "b": 2, "c": 3})
        assert h1 == h2

    def test_raw_body_hash(self):
        data = b'{"key":"value"}'
        expected = hashlib.sha256(data).hexdigest()
        assert raw_body_hash(data) == expected

    def test_signing_content_format(self):
        content = signing_content("POST", "/api/v1/test", "1234567890", "abc123", "bodyhash")
        decoded = content.decode("utf-8")
        assert decoded == "POST\n/api/v1/test\n1234567890\nabc123\nbodyhash"


class TestSignatureGeneration:
    def test_generate_signature(self):
        secret = "test-secret"
        sig = generate_signature(secret, "POST", "/test", "1000", "nonce1", "hash1")
        # Verify manually
        expected = hmac.new(
            b"test-secret",
            b"POST\n/test\n1000\nnonce1\nhash1",
            hashlib.sha256,
        ).hexdigest()
        assert sig == expected

    def test_different_secret_different_sig(self):
        sig1 = generate_signature("secret-a", "POST", "/test", "1000", "n1", "h1")
        sig2 = generate_signature("secret-b", "POST", "/test", "1000", "n1", "h1")
        assert sig1 != sig2

    def test_different_body_different_sig(self):
        sig1 = generate_signature("secret", "POST", "/test", "1000", "n1", body_hash({"a": 1}))
        sig2 = generate_signature("secret", "POST", "/test", "1000", "n1", body_hash({"a": 2}))
        assert sig1 != sig2


class TestBuildGatewayHeaders:
    def test_returns_all_required_headers(self):
        headers = build_gateway_headers("secret", "GW001", "POST", "/test", {"key": "val"})
        assert "X-Gateway-Code" in headers
        assert "X-Gateway-Timestamp" in headers
        assert "X-Gateway-Nonce" in headers
        assert "X-Gateway-Body-SHA256" in headers
        assert "X-Gateway-Signature" in headers
        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"
        assert headers["X-Gateway-Code"] == "GW001"

    def test_nonce_is_unique(self):
        h1 = build_gateway_headers("s", "GW", "GET", "/")
        h2 = build_gateway_headers("s", "GW", "GET", "/")
        assert h1["X-Gateway-Nonce"] != h2["X-Gateway-Nonce"]

    def test_no_gateway_secret_in_headers(self):
        """Gateway secret must NOT appear in headers or body hash."""
        secret = "super-secret-key-abc123"
        headers = build_gateway_headers(secret, "GW001", "POST", "/test", {"data": "x"})
        all_values = " ".join(headers.values())
        assert secret not in all_values
        assert "super-secret" not in all_values
