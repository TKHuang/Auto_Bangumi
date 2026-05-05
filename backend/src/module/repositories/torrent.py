from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, delete, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.torrent import (
    RenameStatus,
    Torrent,
    TorrentState,
    normalize_hash,
)


class TorrentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _norm(value: Optional[str]) -> Optional[str]:
        return normalize_hash(value)

    @staticmethod
    def _norm_list(values: list[Optional[str]]) -> list[str]:
        out: list[str] = []
        for v in values:
            n = normalize_hash(v)
            if n:
                out.append(n)
        return out

    def _preferred_hash_ordering(self):
        return (
            Torrent.pikpak_cloud_path.is_not(None).desc(),
            (Torrent.state != TorrentState.EXCLUDED).desc(),
            Torrent.downloaded.desc(),
            Torrent.updated_at.desc(),
            Torrent.id.desc(),
        )

    @staticmethod
    def _uses_unbound_hash_index(value: dict) -> bool:
        return value.get("bangumi_id") is None and value.get("hash") is not None

    @staticmethod
    def _with_ignore_conflict_target(stmt, *, unbound_hash: bool):
        if unbound_hash:
            return stmt.on_conflict_do_nothing(
                index_elements=["hash"],
                index_where=and_(
                    Torrent.hash.is_not(None),
                    Torrent.bangumi_id.is_(None),
                ),
            )
        return stmt.on_conflict_do_nothing(
            index_elements=["hash", "bangumi_id"]
        )

    async def _execute_insert_ignore(
        self, values: list[dict], *, unbound_hash: bool
    ) -> int:
        if not values:
            return 0
        stmt = sqlite_insert(Torrent).values(values)
        stmt = self._with_ignore_conflict_target(
            stmt, unbound_hash=unbound_hash
        )
        result = await self.session.execute(stmt)
        return result.rowcount if result.rowcount is not None else 0

    async def _execute_insert_ignore_batches(self, values: list[dict]) -> int:
        inserted = 0
        batch: list[dict] = []
        batch_unbound_hash: Optional[bool] = None

        for value in values:
            unbound_hash = self._uses_unbound_hash_index(value)
            if batch and unbound_hash != batch_unbound_hash:
                inserted += await self._execute_insert_ignore(
                    batch,
                    unbound_hash=bool(batch_unbound_hash),
                )
                batch = []
            batch.append(value)
            batch_unbound_hash = unbound_hash

        if batch:
            inserted += await self._execute_insert_ignore(
                batch,
                unbound_hash=bool(batch_unbound_hash),
            )
        return inserted

    async def get_by_hash(self, hash: str) -> Optional[Torrent]:
        normalized = self._norm(hash)
        if not normalized:
            return None
        stmt = (
            select(Torrent)
            .where(Torrent.hash == normalized)
            .order_by(*self._preferred_hash_ordering())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_hashes(self, hashes: list[str]) -> dict[str, Torrent]:
        normalized = self._norm_list(hashes)
        if not normalized:
            return {}
        stmt = (
            select(Torrent)
            .where(Torrent.hash.in_(normalized))
            .order_by(Torrent.hash, *self._preferred_hash_ordering())
        )
        result = await self.session.execute(stmt)
        torrents_by_hash: dict[str, Torrent] = {}
        for torrent in result.scalars().all():
            if torrent.hash and torrent.hash not in torrents_by_hash:
                torrents_by_hash[torrent.hash] = torrent
        return torrents_by_hash

    async def create(self, data: dict) -> Torrent:
        torrent = Torrent(**data)
        self.session.add(torrent)
        await self.session.flush()
        await self.session.refresh(torrent)
        return torrent

    async def create_or_ignore(self, data: dict) -> bool:
        values = {
            "bangumi_id": data["bangumi_id"],
            "rss_id": data["rss_id"],
            "name": data.get("name") or "",
            "url": data.get("url") or "",
            "homepage": data.get("homepage"),
            "hash": self._norm(data.get("hash")),
            "state": data.get("state", TorrentState.PENDING.value),
            "downloaded": data.get("downloaded", False),
            "renamed_at": data.get("renamed_at"),
            "renamed_file_count": data.get("renamed_file_count"),
            "pikpak_cloud_path": data.get("pikpak_cloud_path"),
            "pikpak_task_id": data.get("pikpak_task_id"),
            "mikan_bangumi_id": data.get("mikan_bangumi_id"),
            "mikan_subgroup_id": data.get("mikan_subgroup_id"),
        }
        inserted = await self._execute_insert_ignore(
            [values],
            unbound_hash=self._uses_unbound_hash_index(values),
        )
        return inserted > 0

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
                "hash": self._norm(t.hash),
                "pikpak_cloud_path": getattr(t, "pikpak_cloud_path", None),
                "state": state.value if isinstance(state, TorrentState) else TorrentState.PENDING.value,
            }
            values.append(val)

        return await self._execute_insert_ignore_batches(values)

    async def exclude_hashes(
        self, hashes: list[str], bangumi_id: int, rss_id: Optional[int] = None
    ) -> int:
        excluded_hashes = list(dict.fromkeys(self._norm_list(hashes)))
        if not excluded_hashes:
            return 0

        update_stmt = (
            update(Torrent)
            .where(
                Torrent.bangumi_id == bangumi_id,
                Torrent.hash.in_(excluded_hashes),
            )
            .values(downloaded=True, state=TorrentState.EXCLUDED)
        )
        update_result = await self.session.execute(update_stmt)

        existing_stmt = select(Torrent.hash).where(
            Torrent.bangumi_id == bangumi_id,
            Torrent.hash.in_(excluded_hashes),
        )
        existing_result = await self.session.execute(existing_stmt)
        existing_hashes = set(existing_result.scalars().all())

        missing_torrents = [
            Torrent(
                name="",
                url="",
                hash=hash_value,
                bangumi_id=bangumi_id,
                rss_id=rss_id,
                downloaded=True,
                state=TorrentState.EXCLUDED,
            )
            for hash_value in excluded_hashes
            if hash_value not in existing_hashes
        ]
        inserted_count = await self.add_all_or_ignore(missing_torrents)
        await self.session.flush()
        return update_result.rowcount + inserted_count

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
        # Conflicts are user-actionable (see RenameStatus.CONFLICT) — they MUST
        # NOT be retried automatically, otherwise the renamer keeps hammering
        # the downloader for a name collision the user hasn't resolved yet and
        # the conflict status flips back to "unrenamed" forever.
        from module.domain.models.bangumi import Bangumi
        return (
            select(Torrent)
            .join(Bangumi, Bangumi.id == Torrent.bangumi_id)
            .where(
                and_(
                    Torrent.renamed_at.is_(None),
                    Torrent.state != TorrentState.EXCLUDED,
                    Torrent.rename_status != RenameStatus.CONFLICT,
                    Bangumi.active,
                    ~Bangumi.deleted,
                )
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
        torrent.rename_status = RenameStatus.DONE
        torrent.rename_conflict_target = None
        if cloud_path:
            torrent.pikpak_cloud_path = cloud_path

        await self.session.flush()
        await self.session.refresh(torrent)
        return torrent

    async def mark_rename_conflict(
        self, id: int, conflict_target: str
    ) -> None:
        """Record that the rename hit a name collision against ``conflict_target``.

        Leaves ``renamed_at`` NULL on purpose so the row doesn't pretend the
        physical file is named correctly. Sets ``rename_status=CONFLICT`` so
        ``_unrenamed_base_stmt`` skips it on the next cron tick — manual
        intervention is required (delete one of the duplicates, change the
        offset/title, then call ``clear_rename_conflict``).
        """
        torrent = await self.session.get(Torrent, id)
        if not torrent:
            raise ValueError(f"Torrent with id {id} not found")
        torrent.rename_status = RenameStatus.CONFLICT
        torrent.rename_conflict_target = conflict_target
        await self.session.flush()

    async def clear_rename_conflict(self, id: int) -> None:
        """Move a CONFLICT row back to PENDING so the next rename tick retries."""
        torrent = await self.session.get(Torrent, id)
        if not torrent:
            raise ValueError(f"Torrent with id {id} not found")
        torrent.rename_status = RenameStatus.PENDING
        torrent.rename_conflict_target = None
        await self.session.flush()

    async def get_rename_conflicts(
        self, bangumi_id: Optional[int] = None
    ) -> list[Torrent]:
        """Return all torrents currently stuck on a rename name conflict.

        Optionally narrow to a single bangumi.
        """
        stmt = select(Torrent).where(
            Torrent.rename_status == RenameStatus.CONFLICT,
            Torrent.state != TorrentState.EXCLUDED,
        )
        if bangumi_id is not None:
            stmt = stmt.where(Torrent.bangumi_id == bangumi_id)
        stmt = stmt.order_by(Torrent.bangumi_id, Torrent.id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def check_new_by_hash(
        self, hashes: list[Optional[str]], bangumi_id: int
    ) -> list[Optional[str]]:
        normalized = [normalize_hash(h) for h in hashes]
        existing_stmt = select(Torrent.hash).where(
            and_(
                Torrent.hash.in_([h for h in normalized if h is not None]),
                Torrent.bangumi_id == bangumi_id,
            )
        )
        result = await self.session.execute(existing_stmt)
        existing_hashes = set(result.scalars().all())

        new_hashes: list[Optional[str]] = []
        for h in normalized:
            if h is None:
                new_hashes.append(h)
            elif h not in existing_hashes:
                new_hashes.append(h)
        
        return new_hashes

    async def clear_rename_status(self, bangumi_id: int, new_cloud_path: Optional[str] = None) -> None:
        # Resetting rename_status back to PENDING here is important: if a row
        # was stuck on CONFLICT because the user had two torrents producing
        # the same SxxExx, and the user then changed title/season/offset,
        # the new target paths probably don't collide anymore — let the
        # renamer retry instead of leaving the row in CONFLICT forever.
        values: dict = {
            "renamed_at": None,
            "renamed_file_count": None,
            "rename_status": RenameStatus.PENDING,
            "rename_conflict_target": None,
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
        stmt = (
            select(Torrent)
            .where(
                and_(
                    Torrent.bangumi_id == bangumi_id,
                    Torrent.homepage.is_not(None),
                    Torrent.homepage != "",
                )
            )
            .order_by(Torrent.id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_unrenamed_hashes(self) -> set[str]:
        result = await self.session.execute(self._unrenamed_base_stmt())
        torrents = result.scalars().all()
        return {t.hash.lower() for t in torrents if t.hash}

    async def mark_downloaded_by_hash(self, hash: str, bangumi_id: int, save_path: Optional[str] = None) -> int:
        normalized = self._norm(hash)
        values: dict = {"downloaded": True}
        if save_path is not None:
            values["pikpak_cloud_path"] = save_path
        stmt = (
            update(Torrent)
            .where(Torrent.hash == normalized, Torrent.bangumi_id == bangumi_id)
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

    async def backfill_mikan_ids(
        self,
        torrent_id: int,
        mikan_bangumi_id: Optional[int],
        mikan_subgroup_id: Optional[int],
    ) -> None:
        """One-shot setter used by scripts/backfill_series.py. Idempotent —
        overwrites whatever is currently stored."""
        stmt = (
            update(Torrent)
            .where(Torrent.id == torrent_id)
            .values(
                mikan_bangumi_id=mikan_bangumi_id,
                mikan_subgroup_id=mikan_subgroup_id,
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()
