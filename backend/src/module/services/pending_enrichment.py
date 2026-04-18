"""Service layer for pending_torrent_enrichment queue.

The queue holds torrents we couldn't resolve to a Mikan ID at fetch time.
A scheduled drain job re-tries each entry; success removes the row,
failure increments attempt_count + records last_error.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.pending_enrichment import PendingTorrentEnrichment


class PendingEnrichmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue(
        self,
        *,
        info_hash: str,
        raw_name: str,
        homepage: Optional[str],
        url: str,
        rss_id: int,
        published_at: Optional[datetime],
    ) -> None:
        """Insert or ignore (info_hash is PK). Idempotent on duplicate hash."""
        stmt = sqlite_insert(PendingTorrentEnrichment).values(
            info_hash=info_hash,
            raw_name=raw_name,
            homepage=homepage or "",
            url=url,
            rss_id=rss_id,
            published_at=published_at,
            first_seen_at=datetime.now(timezone.utc),
            attempt_count=0,
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["info_hash"])
        await self.session.execute(stmt)

    async def list_pending(self) -> list[PendingTorrentEnrichment]:
        result = await self.session.execute(
            select(PendingTorrentEnrichment).order_by(
                PendingTorrentEnrichment.first_seen_at
            )
        )
        return list(result.scalars().all())

    async def mark_attempted(self, info_hash: str, *, error: str) -> None:
        await self.session.execute(
            update(PendingTorrentEnrichment)
            .where(PendingTorrentEnrichment.info_hash == info_hash)
            .values(
                attempt_count=PendingTorrentEnrichment.attempt_count + 1,
                last_error=error,
                last_attempt_at=datetime.now(timezone.utc),
            )
        )

    async def remove(self, info_hash: str) -> None:
        await self.session.execute(
            delete(PendingTorrentEnrichment).where(
                PendingTorrentEnrichment.info_hash == info_hash
            )
        )
