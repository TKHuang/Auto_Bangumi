"""Staging queue for RSS-parsed torrents awaiting Mikan ID resolution (spec §6.1, §8.3).

Rows exist here iff the RSS feed produced a torrent whose MikanEpisodeRef is not
yet resolvable (parse_status='failed' or Mikan unreachable). The resolver retries
on every RSS refresh tick; on success, a real Torrent row is created and the
staging row is deleted.

The length of this table is the Dashboard 'pending' count.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PendingTorrentEnrichment(Base):
    __tablename__ = "pending_torrent_enrichment"

    __table_args__ = (
        Index("ix_pending_torrent_enrichment_rss", "rss_id"),
    )

    info_hash: Mapped[str] = mapped_column(String, primary_key=True)
    raw_name: Mapped[str] = mapped_column(String, nullable=False)
    homepage: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    rss_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rssitem.id", ondelete="CASCADE"),
        nullable=False,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
