"""PendingTorrentEnrichmentRepository - staging queue for blocked torrents.

The length of this queue is the Dashboard 'pending' count shown to the user.
enqueue() is idempotent per info_hash; mark_attempt() tracks retry history.
delete() is called on successful resolution.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.pending_enrichment import PendingTorrentEnrichment


class PendingTorrentEnrichmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def enqueue(
        self,
        info_hash: str,
        raw_name: str,
        homepage: str,
        url: str,
        rss_id: int,
        published_at: Optional[datetime] = None,
    ) -> PendingTorrentEnrichment:
        """Idempotent insert. Returns the existing row unchanged if info_hash already in queue."""
        existing = await self.get(info_hash)
        if existing is not None:
            return existing

        row = PendingTorrentEnrichment(
            info_hash=info_hash,
            raw_name=raw_name,
            homepage=homepage,
            url=url,
            rss_id=rss_id,
            published_at=published_at,
            first_seen_at=datetime.now(timezone.utc),
            attempt_count=0,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def get(self, info_hash: str) -> Optional[PendingTorrentEnrichment]:
        return await self.session.get(PendingTorrentEnrichment, info_hash)

    async def mark_attempt(self, info_hash: str, error: Optional[str]) -> None:
        row = await self.get(info_hash)
        if row is None:
            return
        row.attempt_count = row.attempt_count + 1
        row.last_error = error
        row.last_attempt_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def delete(self, info_hash: str) -> None:
        row = await self.get(info_hash)
        if row is not None:
            await self.session.delete(row)
            await self.session.flush()

    async def list_all(self, limit: int = 100) -> list[PendingTorrentEnrichment]:
        stmt = (
            select(PendingTorrentEnrichment)
            .order_by(PendingTorrentEnrichment.first_seen_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        stmt = select(func.count()).select_from(PendingTorrentEnrichment)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())
