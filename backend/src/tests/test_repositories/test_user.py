import pytest

from module.domain.models import User
from module.repositories.user import UserRepository


@pytest.mark.asyncio
class TestUserRepository:
    async def test_create_user_success(self, async_session):
        repo = UserRepository(async_session)
        
        data = {
            "username": "testuser",
            "password": "hashed_password_here",
        }
        
        async with async_session.begin():
            user = await repo.create(data)
        
        assert user.id is not None
        assert user.username == "testuser"
        assert user.password == "hashed_password_here"

    async def test_create_user_duplicate_username_raises_error(self, async_session):
        repo = UserRepository(async_session)
        
        data = {
            "username": "testuser",
            "password": "hashed_password",
        }
        
        async with async_session.begin():
            await repo.create(data)
        
        async with async_session.begin():
            with pytest.raises(Exception):
                await repo.create(data)

    async def test_get_by_username_returns_user(self, async_session):
        repo = UserRepository(async_session)
        
        data = {
            "username": "testuser",
            "password": "hashed_password",
        }
        
        async with async_session.begin():
            await repo.create(data)
        
        async with async_session.begin():
            found = await repo.get_by_username("testuser")
        
        assert found is not None
        assert found.username == "testuser"

    async def test_get_by_username_returns_none_when_not_found(self, async_session):
        repo = UserRepository(async_session)
        
        async with async_session.begin():
            found = await repo.get_by_username("nonexistent")
        
        assert found is None

    async def test_update_password_changes_password(self, async_session):
        repo = UserRepository(async_session)
        
        data = {
            "username": "testuser",
            "password": "old_password",
        }
        
        async with async_session.begin():
            user = await repo.create(data)
            await repo.update_password(user.id, "new_password")
        
        async with async_session.begin():
            updated = await repo.get_by_username("testuser")
        
        assert updated.password == "new_password"

    async def test_get_by_id_returns_user(self, async_session):
        repo = UserRepository(async_session)
        
        data = {
            "username": "testuser",
            "password": "hashed_password",
        }
        
        async with async_session.begin():
            created = await repo.create(data)
        
        async with async_session.begin():
            found = await repo.get_by_id(created.id)
        
        assert found is not None
        assert found.id == created.id
