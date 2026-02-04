from typing import Optional

from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from zen_bangumi.domain.models.bangumi import Bangumi
from zen_bangumi.repositories.exceptions import ConcurrentModificationError


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

    async def get_all(self, filters: Optional[dict] = None) -> list[Bangumi]:
        stmt = select(Bangumi).where(Bangumi.deleted == False)
        if filters:
            for key, value in filters.items():
                if hasattr(Bangumi, key):
                    stmt = stmt.where(getattr(Bangumi, key) == value)
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

        bangumi.version += 1
        await self.session.flush()
        await self.session.refresh(bangumi)
        return bangumi

    async def delete(self, id: int) -> None:
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

    async def get_pending_review(self) -> list[Bangumi]:
        stmt = select(Bangumi).where(
            and_(
                Bangumi.deleted == False,
                Bangumi.pending_review == True,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def match_torrent(self, parsed_info: dict) -> Optional[Bangumi]:
        torrent_name = parsed_info.get("name", "")
        if not torrent_name:
            return None

        stmt = select(Bangumi).where(
            and_(
                func.instr(torrent_name, Bangumi.title_raw) > 0,
                Bangumi.deleted == False,
                Bangumi.pending_review == False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
