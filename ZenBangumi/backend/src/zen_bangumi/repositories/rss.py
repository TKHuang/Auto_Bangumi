from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from zen_bangumi.domain.models.rss import RSSItem
from zen_bangumi.domain.models.bangumi import Bangumi
from zen_bangumi.domain.models.torrent import Torrent


class RSSRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> list[RSSItem]:
        stmt = select(RSSItem)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_enabled(self) -> list[RSSItem]:
        stmt = select(RSSItem).where(RSSItem.enabled == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self, url: str, name: Optional[str] = None, enabled: bool = True, aggregate: bool = False
    ) -> RSSItem:
        rss_item = RSSItem(
            url=url,
            name=name,
            enabled=enabled,
            aggregate=aggregate,
        )
        self.session.add(rss_item)
        await self.session.flush()
        await self.session.refresh(rss_item)
        return rss_item

    async def delete(self, id: int) -> None:
        rss_item = await self.session.get(RSSItem, id)
        if not rss_item:
            raise ValueError(f"RSS item with id {id} not found")

        torrent_stmt = delete(Torrent).where(Torrent.rss_id == id)
        await self.session.execute(torrent_stmt)

        bangumi_stmt = delete(Bangumi).where(Bangumi.rss_id == id)
        await self.session.execute(bangumi_stmt)

        await self.session.delete(rss_item)
        await self.session.flush()

    async def update(self, id: int, data: dict) -> RSSItem:
        rss_item = await self.session.get(RSSItem, id)
        if not rss_item:
            raise ValueError(f"RSS item with id {id} not found")

        for key, value in data.items():
            if hasattr(rss_item, key) and key != "id":
                setattr(rss_item, key, value)

        await self.session.flush()
        await self.session.refresh(rss_item)
        return rss_item
