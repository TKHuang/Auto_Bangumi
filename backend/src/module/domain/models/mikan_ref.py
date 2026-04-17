"""Mikan episode-page scraping cache (spec §6.1, §8.1).

Stores the parsed (bangumi_id, subgroup_id) extracted from each Mikan episode
page, keyed by the torrent's info_hash (which Mikan uses as the URL suffix).

parse_status values:
  - 'ok'         : parser extracted a MikanRef; mikan_bangumi_id is non-null
  - 'failed'     : Mikan fetch or parse failed; retry on next resolver pass
  - 'non_mikan'  : homepage URL is not a Mikan episode URL; never retry
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MikanEpisodeRef(Base):
    __tablename__ = "mikan_episode_ref"

    __table_args__ = (
        Index(
            "ix_mikan_episode_ref_series",
            "mikan_bangumi_id",
            "mikan_subgroup_id",
        ),
    )

    info_hash: Mapped[str] = mapped_column(String, primary_key=True)
    mikan_bangumi_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mikan_subgroup_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    canonical_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    poster_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    parse_status: Mapped[str] = mapped_column(String, nullable=False)
