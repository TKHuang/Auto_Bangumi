from typing import Optional

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from module.domain.models.bangumi import Bangumi
from module.repositories.exceptions import ConcurrentModificationError


class BangumiRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: int) -> Optional[Bangumi]:
        stmt = (
            select(Bangumi)
            .options(selectinload(Bangumi.series))
            .where(Bangumi.id == id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, include_deleted: bool = False) -> list[Bangumi]:
        stmt = select(Bangumi).options(selectinload(Bangumi.series))
        if not include_deleted:
            stmt = stmt.where(Bangumi.deleted == False)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # Fields that map to Series or path_override (not direct Bangumi columns).
    # These are translated during update; legacy callers may still pass them.
    _SERIES_MAPPED_KEYS: frozenset[str] = frozenset(
        {"official_title", "season", "year", "poster_link", "save_path"}
    )
    # Parser intermediates that are silently dropped (not stored anywhere).
    _DROPPED_INTERMEDIATES: frozenset[str] = frozenset({"title_raw", "season_raw"})

    def _apply_update_dict(self, bangumi: "Bangumi", data: dict) -> None:
        """Apply an update dict to a Bangumi ORM instance.

        Mapping:
        - save_path      → path_override
        - poster_link    → series.poster_url  (if series is loaded)
        - official_title → series.canonical_title  (if series is loaded)
        - season         → series.season  (if series is loaded)
        - year           → series.year  (if series is loaded)
        - title_raw, season_raw → silently dropped (parser intermediates)
        - everything else → setattr if column exists
        """
        for key, value in data.items():
            if key in ("id", "version"):
                continue
            if key == "save_path":
                bangumi.path_override = value
            elif key == "poster_link":
                if bangumi.series is not None:
                    bangumi.series.poster_url = value
            elif key == "official_title":
                if bangumi.series is not None:
                    bangumi.series.canonical_title = value
            elif key == "season":
                if bangumi.series is not None and value is not None:
                    bangumi.series.season = int(value)
            elif key == "year":
                if bangumi.series is not None and value is not None:
                    bangumi.series.year = int(value)
            elif key in self._DROPPED_INTERMEDIATES:
                pass
            elif hasattr(bangumi, key):
                setattr(bangumi, key, value)

    async def create(self, data: dict) -> Bangumi:
        if "group_name" in data and not data["group_name"]:
            data["group_name"] = "Unknown"
        # Drop legacy keys that no longer exist as Bangumi columns.
        _drop = self._SERIES_MAPPED_KEYS | self._DROPPED_INTERMEDIATES
        filtered = {k: v for k, v in data.items() if k not in _drop}
        bangumi = Bangumi(**filtered)
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

        self._apply_update_dict(bangumi, data)

        await self.session.flush()
        await self.session.refresh(bangumi)
        return bangumi

    async def soft_delete(self, id: int) -> None:
        bangumi = await self.get_by_id(id)
        if not bangumi:
            raise ValueError(f"Bangumi with id {id} not found")
        
        bangumi.deleted = True
        await self.session.flush()

    async def get_active(self, enabled_only: bool = False) -> list[Bangumi]:
        """List bangumi that are not soft-deleted and not pending review.

        When ``enabled_only`` is True, also excludes rows with ``active=False``.
        Processing paths (RSS torrent matching, rename) must pass
        ``enabled_only=True`` so disabled subscriptions don't swallow torrents
        (spec §10.2). The UI listing (``/bangumi/get/all``) keeps the default
        so users can see and re-enable disabled rows.
        """
        conditions = [
            Bangumi.deleted == False,
            Bangumi.pending_review == False,
        ]
        if enabled_only:
            conditions.append(Bangumi.active == True)
        stmt = (
            select(Bangumi)
            .options(selectinload(Bangumi.series))
            .where(and_(*conditions))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_review(self, rss_id: Optional[int] = None) -> list[Bangumi]:
        stmt = (
            select(Bangumi)
            .options(selectinload(Bangumi.series))
            .where(
                and_(
                    Bangumi.deleted == False,
                    Bangumi.pending_review == True,
                )
            )
        )
        if rss_id is not None:
            stmt = stmt.where(Bangumi.rss_id == rss_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_rss(self, rss_id: int) -> list[Bangumi]:
        stmt = (
            select(Bangumi)
            .options(selectinload(Bangumi.series))
            .where(Bangumi.rss_id == rss_id)
        )
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

    async def find_by_any_rss_link(self, rss_links: list[str]) -> Optional[Bangumi]:
        for rss_link in rss_links:
            if not rss_link:
                continue
            stmt = (
                select(Bangumi)
                .options(selectinload(Bangumi.series))
                .where(and_(func.instr(Bangumi.rss_link, rss_link) > 0, Bangumi.deleted == False))
                .order_by(Bangumi.id)
                .limit(1)
            )
            result = await self.session.execute(stmt)
            found = result.scalars().first()
            if found:
                return found
        return None

    async def match_poster(self, bangumi_name: str) -> str:
        """Return poster URL for the first bangumi whose series canonical_title
        appears within bangumi_name.  Queries via the series join.
        """
        from module.domain.models.series import Series as SeriesModel
        stmt = (
            select(Bangumi)
            .options(selectinload(Bangumi.series))
            .join(SeriesModel, Bangumi.series_id == SeriesModel.id)
            .where(func.instr(bangumi_name, SeriesModel.canonical_title) > 0)
        )
        result = await self.session.execute(stmt)
        data = result.scalar_one_or_none()
        if data is None:
            return ""
        return data.series.poster_url if data.series is not None else ""

    async def match_torrent(self, torrent_name: str) -> Optional[Bangumi]:
        """Return the first active bangumi whose series canonical_title
        appears within torrent_name.  title_raw was dropped in 0008; we fall
        back to matching on the series canonical title as the closest proxy.

        Ties (multiple rules whose canonical_title appears in the name) are
        broken by descending title length (most specific first) then ascending
        bangumi id, so the result is deterministic across requests.
        """
        from module.domain.models.series import Series as SeriesModel
        stmt = (
            select(Bangumi)
            .options(selectinload(Bangumi.series))
            .join(SeriesModel, Bangumi.series_id == SeriesModel.id)
            .where(
                and_(
                    func.instr(torrent_name, SeriesModel.canonical_title) > 0,
                    Bangumi.deleted == False,
                    Bangumi.pending_review == False,
                )
            )
            .order_by(func.length(SeriesModel.canonical_title).desc(), Bangumi.id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

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

    async def delete_one(self, id: int, gc_series: bool = True) -> bool:
        """Delete a bangumi (and its torrents) by id.

        Args:
            id: bangumi to remove.
            gc_series: when True (default — the user-initiated delete path),
                also drop the linked Series row if no remaining bangumi
                references it (mirrors RSS cascade GC). Pass False from the
                recreate-on-resubscribe path because the caller will
                immediately re-insert a new bangumi pointing at the SAME
                series — GC'ing the row mid-flight would FK-violate the
                follow-up insert.
        """
        from module.domain.models.torrent import Torrent
        target = await self.session.get(Bangumi, id)
        series_id = target.series_id if target is not None else None

        stmt = delete(Torrent).where(Torrent.bangumi_id == id)
        await self.session.execute(stmt)
        stmt = delete(Bangumi).where(Bangumi.id == id)
        result = await self.session.execute(stmt)
        await self.session.flush()

        if gc_series and result.rowcount > 0 and series_id is not None:
            await self._gc_orphan_series([series_id])

        return result.rowcount > 0

    async def delete_many(self, ids: list[int], gc_series: bool = True) -> int:
        """Delete multiple bangumi rows; see ``delete_one`` for ``gc_series``."""
        if not ids:
            return 0
        from module.domain.models.torrent import Torrent
        affected_series = await self.session.execute(
            select(Bangumi.series_id).where(Bangumi.id.in_(ids))
        )
        series_ids = {sid for sid, in affected_series.all() if sid is not None}

        await self.session.execute(delete(Torrent).where(Torrent.bangumi_id.in_(ids)))
        result = await self.session.execute(delete(Bangumi).where(Bangumi.id.in_(ids)))
        await self.session.flush()

        if gc_series and result.rowcount > 0 and series_ids:
            await self._gc_orphan_series(list(series_ids))

        return result.rowcount

    async def _gc_orphan_series(self, series_ids: list[int]) -> int:
        """Delete Series rows that no remaining Bangumi references.

        Series rows are created opportunistically during RSS subscription and
        never receive their own delete endpoint. When the last bangumi
        pointing at a series is removed (whether via the user's "Delete rule"
        action or a manual cleanup script), leaving the series row behind
        means the next subscription with the same Mikan id silently re-binds
        to a stale row whose ``root_path`` may already be obsolete.
        """
        from module.domain.models.series import Series

        if not series_ids:
            return 0

        # Keep the series alive while ANY bangumi row still references it
        # (including soft-deleted ones — un-disable would otherwise break).
        still_referenced = await self.session.execute(
            select(Bangumi.series_id).where(Bangumi.series_id.in_(series_ids))
        )
        keep = {sid for sid, in still_referenced.all() if sid is not None}
        orphans = [sid for sid in series_ids if sid not in keep]

        if not orphans:
            return 0

        result = await self.session.execute(
            delete(Series).where(Series.id.in_(orphans))
        )
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
        self._apply_update_dict(bangumi, data)
        await self.session.flush()
        return True

    async def get_by_series_and_subgroup(
        self, series_id: int, mikan_subgroup_id: int
    ) -> Optional[Bangumi]:
        """Identity lookup for Mikan-sourced bangumi (spec §6.2 partial UNIQUE)."""
        stmt = select(Bangumi).where(
            and_(
                Bangumi.series_id == series_id,
                Bangumi.mikan_subgroup_id == mikan_subgroup_id,
                Bangumi.deleted == False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_series_and_rss(
        self, series_id: int, rss_id: Optional[int]
    ) -> Optional[Bangumi]:
        """Fallback identity for non-Mikan bangumi: (series_id, rss_id) when
        mikan_subgroup_id IS NULL. rss_id None never matches (no fallback key).
        """
        if rss_id is None:
            return None
        stmt = select(Bangumi).where(
            and_(
                Bangumi.series_id == series_id,
                Bangumi.rss_id == rss_id,
                Bangumi.mikan_subgroup_id.is_(None),
                Bangumi.deleted == False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_mikan_bangumi_url(
        self, mikan_bangumi_url: str
    ) -> Optional[Bangumi]:
        """Short-circuit lookup for aggregate-RSS ingestion: once an operator
        resolves a bangumi via the pending queue (binding the canonical Mikan
        bangumi-page URL), future episodes whose Mikan page maps to the same
        URL bind automatically. Returns None when no undeleted row matches.
        """
        if not mikan_bangumi_url:
            return None
        stmt = (
            select(Bangumi)
            .options(selectinload(Bangumi.series))
            .where(
                and_(
                    Bangumi.mikan_bangumi_url == mikan_bangumi_url,
                    Bangumi.deleted == False,
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_series(self, series_id: int) -> list[Bangumi]:
        stmt = select(Bangumi).where(
            and_(Bangumi.series_id == series_id, Bangumi.deleted == False)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def deactivate_siblings_in_series(
        self, series_id: int, except_bangumi_id: int
    ) -> int:
        """Set active=false on all undeleted siblings of `except_bangumi_id`
        within the same series. Returns the number of rows updated."""
        stmt = (
            update(Bangumi)
            .where(
                Bangumi.series_id == series_id,
                Bangumi.id != except_bangumi_id,
                Bangumi.deleted == False,
                Bangumi.active == True,
            )
            .values(active=False)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount
