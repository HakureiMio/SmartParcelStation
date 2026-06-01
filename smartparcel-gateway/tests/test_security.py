from gateway.core.security import body_hash, generate_signature


def test_hmac_signature_stable():
    b = body_hash({"a": 1})
    sig = generate_signature("abc", "POST", "/x", "100", "n1", b)
    assert len(sig) == 64
    assert sig == generate_signature("abc", "POST", "/x", "100", "n1", b)
