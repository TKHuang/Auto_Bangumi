"""TDD tests for JWT token creation and validation."""

import os
import time
from datetime import timedelta
from unittest.mock import patch

import pytest
from jose import JWTError

from module.security import create_access_token, decode_access_token


@pytest.mark.unit
class TestCreateAccessToken:
    """Tests for create_access_token function."""

    def test_create_token_with_default_expiry(self):
        """Token should have 24-hour default expiry."""
        token = create_access_token("testuser")
        payload = decode_access_token(token)
        assert "exp" in payload
        # Verify expiry is approximately 24 hours from now
        now = time.time()
        exp_time = payload["exp"]
        delta = exp_time - now
        # Should be between 23.5 and 24.5 hours
        assert 84600 < delta < 86400 + 3600

    def test_create_token_with_custom_expiry(self):
        """Token should respect custom expiry duration."""
        custom_delta = timedelta(hours=1)
        token = create_access_token("testuser", expires_delta=custom_delta)
        payload = decode_access_token(token)
        now = time.time()
        exp_time = payload["exp"]
        delta = exp_time - now
        # Should be between 59 and 61 minutes
        assert 3540 < delta < 3660

    def test_create_token_contains_username(self):
        """Token should contain username in 'sub' claim."""
        username = "alice"
        token = create_access_token(username)
        payload = decode_access_token(token)
        assert payload["sub"] == username

    def test_create_token_uses_hs256(self):
        """Token should use HS256 algorithm."""
        token = create_access_token("testuser")
        # JWT format: header.payload.signature
        parts = token.split(".")
        assert len(parts) == 3
        # Decode header to verify algorithm
        import base64
        import json

        header_b64 = parts[0]
        # Add padding if needed
        padding = 4 - len(header_b64) % 4
        if padding != 4:
            header_b64 += "=" * padding
        header = json.loads(base64.urlsafe_b64decode(header_b64))
        assert header["alg"] == "HS256"


@pytest.mark.unit
class TestDecodeAccessToken:
    """Tests for decode_access_token function."""

    def test_decode_valid_token(self):
        """Should decode valid token and return payload."""
        token = create_access_token("testuser")
        payload = decode_access_token(token)
        assert payload["sub"] == "testuser"
        assert "exp" in payload

    @pytest.mark.parametrize("bad_token", ["invalid.token.here", "not-a-jwt", ""])
    def test_decode_bad_token_raises_error(self, bad_token):
        """Invalid, malformed, or empty token should raise JWTError."""
        with pytest.raises(JWTError):
            decode_access_token(bad_token)

    def test_decode_token_missing_sub_raises_error(self):
        """Token without 'sub' claim should raise JWTError."""
        # Create a token with missing 'sub' by using jose directly
        from jose import jwt

        secret = os.getenv("JWT_SECRET_KEY", "test-secret-key")
        token = jwt.encode({"exp": time.time() + 3600}, secret, algorithm="HS256")
        with pytest.raises(JWTError):
            decode_access_token(token)

    def test_decode_expired_token_raises_error(self):
        """Expired token should raise JWTError."""
        token = create_access_token("testuser", expires_delta=timedelta(seconds=-1))
        with pytest.raises(JWTError):
            decode_access_token(token)

    def test_decode_token_with_wrong_secret_raises_error(self):
        """Token signed with different secret should raise JWTError."""
        token = create_access_token("testuser")
        # Patch the secret key to a different value
        with patch("module.security.jwt.SECRET_KEY", "wrong-secret"):
            with pytest.raises(JWTError):
                decode_access_token(token)


@pytest.mark.unit
class TestJWTIntegration:
    """Integration tests for JWT creation and validation."""

    @pytest.mark.parametrize(
        "username", ["testuser", "alice", "bob", "charlie", "user@example.com"]
    )
    def test_roundtrip_token_creation_and_validation(self, username):
        """Create -> decode roundtrip preserves username/exp; different users get independent tokens."""
        token = create_access_token(username)
        other_token = create_access_token(f"other-{username}")

        payload = decode_access_token(token)
        assert payload["sub"] == username
        assert "exp" in payload

        assert token != other_token
        assert decode_access_token(other_token)["sub"] == f"other-{username}"
