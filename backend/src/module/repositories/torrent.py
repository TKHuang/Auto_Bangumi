from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, delete, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.torrent import Torrent, TorrentState


class TorrentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_hash(self, hash: str) -> Optional[Torrent]:
        stmt = select(Torrent).where(Torrent.hash == hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_hashes(self, hashes: list[str]) -> dict[str, Torrent]:
        if not hashes:
            return {}
        stmt = select(Torrent).where(Torrent.hash.in_(hashes))
        result = await self.session.execute(stmt)
        return {t.hash: t for t in result.scalars().all() if t.hash}

    async def create(self, data: dict) -> Torrent:
        torrent = Torrent(**data)
        self.session.add(torrent)
        await self.session.flush()
        await self.session.refresh(torrent)
        return torrent

    async def add_all_or_ignore(self, torrents: list[Torrent]) -> int:
        if not torrents:
            return 0
        
        values = []
        for t in torrents:
            downloaded = getattr(t, "downloaded", None)
            state = getattr(t, "state", None)
            val = {
                "bangumi_id": t.bangumi_id,
                "rss_id": t.rss_id,
                "name": t.name or "",
                "url": t.url or "",
                "homepage": getattr(t, "homepage", None),
                "downloaded": downloaded if downloaded is not None else False,
                "hash": t.hash,
                "pikpak_cloud_path": getattr(t, "pikpak_cloud_path", None),
                "state": state.value if isinstance(state, TorrentState) else TorrentState.PENDING.value,
            }
            values.append(val)

        stmt = sqlite_insert(Torrent).values(values)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["hash", "bangumi_id"]
        )
        result = await self.session.execute(stmt)
        return result.rowcount

    async def get_by_bangumi(self, bangumi_id: int) -> list[Torrent]:
        stmt = select(Torrent).where(Torrent.bangumi_id == bangumi_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_visible_by_bangumi(self, bangumi_id: int) -> list[Torrent]:
        stmt = select(Torrent).where(
            and_(
                Torrent.bangumi_id == bangumi_id,
                Torrent.state != TorrentState.EXCLUDED,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_rss(self, rss_id: int) -> list[Torrent]:
        stmt = select(Torrent).where(Torrent.rss_id == rss_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_visible_by_rss(self, rss_id: int) -> list[Torrent]:
        stmt = select(Torrent).where(
            and_(
                Torrent.rss_id == rss_id,
                Torrent.state != TorrentState.EXCLUDED,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def _unrenamed_base_stmt(self):
        return select(Torrent).where(
            and_(
                Torrent.renamed_at.is_(None),
                Torrent.state != TorrentState.EXCLUDED,
            )
        )

    async def get_unrenamed(self) -> list[Torrent]:
        result = await self.session.execute(self._unrenamed_base_stmt())
        return list(result.scalars().all())

    async def mark_renamed(
        self, id: int, file_count: int, cloud_path: Optional[str] = None
    ) -> Torrent:
        torrent = await self.session.get(Torrent, id)
        if not torrent:
            raise ValueError(f"Torrent with id {id} not found")

        torrent.renamed_at = datetime.now(timezone.utc)
        torrent.renamed_file_count = file_count
        if cloud_path:
            torrent.pikpak_cloud_path = cloud_path

        await self.session.flush()
        await self.session.refresh(torrent)
        return torrent

    async def check_new_by_hash(
        self, hashes: list[Optional[str]], bangumi_id: int
    ) -> list[Optional[str]]:
        existing_stmt = select(Torrent.hash).where(
            and_(
                Torrent.hash.in_([h for h in hashes if h is not None]),
                Torrent.bangumi_id == bangumi_id,
            )
        )
        result = await self.session.execute(existing_stmt)
        existing_hashes = set(result.scalars().all())
        
        new_hashes = []
        for h in hashes:
            if h is None:
                new_hashes.append(h)
            elif h not in existing_hashes:
                new_hashes.append(h)
        
        return new_hashes

    async def clear_rename_status(self, bangumi_id: int, new_cloud_path: Optional[str] = None) -> None:
        values: dict = {
            "renamed_at": None,
            "renamed_file_count": None,
        }
        if new_cloud_path is not None:
            values["pikpak_cloud_path"] = new_cloud_path
        stmt = (
            update(Torrent)
            .where(
                Torrent.bangumi_id == bangumi_id,
                Torrent.state != TorrentState.EXCLUDED,
            )
            .values(**values)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def mark_downloaded(self, id: int) -> None:
        torrent = await self.session.get(Torrent, id)
        if not torrent:
            raise ValueError(f"Torrent with id {id} not found")
        
        torrent.downloaded = True
        await self.session.flush()

    async def get_by_id(self, id: int) -> Optional[Torrent]:
        return await self.session.get(Torrent, id)

    async def get_all(self) -> list[Torrent]:
        stmt = select(Torrent)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_bangumi_with_homepage(self, bangumi_id: int) -> Optional[Torrent]:
        stmt = select(Torrent).where(
            and_(
                Torrent.bangumi_id == bangumi_id,
                Torrent.homepage.is_not(None),
                Torrent.homepage != "",
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_unrenamed_hashes(self) -> set[str]:
        result = await self.session.execute(self._unrenamed_base_stmt())
        torrents = result.scalars().all()
        return {t.hash.lower() for t in torrents if t.hash}

    async def mark_downloaded_by_hash(self, hash: str, bangumi_id: int, save_path: Optional[str] = None) -> int:
        values: dict = {"downloaded": True}
        if save_path is not None:
            values["pikpak_cloud_path"] = save_path
        stmt = (
            update(Torrent)
            .where(Torrent.hash == hash, Torrent.bangumi_id == bangumi_id)
            .values(**values)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def delete_by_bangumi(self, bangumi_id: int) -> None:
        stmt = delete(Torrent).where(Torrent.bangumi_id == bangumi_id)
        await self.session.execute(stmt)
        await self.session.flush()

    async def delete_by_rss(self, rss_id: int) -> None:
        stmt = delete(Torrent).where(Torrent.rss_id == rss_id)
        await self.session.execute(stmt)
        await self.session.flush()

    async def delete_all(self) -> None:
        stmt = delete(Torrent)
        await self.session.execute(stmt)
        await self.session.flush()
