from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, delete, func, select
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

    async def get_by_url(self, url: str) -> Optional[RSSItem]:
        stmt = select(RSSItem).where(RSSItem.url == url)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def enable(self, id: int) -> bool:
        rss = await self.get_by_id(id)
        if not rss:
            return False
        rss.enabled = True
        await self.session.flush()
        return True

    async def disable(self, id: int) -> bool:
        rss = await self.get_by_id(id)
        if not rss:
            return False
        rss.enabled = False
        await self.session.flush()
        return True

    async def get_aggregate(self) -> list[RSSItem]:
        stmt = select(RSSItem).where(
            and_(RSSItem.aggregate == True, RSSItem.enabled == True)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _collect_cascade_bangumi_ids(self, rss: RSSItem) -> list[int]:
        """Resolve bangumi IDs reachable via this RSS, direct and by URL fallback."""
        from module.domain.models.bangumi import Bangumi

        direct = select(Bangumi.id).where(Bangumi.rss_id == rss.id)
        fallback = select(Bangumi.id).where(
            and_(
                Bangumi.rss_id.is_(None),
                func.instr(Bangumi.rss_link, rss.url) > 0,
            )
        )
        ids: list[int] = []
        for stmt in (direct, fallback):
            result = await self.session.execute(stmt)
            ids.extend(result.scalars().all())
        return ids

    async def collect_cascade_hashes(self, id: int) -> list[str]:
        """Collect torrent hashes reachable from this RSS for file deletion.

        Includes torrents linked directly by ``rss_id`` and indirectly via
        descendant bangumi rows (both direct and rss_link fallback). Excluded
        sentinel rows (empty hash) are filtered out.
        """
        from module.domain.models.torrent import Torrent

        rss = await self.get_by_id(id)
        if not rss:
            return []

        bangumi_ids = await self._collect_cascade_bangumi_ids(rss)

        hash_stmt = select(Torrent.hash).where(
            and_(
                Torrent.hash.is_not(None),
                Torrent.hash != "",
                (Torrent.rss_id == id) | (Torrent.bangumi_id.in_(bangumi_ids)),
            )
        )
        result = await self.session.execute(hash_stmt)
        seen: set[str] = set()
        hashes: list[str] = []
        for raw in result.scalars():
            if raw and raw not in seen:
                seen.add(raw)
                hashes.append(raw)
        return hashes

    async def cascade_delete(self, id: int) -> bool:
        from module.domain.models.bangumi import Bangumi
        from module.domain.models.series import Series
        from module.domain.models.torrent import Torrent

        rss = await self.get_by_id(id)
        if not rss:
            return False

        await self.session.execute(
            delete(Torrent).where(Torrent.rss_id == id)
        )

        bangumi_ids = await self._collect_cascade_bangumi_ids(rss)
        affected_series_ids: set[int] = set()
        if bangumi_ids:
            series_rows = await self.session.execute(
                select(Bangumi.series_id).where(Bangumi.id.in_(bangumi_ids))
            )
            affected_series_ids = {
                row for row in series_rows.scalars().all() if row is not None
            }
        for bangumi_id in bangumi_ids:
            await self.session.execute(
                delete(Torrent).where(Torrent.bangumi_id == bangumi_id)
            )
            await self.session.execute(
                delete(Bangumi).where(Bangumi.id == bangumi_id)
            )

        # GC any series left without a surviving bangumi — otherwise deleted
        # RSS feeds leave phantom series rows that still own canonical titles
        # and break a "fresh" re-subscription.
        for series_id in affected_series_ids:
            remaining = await self.session.execute(
                select(func.count())
                .select_from(Bangumi)
                .where(Bangumi.series_id == series_id)
            )
            if remaining.scalar_one() == 0:
                await self.session.execute(
                    delete(Series).where(Series.id == series_id)
                )

        await self.session.execute(
            delete(RSSItem).where(RSSItem.id == id)
        )
        await self.session.flush()
        return True

    async def set_status(self, id: int, status: str) -> bool:
        rss = await self.get_by_id(id)
        if not rss:
            return False
        rss.last_status = status
        await self.session.flush()
        return True
