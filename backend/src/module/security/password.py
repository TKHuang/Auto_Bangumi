"""Password hashing and verification using bcrypt."""

import bcrypt

# A fixed bcrypt hash of an unguessable string. Used by ``dummy_verify_password``
# to spend bcrypt-equivalent CPU for nonexistent users so login response time
# does not leak whether a username is registered.
_DUMMY_HASH = bcrypt.hashpw(b"unused", bcrypt.gensalt(rounds=12))


def hash_password(password: str) -> str:
    """Hash a plain text password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string in bcrypt format
    """
    salt = bcrypt.gensalt()
    # bcrypt has a 72-byte limit, truncate if necessary
    password_bytes = password.encode("utf-8")[:72]
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed_bytes.decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a plain password against a hashed password.

    Args:
        password: Plain text password to verify
        hashed: Hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    # bcrypt has a 72-byte limit, truncate if necessary
    password_bytes = password.encode("utf-8")[:72]
    return bcrypt.checkpw(password_bytes, hashed.encode("utf-8"))


def dummy_verify_password() -> None:
    """Spend bcrypt-equivalent CPU on a fixed dummy hash.

    Call this from the login flow when the username is not found so the
    response time is indistinguishable from the "user found, password wrong"
    branch.  Without this, an attacker can probe whether a username exists
    by measuring login latency (real bcrypt verify ~100ms vs early-return ~µs).
    """
    bcrypt.checkpw(b"unused", _DUMMY_HASH)
