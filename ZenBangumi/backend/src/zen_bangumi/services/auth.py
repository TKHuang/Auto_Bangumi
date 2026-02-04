"""Authentication service for password hashing and JWT token management.

This module provides core authentication utilities:
- Password hashing with bcrypt
- JWT token creation and validation
- Token expiration handling
"""

import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import bcrypt
from jose import ExpiredSignatureError, JWTError, jwt


@lru_cache(maxsize=1)
def _get_secret_key() -> str:
    """Get JWT secret key from environment or generate a temporary one.
    
    Set JWT_SECRET_KEY environment variable for persistent tokens across restarts.
    """
    key = os.getenv("JWT_SECRET_KEY")
    if key:
        return key
    import secrets
    return secrets.token_urlsafe(32)


SECRET_KEY = _get_secret_key()
ALGORITHM = "HS256"


def hash_password(plain: str) -> str:
    """Hash a plain text password using bcrypt.
    
    Args:
        plain: Plain text password to hash
        
    Returns:
        Hashed password string
    """
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(plain.encode('utf-8'), salt)
    return hashed_bytes.decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against a hashed password.
    
    Args:
        plain: Plain text password to verify
        hashed: Hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))


def create_access_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token for a user.
    
    Args:
        user_id: User ID to encode in the token
        expires_delta: Token expiration duration (default: 24 hours)
        
    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=24)
    
    to_encode = {
        "sub": str(user_id),
        "exp": expire,
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, int]:
    """Decode and validate a JWT access token.
    
    Args:
        token: JWT token string to decode
        
    Returns:
        Token payload dictionary containing user_id and expiration
        
    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise JWTError("Token missing user_id (sub)")
        
        expires = payload.get("exp")
        if expires is None:
            raise JWTError("Token missing expiration")
        
        return {"user_id": int(user_id_str), "exp": expires}
    except ExpiredSignatureError:
        raise JWTError("Token expired")
    except JWTError:
        raise
    except Exception as e:
        raise JWTError(f"Token decode error: {str(e)}")
