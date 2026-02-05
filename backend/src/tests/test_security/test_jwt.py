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

    def test_create_token_returns_string(self):
        """Token should be a string."""
        token = create_access_token("testuser")
        assert isinstance(token, str)
        assert len(token) > 0

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

    def test_create_token_with_different_usernames(self):
        """Different usernames should produce different tokens."""
        token1 = create_access_token("user1")
        token2 = create_access_token("user2")
        assert token1 != token2
        assert decode_access_token(token1)["sub"] == "user1"
        assert decode_access_token(token2)["sub"] == "user2"

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

    def test_decode_token_returns_dict(self):
        """Decoded token should be a dictionary."""
        token = create_access_token("testuser")
        payload = decode_access_token(token)
        assert isinstance(payload, dict)

    def test_decode_invalid_token_raises_error(self):
        """Invalid token should raise JWTError."""
        with pytest.raises(JWTError):
            decode_access_token("invalid.token.here")

    def test_decode_malformed_token_raises_error(self):
        """Malformed token should raise JWTError."""
        with pytest.raises(JWTError):
            decode_access_token("not-a-jwt")

    def test_decode_empty_token_raises_error(self):
        """Empty token should raise JWTError."""
        with pytest.raises(JWTError):
            decode_access_token("")

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
        # Create token with 1-second expiry
        token = create_access_token("testuser", expires_delta=timedelta(seconds=1))
        # Wait for expiry
        time.sleep(2)
        with pytest.raises(JWTError):
            decode_access_token(token)

    def test_decode_token_with_wrong_secret_raises_error(self):
        """Token signed with different secret should raise JWTError."""
        token = create_access_token("testuser")
        # Patch the secret key to a different value
        with patch("module.security.jwt.SECRET_KEY", "wrong-secret"):
            with pytest.raises(JWTError):
                decode_access_token(token)

    def test_decode_token_preserves_username(self):
        """Decoded token should preserve original username."""
        usernames = ["alice", "bob", "charlie", "user@example.com"]
        for username in usernames:
            token = create_access_token(username)
            payload = decode_access_token(token)
            assert payload["sub"] == username


@pytest.mark.unit
class TestJWTIntegration:
    """Integration tests for JWT creation and validation."""

    def test_roundtrip_token_creation_and_validation(self):
        """Should create and validate token in roundtrip."""
        username = "testuser"
        token = create_access_token(username)
        payload = decode_access_token(token)
        assert payload["sub"] == username
        assert "exp" in payload

    def test_multiple_tokens_are_independent(self):
        """Multiple tokens should be independent."""
        token1 = create_access_token("user1")
        token2 = create_access_token("user2")
        payload1 = decode_access_token(token1)
        payload2 = decode_access_token(token2)
        assert payload1["sub"] == "user1"
        assert payload2["sub"] == "user2"
        assert token1 != token2

    def test_token_expiry_is_in_future(self):
        """Token expiry should always be in the future."""
        token = create_access_token("testuser")
        payload = decode_access_token(token)
        exp_time = payload["exp"]
        now = time.time()
        assert exp_time > now

    def test_custom_expiry_shorter_than_default(self):
        """Custom 1-hour expiry should be shorter than default 24-hour."""
        token_default = create_access_token("user1")
        token_custom = create_access_token("user2", expires_delta=timedelta(hours=1))
        payload_default = decode_access_token(token_default)
        payload_custom = decode_access_token(token_custom)
        assert payload_default["exp"] > payload_custom["exp"]
