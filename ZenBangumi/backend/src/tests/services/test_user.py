import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from zen_bangumi.domain.models.user import User
from zen_bangumi.services.auth import verify_password
from zen_bangumi.services.user import authenticate, create_user, update_password


@pytest.mark.asyncio
async def test_create_user_hashes_password(test_session):
    username = "testuser"
    plain_password = "test_password_123"
    
    user = await create_user(username, plain_password, test_session)
    await test_session.commit()
    
    assert user.id is not None
    assert user.username == username
    assert user.password_hash != plain_password
    assert verify_password(plain_password, user.password_hash)
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_create_user_duplicate_username_raises_integrity_error(test_session):
    username = "duplicate_user"
    
    await create_user(username, "password1", test_session)
    await test_session.commit()
    
    with pytest.raises(IntegrityError):
        await create_user(username, "password2", test_session)
        await test_session.commit()


@pytest.mark.asyncio
async def test_authenticate_correct_password_returns_user(test_session):
    username = "authuser"
    password = "correct_password"
    
    created_user = await create_user(username, password, test_session)
    await test_session.commit()
    
    authenticated_user = await authenticate(username, password, test_session)
    
    assert authenticated_user is not None
    assert authenticated_user.id == created_user.id
    assert authenticated_user.username == username


@pytest.mark.asyncio
async def test_authenticate_wrong_password_returns_none(test_session):
    username = "authuser2"
    correct_password = "correct_password"
    wrong_password = "wrong_password"
    
    await create_user(username, correct_password, test_session)
    await test_session.commit()
    
    result = await authenticate(username, wrong_password, test_session)
    
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_nonexistent_user_returns_none(test_session):
    result = await authenticate("nonexistent_user", "any_password", test_session)
    
    assert result is None


@pytest.mark.asyncio
async def test_update_password_changes_password_hash(test_session):
    username = "updateuser"
    old_password = "old_password"
    new_password = "new_password"
    
    user = await create_user(username, old_password, test_session)
    await test_session.commit()
    
    old_hash = user.password_hash
    
    await update_password(user.id, old_password, new_password, test_session)
    await test_session.commit()
    await test_session.refresh(user)
    
    assert user.password_hash != old_hash
    assert verify_password(new_password, user.password_hash)
    assert not verify_password(old_password, user.password_hash)


@pytest.mark.asyncio
async def test_update_password_incorrect_old_password_raises_value_error(test_session):
    username = "updateuser2"
    old_password = "old_password"
    wrong_old_password = "wrong_old_password"
    new_password = "new_password"
    
    user = await create_user(username, old_password, test_session)
    await test_session.commit()
    
    with pytest.raises(ValueError, match="Incorrect old password"):
        await update_password(user.id, wrong_old_password, new_password, test_session)


@pytest.mark.asyncio
async def test_update_password_nonexistent_user_raises_value_error(test_session):
    with pytest.raises(ValueError, match="User not found"):
        await update_password(9999, "old_password", "new_password", test_session)
