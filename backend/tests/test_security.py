import pytest

from app.security import hash_password, verify_password, create_access_token, decode_token


def test_hash_then_verify_roundtrip():
    h = hash_password("hunter2")
    assert h != "hunter2"
    assert verify_password("hunter2", h) is True
    assert verify_password("wrong", h) is False


def test_token_roundtrip_returns_subject():
    token = create_access_token(sub="42")
    assert decode_token(token) == "42"


def test_decode_rejects_garbage():
    with pytest.raises(ValueError):
        decode_token("not.a.jwt")


def test_decode_rejects_expired():
    token = create_access_token(sub="42", expires_minutes=-1)
    with pytest.raises(ValueError):
        decode_token(token)
