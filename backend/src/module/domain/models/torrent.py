"""Torrent domain model."""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, VersionMixin


class TorrentState(str, enum.Enum):
    """Torrent lifecycle states."""

    PENDING = "pending"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    RENAMING = "renaming"
    RENAMED = "renamed"
    ERROR = "error"
    STALE = "stale"
    MISSING = "missing"


class Torrent(Base, TimestampMixin, VersionMixin):
    """Torrent entity.

    Represents a torrent file associated with a bangumi episode.
    """

    __tablename__ = "torrent"

    __table_args__ = (
        UniqueConstraint(
            "hash",
            "bangumi_id",
            name="uq_torrent_hash_bangumi",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bangumi_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("bangumi.id"), nullable=True
    )
    rss_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("rssitem.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False, default="")
    url: Mapped[str] = mapped_column(
        String, nullable=False, default="https://example.com/torrent"
    )
    homepage: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    state: Mapped[TorrentState] = mapped_column(
        Enum(TorrentState), nullable=False, default=TorrentState.PENDING
    )
    downloaded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    renamed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    renamed_file_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pikpak_cloud_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pikpak_task_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
