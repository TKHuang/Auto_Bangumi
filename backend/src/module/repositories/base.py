from typing import Generic, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    def __init__(self, session: AsyncSession, model_class: Type[T]):
        self.session = session
        self.model_class = model_class

    async def get_by_id(self, id: int) -> Optional[T]:
        result = await self.session.get(self.model_class, id)
        return result

    async def get_all(self) -> list[T]:
        stmt = select(self.model_class)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: dict) -> T:
        instance = self.model_class(**data)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, id: int) -> None:
        instance = await self.get_by_id(id)
        if not instance:
            raise ValueError(f"{self.model_class.__name__} with id {id} not found")
        await self.session.delete(instance)
        await self.session.flush()
