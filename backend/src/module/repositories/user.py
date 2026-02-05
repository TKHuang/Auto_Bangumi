from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: int) -> Optional[User]:
        result = await self.session.get(User, id)
        return result

    async def get_by_username(self, username: str) -> Optional[User]:
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self) -> list[User]:
        stmt = select(User)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: dict) -> User:
        user = User(**data)
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update_password(self, id: int, password_hash: str) -> User:
        user = await self.get_by_id(id)
        if not user:
            raise ValueError(f"User with id {id} not found")

        user.password = password_hash
        await self.session.flush()
        await self.session.refresh(user)
        return user
