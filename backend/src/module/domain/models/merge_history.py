"""Audit log of bangumi merge operations (spec §6.1, §11).

Every merge writes a row here. undone_at NULL means the merge is active;
non-NULL means the user reverted it via the UI. The (winner, loser) pair is a
permanent blacklist against future auto-merges regardless of undone status.

loser_snapshot, moved_torrent_ids, dropped_torrents are stored as JSON strings
(SQLite has no native JSON but supports the text storage cleanly).
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BangumiMergeHistory(Base):
    __tablename__ = "bangumi_merge_history"

    __table_args__ = (
        Index("ix_bangumi_merge_history_winner", "winner_bangumi_id"),
        Index("ix_bangumi_merge_history_loser", "loser_bangumi_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merged_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    merged_by: Mapped[str] = mapped_column(String, nullable=False)
    merge_reason: Mapped[str] = mapped_column(String, nullable=False)
    # NULL when the underlying bangumi was hard-deleted after the merge.
    # The audit row is the only durable proof the merge happened, so we keep
    # it (and its loser_snapshot/moved_torrent_ids JSON) and let the FK go
    # to NULL via ON DELETE SET NULL — see migration 0010.
    winner_bangumi_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("bangumi.id", ondelete="SET NULL"), nullable=True
    )
    loser_bangumi_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("bangumi.id", ondelete="SET NULL"), nullable=True
    )
    loser_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    moved_torrent_ids: Mapped[str] = mapped_column(Text, nullable=False)
    dropped_torrents: Mapped[str] = mapped_column(Text, nullable=False)
    undone_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    undone_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
