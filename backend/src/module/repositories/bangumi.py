from typing import Optional

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.bangumi import Bangumi
from module.repositories.exceptions import ConcurrentModificationError


class BangumiRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: int) -> Optional[Bangumi]:
        result = await self.session.get(Bangumi, id)
        return result

    async def get_by_composite_key(
        self, official_title: str, season: int, group_name: str
    ) -> Optional[Bangumi]:
        normalized_group = group_name if group_name else "Unknown"
        stmt = select(Bangumi).where(
            and_(
                Bangumi.official_title == official_title,
                Bangumi.season == season,
                Bangumi.group_name == normalized_group,
                Bangumi.deleted == False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, include_deleted: bool = False) -> list[Bangumi]:
        stmt = select(Bangumi)
        if not include_deleted:
            stmt = stmt.where(Bangumi.deleted == False)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: dict) -> Bangumi:
        if "group_name" in data and not data["group_name"]:
            data["group_name"] = "Unknown"

        official_title = data.get("official_title")
        season = data.get("season", 1)
        group_name = data.get("group_name", "Unknown")

        existing = await self.get_by_composite_key(official_title, season, group_name)
        if existing:
            raise ValueError(
                f"Bangumi with composite key ({official_title}, {season}, {group_name}) already exists"
            )

        bangumi = Bangumi(**data)
        self.session.add(bangumi)
        await self.session.flush()
        await self.session.refresh(bangumi)
        return bangumi

    async def update(
        self, id: int, data: dict, expected_version: int
    ) -> Bangumi:
        bangumi = await self.get_by_id(id)
        if not bangumi:
            raise ValueError(f"Bangumi with id {id} not found")

        if bangumi.version != expected_version:
            raise ConcurrentModificationError("Bangumi", id, expected_version)

        for key, value in data.items():
            if hasattr(bangumi, key) and key not in ["id", "version"]:
                setattr(bangumi, key, value)

        await self.session.flush()
        await self.session.refresh(bangumi)
        return bangumi

    async def soft_delete(self, id: int) -> None:
        bangumi = await self.get_by_id(id)
        if not bangumi:
            raise ValueError(f"Bangumi with id {id} not found")
        
        bangumi.deleted = True
        await self.session.flush()

    async def get_active(self) -> list[Bangumi]:
        stmt = select(Bangumi).where(
            and_(
                Bangumi.deleted == False,
                Bangumi.pending_review == False,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_review(self, rss_id: Optional[int] = None) -> list[Bangumi]:
        stmt = select(Bangumi).where(
            and_(
                Bangumi.deleted == False,
                Bangumi.pending_review == True,
            )
        )
        if rss_id is not None:
            stmt = stmt.where(Bangumi.rss_id == rss_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_rss(self, rss_id: int) -> list[Bangumi]:
        stmt = select(Bangumi).where(Bangumi.rss_id == rss_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def enable(self, id: int) -> None:
        bangumi = await self.get_by_id(id)
        if not bangumi:
            raise ValueError(f"Bangumi with id {id} not found")
        
        bangumi.pending_review = False
        await self.session.flush()

    async def disable(self, id: int) -> None:
        bangumi = await self.get_by_id(id)
        if not bangumi:
            raise ValueError(f"Bangumi with id {id} not found")
        
        bangumi.pending_review = True
        await self.session.flush()

    async def reset_all(self) -> None:
        stmt = (
            update(Bangumi)
            .where(Bangumi.deleted == False)
            .values(added=False, eps_collect=False)
        )
        await self.session.execute(stmt)
        await self.session.flush()
