from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from zen_bangumi.domain.models.torrent import Torrent


class TorrentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_hash(self, hash: str) -> Optional[Torrent]:
        stmt = select(Torrent).where(Torrent.hash == hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Torrent:
        torrent_hash = data.get("hash")
        
        if torrent_hash:
            existing = await self.get_by_hash(torrent_hash)
            if existing:
                return existing

        torrent = Torrent(**data)
        self.session.add(torrent)
        await self.session.flush()
        await self.session.refresh(torrent)
        return torrent

    async def get_unrenamed(self, bangumi_id: int) -> list[Torrent]:
        stmt = select(Torrent).where(
            and_(
                Torrent.bangumi_id == bangumi_id,
                Torrent.renamed_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_renamed(
        self, torrent_id: int, file_count: int, cloud_path: Optional[str] = None
    ) -> Torrent:
        torrent = await self.session.get(Torrent, torrent_id)
        if not torrent:
            raise ValueError(f"Torrent with id {torrent_id} not found")

        torrent.renamed_at = datetime.now(timezone.utc)
        torrent.renamed_file_count = file_count
        if cloud_path:
            torrent.pikpak_cloud_path = cloud_path

        await self.session.flush()
        await self.session.refresh(torrent)
        return torrent

    async def get_by_bangumi(self, bangumi_id: int) -> list[Torrent]:
        stmt = select(Torrent).where(Torrent.bangumi_id == bangumi_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
