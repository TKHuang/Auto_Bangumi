"""Atomic merge transaction for two bangumi rows (spec §11.2).

Both `scripts/migrate_duplicates.py` and the future
`POST /api/v1/bangumi/merge` route (Plan 05) call this service. It is the
single chokepoint that:

  1. Verifies the (winner, loser) pair is not blacklisted (spec §11.4).
  2. Moves every torrent on `loser_id` to `winner_id`, dropping any that
     would violate the (hash, bangumi_id) UNIQUE on the winner side.
  3. Unions the loser's observed_groups into the winner's.
  4. Soft-deletes the loser (deleted=True, active=False).
  5. Writes a bangumi_merge_history row capturing full snapshots.

All work happens in the calling AsyncSession's existing transaction; the
caller decides when to commit.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.bangumi import Bangumi
from module.domain.models.merge_history import BangumiMergeHistory
from module.domain.models.torrent import Torrent, TorrentState
from module.repositories.bangumi import BangumiRepository
from module.repositories.merge_history import BangumiMergeHistoryRepository
from module.repositories.torrent import TorrentRepository


def _serialize_bangumi(b: Bangumi) -> dict:
    from pathlib import PurePosixPath
    _series = b.series
    _title = _series.canonical_title if _series is not None else None
    _season = _series.season if _series is not None else 1
    _root = _series.root_path if _series is not None else None
    _save_path = (
        b.path_override
        or (str(PurePosixPath(_root) / f"Season {_season}") if _root else None)
    )
    return {
        "id": b.id,
        "rss_id": b.rss_id,
        "official_title": _title,
        "season": _season,
        "group_name": b.group_name,
        "rss_link": b.rss_link,
        "save_path": _save_path,
        "series_id": b.series_id,
        "mikan_subgroup_id": b.mikan_subgroup_id,
        "active": b.active,
        "observed_groups": b.observed_groups,
        "deleted": b.deleted,
    }


def _serialize_torrent(t: Torrent) -> dict:
    return {
        "id": t.id,
        "bangumi_id": t.bangumi_id,
        "rss_id": t.rss_id,
        "name": t.name,
        "url": t.url,
        "hash": t.hash,
        "homepage": t.homepage,
        "downloaded": t.downloaded,
        "state": t.state.value if t.state is not None else None,
    }


def _union_groups(winner_json: Optional[str], loser_json: Optional[str]) -> str:
    """Merge two JSON-encoded group lists into a sorted union.

    Handles None, empty string, and malformed JSON gracefully — any
    undecodable input is treated as an empty list rather than crashing.
    """
    def _decode(raw: Optional[str]) -> list[str]:
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return []
        return [g for g in data if isinstance(g, str)]

    union = sorted(set(_decode(winner_json)) | set(_decode(loser_json)))
    return json.dumps(union, ensure_ascii=False)


class BangumiMergeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._bangumi_repo = BangumiRepository(session)
        self._torrent_repo = TorrentRepository(session)
        self._history_repo = BangumiMergeHistoryRepository(session)

    async def merge(
        self,
        *,
        winner_id: int,
        loser_id: int,
        merge_reason: str,
        merged_by: str,
    ) -> BangumiMergeHistory:
        """Atomically merge `loser_id` into `winner_id`.

        Returns the newly created BangumiMergeHistory row.
        Raises ValueError for any precondition violation.
        """
        # --- Prepare: validate preconditions ---
        if winner_id == loser_id:
            raise ValueError("winner_id and loser_id must differ")

        if await self._history_repo.is_pair_blacklisted(winner_id, loser_id):
            raise ValueError(
                f"pair ({winner_id}, {loser_id}) is blacklisted (spec §11.4)"
            )

        winner = await self._bangumi_repo.get_by_id(winner_id)
        if winner is None:
            raise ValueError(f"winner bangumi id={winner_id} not found")

        loser = await self._bangumi_repo.get_by_id(loser_id)
        if loser is None:
            raise ValueError(f"loser bangumi id={loser_id} not found")

        # --- Compute: snapshot + classify torrents ---
        loser_snapshot = _serialize_bangumi(loser)

        winner_torrents = await self._torrent_repo.get_by_bangumi(winner_id)
        winner_hashes: set[str] = {t.hash for t in winner_torrents if t.hash is not None}

        loser_torrents = await self._torrent_repo.get_by_bangumi(loser_id)

        moved: list[int] = []
        dropped: list[dict] = []

        # --- Execute: move or drop each loser torrent ---
        for t in loser_torrents:
            if t.hash is not None and t.hash in winner_hashes:
                dropped.append(_serialize_torrent(t))
                await self.session.delete(t)
            else:
                t.bangumi_id = winner_id
                moved.append(t.id)

        await self.session.flush()

        # Union observed_groups then soft-delete the loser.
        winner.observed_groups = _union_groups(
            winner.observed_groups, loser.observed_groups
        )
        loser.deleted = True
        loser.active = False

        await self.session.flush()

        # Write the audit row; caller commits.
        history = await self._history_repo.create(
            winner_id=winner_id,
            loser_id=loser_id,
            loser_snapshot=loser_snapshot,
            moved_torrent_ids=moved,
            dropped_torrents=dropped,
            merge_reason=merge_reason,
            merged_by=merged_by,
        )
        return history

    async def undo(
        self,
        *,
        history_id: int,
        undone_by: str,
    ) -> BangumiMergeHistory:
        """Reverse a previous merge by restoring the loser bangumi.

        Raises ValueError if the history row is missing or already undone.
        The caller is responsible for committing the session.
        """
        # --- Prepare: load and validate ---
        history = await self._history_repo.get_by_id(history_id)
        if history is None:
            raise ValueError(f"merge history id={history_id} not found")
        if history.undone_at is not None:
            raise ValueError("merge already undone")
        if history.winner_bangumi_id is None or history.loser_bangumi_id is None:
            raise ValueError("merge participant was deleted; undo unavailable")

        # Cascade guard (spec §11.5): refuse if a newer un-undone merge
        # references either participant — the user must undo the newer
        # merge first or the identity invariant breaks.
        blockers = await self._history_repo.find_cascade_blockers(
            history_id=history.id,
            winner_id=history.winner_bangumi_id,
            loser_id=history.loser_bangumi_id,
        )
        if blockers:
            raise ValueError(
                "cascade: newer un-undone merge(s) reference this pair "
                f"(ids={blockers}); undo the newer merge first"
            )

        loser = await self._bangumi_repo.get_by_id(history.loser_bangumi_id)
        if loser is None:
            raise ValueError(f"loser bangumi id={history.loser_bangumi_id} missing")

        # --- Execute: resurrect loser (inactive — user chooses to re-enable) ---
        loser.deleted = False
        loser.active = False

        # Move back torrents we had transferred to the winner.
        moved_ids: list[int] = json.loads(history.moved_torrent_ids or "[]")
        for tid in moved_ids:
            t = await self._torrent_repo.get_by_id(tid)
            if t is not None and t.bangumi_id == history.winner_bangumi_id:
                t.bangumi_id = history.loser_bangumi_id

        # Recreate torrents that were dropped (hash-conflict duplicates).
        dropped: list[dict] = json.loads(history.dropped_torrents or "[]")
        for t_dict in dropped:
            new_t = Torrent(
                bangumi_id=history.loser_bangumi_id,
                rss_id=t_dict.get("rss_id"),
                name=t_dict["name"],
                url=t_dict["url"],
                hash=t_dict["hash"],
                homepage=t_dict.get("homepage"),
                downloaded=t_dict.get("downloaded", False),
            )
            state_str = t_dict.get("state")
            if state_str is not None:
                try:
                    new_t.state = TorrentState(state_str)
                except ValueError:
                    pass  # unknown state — keep default
            self.session.add(new_t)

        # Mark history row as undone.
        history.undone_at = datetime.now(timezone.utc)
        history.undone_by = undone_by

        await self.session.flush()
        return history
