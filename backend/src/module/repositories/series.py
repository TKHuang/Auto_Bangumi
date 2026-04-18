"""SeriesRepository - identity resolution and CRUD for the series entity.

Identity lookup order (spec §6.4):
  Tier 1  get_by_mikan_id(mikan_bangumi_id)
  Tier 2  get_by_fallback(normalized_title, season, cour_part)
  Tier 3  find_possible_cross_source_merge(...) surfaces merge candidates
"""
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.series import Series


class SeriesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, series_id: int) -> Optional[Series]:
        return await self.session.get(Series, series_id)

    async def get_by_mikan_id(self, mikan_bangumi_id: int) -> Optional[Series]:
        stmt = select(Series).where(Series.mikan_bangumi_id == mikan_bangumi_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_fallback(
        self,
        normalized_title: str,
        season: int,
        cour_part: Optional[str],
    ) -> Optional[Series]:
        stmt = select(Series).where(
            and_(
                Series.normalized_title == normalized_title,
                Series.season == season,
                (Series.cour_part.is_(None) if cour_part is None
                 else Series.cour_part == cour_part),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_possible_cross_source_merge(
        self,
        normalized_title: str,
        season: int,
        cour_part: Optional[str],
    ) -> list[Series]:
        """Return Mikan-sourced series whose fallback key matches the input.

        Used when building a non-Mikan series to surface potential duplicates
        for manual user confirmation (spec §6.4 Tier 3).
        """
        stmt = select(Series).where(
            and_(
                Series.mikan_bangumi_id.is_not(None),
                Series.normalized_title == normalized_title,
                Series.season == season,
                (Series.cour_part.is_(None) if cour_part is None
                 else Series.cour_part == cour_part),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_canonical_title(self, title: str) -> Optional[Series]:
        """Case-insensitive lookup by canonical_title. Returns first match or None."""
        stmt = select(Series).where(
            func.lower(Series.canonical_title) == title.lower()
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create(self, data: dict) -> Series:
        series = Series(**data)
        self.session.add(series)
        await self.session.flush()
        await self.session.refresh(series)
        return series

    async def list_pending_review(self) -> list[Series]:
        stmt = select(Series).where(Series.pending_review == True)  # noqa: E712
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
