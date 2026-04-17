"""Series domain model - the stable anime identity layer (spec §6.1).

A Series represents one anime (one Mikan bangumiId, or one (normalized_title,
season, cour_part) tuple for non-Mikan sources). Multiple Bangumi (subscriptions)
can point to the same Series via Bangumi.series_id (added in Plan 04).
"""

from typing import Optional

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, VersionMixin


class Series(Base, TimestampMixin, VersionMixin):
    __tablename__ = "series"

    __table_args__ = (
        UniqueConstraint("mikan_bangumi_id", name="uq_series_mikan"),
        UniqueConstraint(
            "normalized_title", "season", "cour_part", name="uq_series_fallback"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mikan_bangumi_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    canonical_title: Mapped[str] = mapped_column(String, nullable=False)
    normalized_title: Mapped[str] = mapped_column(String, nullable=False, index=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cour_part: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    root_path: Mapped[str] = mapped_column(String, nullable=False)
    poster_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    default_filter: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    default_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
