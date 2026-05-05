"""Torrent domain model."""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from .base import Base, TimestampMixin, VersionMixin


def normalize_hash(value: Optional[str]) -> Optional[str]:
    """Canonical info-hash form for storage and lookup.

    Different sources hand us mixed-case BitTorrent hashes (qBittorrent
    returns lowercase, some Mikan feeds emit uppercase, manual paste in the
    UI may be either). The DB UNIQUE ``(hash, bangumi_id)`` constraint and
    every ``hash == ?`` lookup is case-sensitive in SQLite, so without
    normalization we end up with two rows for the same torrent.
    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return stripped
    return stripped.lower()


class TorrentState(str, enum.Enum):
    """Torrent lifecycle states.

    Note: Most states are unused (all records default to PENDING).
    Real-time status comes from downloader API queries.
    EXCLUDED is actively used to mark manually-excluded sentinel rows
    that exist solely to prevent cronjob re-downloads.
    Any query returning user-visible torrents must filter state != EXCLUDED.
    """

    PENDING = "pending"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    RENAMING = "renaming"
    RENAMED = "renamed"
    ERROR = "error"
    STALE = "stale"
    MISSING = "missing"
    EXCLUDED = "excluded"


class RenameStatus(str, enum.Enum):
    """Outcome of the latest rename attempt for this torrent.

    Distinct from ``state`` (lifecycle) and ``renamed_at`` (timestamp). The
    renamer transitions through these:

      * ``PENDING``  — never tried, or just had its rename status cleared
                       (e.g. when the user changes title/season).
      * ``DONE``     — rename completed successfully.
      * ``CONFLICT`` — at least one file collided with an existing name in
                       the destination folder. ``rename_conflict_target``
                       holds the contested filename so the UI can show it
                       and the user can decide what to do (delete one of
                       the duplicates, rename with a quality suffix, etc.).
                       The renamer will not auto-retry; the user must act.
      * ``ERROR``    — transient failure (network, missing file). The
                       renamer will retry on the next tick.
    """

    PENDING = "pending"
    DONE = "done"
    CONFLICT = "conflict"
    ERROR = "error"


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
        Index(
            "uq_torrent_hash_unbound",
            "hash",
            unique=True,
            sqlite_where=text("hash IS NOT NULL AND bangumi_id IS NULL"),
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
        Enum(TorrentState, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=TorrentState.PENDING,
        server_default=TorrentState.PENDING.value,
    )
    downloaded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    renamed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    renamed_file_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rename_status: Mapped[RenameStatus] = mapped_column(
        Enum(RenameStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=RenameStatus.PENDING,
        server_default=RenameStatus.PENDING.value,
    )
    rename_conflict_target: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    pikpak_cloud_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pikpak_task_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    mikan_bangumi_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mikan_subgroup_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    @validates("hash")
    def _normalize_hash(self, _key: str, value: Optional[str]) -> Optional[str]:
        return normalize_hash(value)
