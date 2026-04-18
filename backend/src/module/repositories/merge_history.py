"""BangumiMergeHistoryRepository - write-once audit log for merges.

The actual merge transaction (moving torrents, soft-deleting loser) is
implemented in Plan 04. This repo only records history rows and answers
'has this pair ever been merged?' for the permanent-blacklist rule
(spec §11.4).
"""
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.merge_history import BangumiMergeHistory


class BangumiMergeHistoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, history_id: int) -> Optional[BangumiMergeHistory]:
        return await self.session.get(BangumiMergeHistory, history_id)

    async def create(
        self,
        winner_id: int,
        loser_id: int,
        loser_snapshot: dict,
        moved_torrent_ids: list[int],
        dropped_torrents: list[dict],
        merge_reason: str,
        merged_by: str,
    ) -> BangumiMergeHistory:
        row = BangumiMergeHistory(
            merged_at=datetime.now(timezone.utc),
            merged_by=merged_by,
            merge_reason=merge_reason,
            winner_bangumi_id=winner_id,
            loser_bangumi_id=loser_id,
            loser_snapshot=json.dumps(loser_snapshot, ensure_ascii=False, default=str),
            moved_torrent_ids=json.dumps(moved_torrent_ids),
            dropped_torrents=json.dumps(dropped_torrents, ensure_ascii=False, default=str),
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def find_cascade_blockers(
        self, history_id: int, winner_id: int, loser_id: int
    ) -> list[int]:
        """Return ids of later un-undone merges that reference either
        participant — undoing ``history_id`` is unsafe while any exist
        (spec §11.5).

        A blocker is any history row with ``id > history_id`` AND
        ``undone_at IS NULL`` whose winner or loser matches either the
        winner or loser of the history being undone.
        """
        participants = {winner_id, loser_id}
        stmt = (
            select(BangumiMergeHistory.id)
            .where(
                and_(
                    BangumiMergeHistory.id > history_id,
                    BangumiMergeHistory.undone_at.is_(None),
                    or_(
                        BangumiMergeHistory.winner_bangumi_id.in_(participants),
                        BangumiMergeHistory.loser_bangumi_id.in_(participants),
                    ),
                )
            )
            .order_by(BangumiMergeHistory.id)
        )
        result = await self.session.execute(stmt)
        return [row for row in result.scalars().all()]

    async def mark_undone(self, history_id: int, actor: str) -> None:
        row = await self.get_by_id(history_id)
        if row is None:
            raise ValueError(f"merge history id={history_id} not found")
        if row.undone_at is not None:
            raise ValueError(f"merge history id={history_id} already undone")
        row.undone_at = datetime.now(timezone.utc)
        row.undone_by = actor
        await self.session.flush()

    async def is_pair_blacklisted(self, a_id: int, b_id: int) -> bool:
        """Return True if (a, b) or (b, a) appears in history (direction-agnostic).

        Per spec §11.4 undone status is irrelevant: once merged, the pair is
        permanently excluded from auto-merge.
        """
        stmt = select(BangumiMergeHistory.id).where(
            or_(
                and_(
                    BangumiMergeHistory.winner_bangumi_id == a_id,
                    BangumiMergeHistory.loser_bangumi_id == b_id,
                ),
                and_(
                    BangumiMergeHistory.winner_bangumi_id == b_id,
                    BangumiMergeHistory.loser_bangumi_id == a_id,
                ),
            )
        ).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_paginated(
        self, *, limit: int, offset: int
    ) -> tuple[list[BangumiMergeHistory], int]:
        total = (
            await self.session.execute(
                select(func.count(BangumiMergeHistory.id))
            )
        ).scalar() or 0
        rows = (
            await self.session.execute(
                select(BangumiMergeHistory)
                .order_by(desc(BangumiMergeHistory.merged_at))
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()
        return list(rows), int(total)

    async def list_all(self, active_only: bool = False) -> list[BangumiMergeHistory]:
        stmt = select(BangumiMergeHistory).order_by(BangumiMergeHistory.merged_at.desc())
        if active_only:
            stmt = stmt.where(BangumiMergeHistory.undone_at.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
