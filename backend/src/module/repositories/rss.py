from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.rss import RSSItem


class RSSRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: int) -> Optional[RSSItem]:
        result = await self.session.get(RSSItem, id)
        return result

    async def get_all(self) -> list[RSSItem]:
        stmt = select(RSSItem)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_enabled(self) -> list[RSSItem]:
        stmt = select(RSSItem).where(RSSItem.enabled == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: dict) -> RSSItem:
        rss = RSSItem(**data)
        self.session.add(rss)
        await self.session.flush()
        await self.session.refresh(rss)
        return rss

    async def update(self, id: int, data: dict) -> RSSItem:
        rss = await self.get_by_id(id)
        if not rss:
            raise ValueError(f"RSSItem with id {id} not found")

        for key, value in data.items():
            if hasattr(rss, key) and key not in ["id", "version"]:
                setattr(rss, key, value)

        await self.session.flush()
        await self.session.refresh(rss)
        return rss

    async def update_status(
        self, id: int, status: str, error: Optional[str]
    ) -> RSSItem:
        rss = await self.get_by_id(id)
        if not rss:
            raise ValueError(f"RSSItem with id {id} not found")

        rss.last_status = status
        rss.last_error = error
        rss.last_update = datetime.now(timezone.utc).isoformat()

        await self.session.flush()
        await self.session.refresh(rss)
        return rss

    async def delete(self, id: int) -> None:
        rss = await self.get_by_id(id)
        if not rss:
            raise ValueError(f"RSSItem with id {id} not found")
        
        await self.session.delete(rss)
        await self.session.flush()
