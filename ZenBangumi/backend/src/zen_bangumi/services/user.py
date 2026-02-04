"""User management service for creating, authenticating, and updating users."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zen_bangumi.domain.models.user import User
from zen_bangumi.services.auth import hash_password, verify_password


async def create_user(username: str, password: str, session: AsyncSession) -> User:
    """Create a new user with hashed password.
    
    Args:
        username: Unique username for the new user
        password: Plain text password (will be hashed)
        session: SQLAlchemy async session
        
    Returns:
        Created User instance
        
    Raises:
        IntegrityError: If username already exists
    """
    user = User(
        username=username,
        password_hash=hash_password(password),
        created_at=datetime.now(timezone.utc),
    )
    
    session.add(user)
    await session.flush()
    await session.refresh(user)
    
    return user


async def authenticate(username: str, password: str, session: AsyncSession) -> User | None:
    """Authenticate a user by username and password.
    
    Args:
        username: Username to authenticate
        password: Plain text password to verify
        session: SQLAlchemy async session
        
    Returns:
        User instance if authentication succeeds, None otherwise
    """
    stmt = select(User).where(User.username == username)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        return None
    
    if not verify_password(password, user.password_hash):
        return None
    
    return user


async def update_password(
    user_id: int, old_password: str, new_password: str, session: AsyncSession
) -> None:
    """Update a user's password after verifying the old password.
    
    Args:
        user_id: ID of the user to update
        old_password: Current password for verification
        new_password: New password to set (will be hashed)
        session: SQLAlchemy async session
        
    Raises:
        ValueError: If user not found or old password is incorrect
    """
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise ValueError("User not found")
    
    if not verify_password(old_password, user.password_hash):
        raise ValueError("Incorrect old password")
    
    user.password_hash = hash_password(new_password)
    await session.flush()
