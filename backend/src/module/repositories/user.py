from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.user import User
from module.domain.value_objects import ResponseModel
from module.models.user import UserUpdate
from module.security.password import hash_password, verify_password


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

    async def auth_user(self, user: User) -> ResponseModel:
        """Authenticate user by username and password."""
        statement = select(User).where(User.username == user.username)
        result = await self.session.execute(statement)
        db_user = result.scalar_one_or_none()

        if not user.password:
            return ResponseModel(
                status_code=401,
                status=False,
                msg_en="Incorrect password format",
                msg_zh="密码格式不正确",
            )
        if not db_user:
            return ResponseModel(
                status_code=401,
                status=False,
                msg_en="User not found",
                msg_zh="用户不存在",
            )
        if not verify_password(user.password, db_user.password):
            return ResponseModel(
                status_code=401,
                status=False,
                msg_en="Incorrect password",
                msg_zh="密码错误",
            )
        return ResponseModel(
            status_code=200,
            status=True,
            msg_en="Login successfully",
            msg_zh="登录成功",
        )

    async def update_user(self, username: str, update_user: UserUpdate) -> User:
        """Update user username and/or password."""
        statement = select(User).where(User.username == username)
        result = await self.session.execute(statement)
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise ValueError(f"User '{username}' not found")

        if update_user.username:
            db_user.username = update_user.username
        if update_user.password:
            db_user.password = hash_password(update_user.password)

        self.session.add(db_user)
        await self.session.flush()
        await self.session.refresh(db_user)
        return db_user
