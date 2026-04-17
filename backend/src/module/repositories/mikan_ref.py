"""MikanEpisodeRefRepository - Mikan page scrape cache with health metrics.

upsert() is the single write path. parse_status='ok' clears last_error.
Health queries feed the Dashboard Mikan banner.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.mikan_ref import MikanEpisodeRef


class MikanEpisodeRefRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, info_hash: str) -> Optional[MikanEpisodeRef]:
        return await self.session.get(MikanEpisodeRef, info_hash)

    async def upsert(
        self,
        info_hash: str,
        parse_status: str,
        mikan_bangumi_id: Optional[int] = None,
        mikan_subgroup_id: Optional[int] = None,
        canonical_title: Optional[str] = None,
        poster_url: Optional[str] = None,
        last_error: Optional[str] = None,
    ) -> MikanEpisodeRef:
        """Create or update a cache row. Increments attempt_count each call."""
        existing = await self.get(info_hash)
        now = datetime.now(timezone.utc)

        if existing is None:
            ref = MikanEpisodeRef(
                info_hash=info_hash,
                parse_status=parse_status,
                mikan_bangumi_id=mikan_bangumi_id,
                mikan_subgroup_id=mikan_subgroup_id,
                canonical_title=canonical_title,
                poster_url=poster_url,
                last_error=last_error,
                fetched_at=now,
                attempt_count=1,
            )
            self.session.add(ref)
            await self.session.flush()
            await self.session.refresh(ref)
            return ref

        existing.parse_status = parse_status
        existing.fetched_at = now
        existing.attempt_count = existing.attempt_count + 1
        if parse_status == "ok":
            existing.mikan_bangumi_id = mikan_bangumi_id
            existing.mikan_subgroup_id = mikan_subgroup_id
            existing.canonical_title = canonical_title
            existing.poster_url = poster_url
            existing.last_error = None
        else:
            existing.last_error = last_error
        await self.session.flush()
        await self.session.refresh(existing)
        return existing

    async def last_success_at(self) -> Optional[datetime]:
        stmt = (
            select(func.max(MikanEpisodeRef.fetched_at))
            .where(MikanEpisodeRef.parse_status == "ok")
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def consecutive_failures(self) -> int:
        """Count failed entries since the most recent success.

        Used for Mikan health 'down' detection (spec §12.2).
        """
        last_ok = await self.last_success_at()
        stmt = select(func.count()).where(MikanEpisodeRef.parse_status == "failed")
        if last_ok is not None:
            stmt = stmt.where(MikanEpisodeRef.fetched_at > last_ok)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())
