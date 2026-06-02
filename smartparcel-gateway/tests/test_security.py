from gateway.core.security import body_hash, generate_signature, serialize_json_body


def test_hmac_signature_stable():
    b = body_hash({"b": 2, "a": 1})
    sig = generate_signature("abc", "POST", "/x", "100", "n1", b)
    assert len(sig) == 64
    assert sig == generate_signature("abc", "POST", "/x", "100", "n1", b)


def test_body_hash_uses_stable_json():
    left = body_hash({"b": 2, "a": 1})
    right = body_hash({"a": 1, "b": 2})
    assert left == right
    assert serialize_json_body(None) == b""
    assert serialize_json_body([{"a": 1}]) == b'[{"a":1}]'
