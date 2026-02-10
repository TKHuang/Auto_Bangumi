"""JWT token creation and validation using HS256 algorithm."""

import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from jose import JWTError, jwt


@lru_cache(maxsize=1)
def _get_secret_key() -> str:
    """Get JWT secret key from environment, file, or generate and persist one."""
    key = os.getenv("JWT_SECRET_KEY")
    if key:
        return key

    key_file = os.path.join("data", ".jwt_secret_key")
    try:
        if os.path.isfile(key_file):
            with open(key_file) as f:
                stored = f.read().strip()
                if stored:
                    return stored
    except OSError:
        pass

    import secrets
    generated = secrets.token_urlsafe(32)
    try:
        os.makedirs("data", exist_ok=True)
        with open(key_file, "w") as f:
            f.write(generated)
    except OSError:
        pass
    return generated


SECRET_KEY = _get_secret_key()
ALGORITHM = "HS256"


def create_access_token(
    username: str, expires_delta: timedelta | None = None
) -> str:
    """Create a JWT access token for a user.

    Args:
        username: Username to encode in the token's 'sub' claim
        expires_delta: Token expiration duration (default: 24 hours)

    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=24)

    to_encode = {
        "sub": username,
        "exp": expire,
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, int | str]:
    """Decode and validate a JWT access token.

    Args:
        token: JWT token string to decode

    Returns:
        Token payload dictionary containing 'sub' (username) and 'exp' (expiration)

    Raises:
        JWTError: If token is invalid, expired, or missing required claims
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise JWTError("Token missing username (sub)")

        exp = payload.get("exp")
        if exp is None:
            raise JWTError("Token missing expiration (exp)")

        return payload
    except JWTError:
        raise
    except Exception as e:
        raise JWTError(f"Token decode error: {str(e)}")


def verify_token(token: str) -> dict[str, int | str] | None:
    """Verify a JWT token (legacy compatibility).

    Args:
        token: JWT token string to verify

    Returns:
        Token payload if valid, None if invalid or expired
    """
    try:
        return decode_access_token(token)
    except JWTError:
        return None
