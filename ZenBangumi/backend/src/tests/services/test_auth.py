import time
from datetime import timedelta

import pytest
from jose import JWTError

from zen_bangumi.services.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_not_reversible():
    plain = "test_password_123"
    hashed = hash_password(plain)
    
    assert hashed != plain
    assert len(hashed) > 50
    assert hashed.startswith("$2b$")


def test_verify_password_correct():
    plain = "my_secure_password"
    hashed = hash_password(plain)
    
    assert verify_password(plain, hashed) is True


def test_verify_password_incorrect():
    plain = "correct_password"
    wrong = "wrong_password"
    hashed = hash_password(plain)
    
    assert verify_password(wrong, hashed) is False


def test_create_access_token_contains_user_id():
    user_id = 42
    token = create_access_token(user_id)
    
    assert isinstance(token, str)
    assert len(token) > 50
    
    payload = decode_access_token(token)
    assert payload["user_id"] == user_id


def test_create_access_token_default_expires_24h():
    user_id = 1
    token = create_access_token(user_id)
    payload = decode_access_token(token)
    
    exp_timestamp = payload["exp"]
    current_timestamp = time.time()
    time_diff = exp_timestamp - current_timestamp
    
    assert 23 * 3600 < time_diff < 25 * 3600


def test_create_access_token_custom_expiration():
    user_id = 1
    expires_delta = timedelta(hours=1)
    token = create_access_token(user_id, expires_delta)
    payload = decode_access_token(token)
    
    exp_timestamp = payload["exp"]
    current_timestamp = time.time()
    time_diff = exp_timestamp - current_timestamp
    
    assert 0.9 * 3600 < time_diff < 1.1 * 3600


def test_decode_access_token_expired_raises_error():
    user_id = 1
    expires_delta = timedelta(seconds=-1)
    token = create_access_token(user_id, expires_delta)
    
    with pytest.raises(JWTError, match="Token expired"):
        decode_access_token(token)


def test_decode_access_token_invalid_token_raises_error():
    invalid_token = "not.a.valid.jwt.token"
    
    with pytest.raises(JWTError):
        decode_access_token(invalid_token)


def test_decode_access_token_missing_user_id_raises_error():
    from zen_bangumi.services.auth import ALGORITHM, SECRET_KEY
    from jose import jwt
    from datetime import datetime, timezone
    
    payload = {"exp": datetime.now(timezone.utc).timestamp() + 3600}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    with pytest.raises(JWTError, match="missing user_id"):
        decode_access_token(token)
