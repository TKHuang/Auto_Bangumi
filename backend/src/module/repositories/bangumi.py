from typing import Optional

from sqlalchemy import and_, delete, func, select, update
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

    async def find_by_official_title(self, official_title: str) -> Optional[Bangumi]:
        stmt = select(Bangumi).where(
            and_(Bangumi.official_title == official_title, Bangumi.deleted == False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_any_rss_link(self, rss_links: list[str]) -> Optional[Bangumi]:
        for rss_link in rss_links:
            if not rss_link:
                continue
            stmt = select(Bangumi).where(
                and_(func.instr(Bangumi.rss_link, rss_link) > 0, Bangumi.deleted == False)
            )
            result = await self.session.execute(stmt)
            found = result.scalar_one_or_none()
            if found:
                return found
        return None

    async def match_poster(self, bangumi_name: str) -> str:
        stmt = select(Bangumi).where(func.instr(bangumi_name, Bangumi.official_title) > 0)
        result = await self.session.execute(stmt)
        data = result.scalar_one_or_none()
        return data.poster_link if data else ""

    async def match_torrent(self, torrent_name: str) -> Optional[Bangumi]:
        stmt = select(Bangumi).where(
            and_(
                func.instr(torrent_name, Bangumi.title_raw) > 0,
                Bangumi.deleted == False,
                Bangumi.pending_review == False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_pending_by_rss_id(self, rss_id: int) -> int:
        stmt = select(func.count()).select_from(Bangumi).where(
            and_(Bangumi.rss_id == rss_id, Bangumi.pending_review == True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def count_active_by_rss_id(self, rss_id: int) -> int:
        stmt = select(func.count()).select_from(Bangumi).where(
            and_(Bangumi.rss_id == rss_id, Bangumi.pending_review == False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def activate_pending(self, bangumi_id: int, filter_value: Optional[str] = None) -> tuple[bool, str]:
        bangumi = await self.get_by_id(bangumi_id)
        if not bangumi:
            return False, "Bangumi not found"
        if not bangumi.pending_review:
            return False, "Bangumi is not pending review"
        bangumi.pending_review = False
        bangumi.global_filter_matches = None
        if filter_value is not None:
            bangumi.filter = filter_value
        await self.session.flush()
        return True, "Bangumi activated successfully"

    async def update_pending_review(self, bangumi_id: int, pending: bool, global_filter_matches: Optional[str] = None) -> bool:
        bangumi = await self.get_by_id(bangumi_id)
        if not bangumi:
            return False
        bangumi.pending_review = pending
        if pending and global_filter_matches:
            bangumi.global_filter_matches = global_filter_matches
        elif not pending:
            bangumi.global_filter_matches = None
        await self.session.flush()
        return True

    async def delete_one(self, id: int) -> bool:
        from module.domain.models.torrent import Torrent
        stmt = delete(Torrent).where(Torrent.bangumi_id == id)
        await self.session.execute(stmt)
        stmt = delete(Bangumi).where(Bangumi.id == id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def delete_many(self, ids: list[int]) -> int:
        if not ids:
            return 0
        from module.domain.models.torrent import Torrent
        await self.session.execute(delete(Torrent).where(Torrent.bangumi_id.in_(ids)))
        result = await self.session.execute(delete(Bangumi).where(Bangumi.id.in_(ids)))
        await self.session.flush()
        return result.rowcount

    async def disable_many(self, ids: list[int]) -> int:
        if not ids:
            return 0
        stmt = update(Bangumi).where(Bangumi.id.in_(ids)).values(deleted=True)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def delete_all(self) -> None:
        from module.domain.models.torrent import Torrent
        await self.session.execute(delete(Torrent))
        await self.session.execute(delete(Bangumi))
        await self.session.flush()

    async def backfill_rss_id(self, rss_id: int, rss_url: str) -> int:
        stmt = select(Bangumi).where(
            and_(Bangumi.rss_id.is_(None), func.instr(Bangumi.rss_link, rss_url) > 0)
        )
        result = await self.session.execute(stmt)
        bangumi_list = list(result.scalars().all())
        for b in bangumi_list:
            b.rss_id = rss_id
        await self.session.flush()
        return len(bangumi_list)

    async def update_simple(self, id: int, data: dict) -> bool:
        bangumi = await self.get_by_id(id)
        if not bangumi:
            return False
        for key, value in data.items():
            if hasattr(bangumi, key) and key not in ["id", "version"]:
                setattr(bangumi, key, value)
        await self.session.flush()
        return True
