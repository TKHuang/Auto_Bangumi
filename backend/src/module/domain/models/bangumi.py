"""Bangumi domain model (post-0008 lockdown).

Identity is driven by (series_id, mikan_subgroup_id) for Mikan-sourced rows
and (series_id, rss_id) for fallback rows. Display-side fields like
canonical_title, save_path, year, poster_url live on Series and are accessed
via bangumi.series directly.
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, ForeignKey, Index, Integer, String, Text, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, VersionMixin

if TYPE_CHECKING:
    from .series import Series


class Bangumi(Base, TimestampMixin, VersionMixin):
    __tablename__ = "bangumi"

    __table_args__ = (
        Index(
            "uq_bangumi_series_subgroup",
            "series_id", "mikan_subgroup_id",
            unique=True,
            sqlite_where=text("deleted = 0"),
        ),
        Index(
            "uq_bangumi_series_rss_fallback",
            "series_id", "rss_id",
            unique=True,
            sqlite_where=text(
                "mikan_subgroup_id IS NULL AND deleted = 0"
            ),
        ),
        Index(
            "uq_bangumi_mikan_url",
            "mikan_bangumi_url",
            unique=True,
            sqlite_where=text(
                "mikan_bangumi_url IS NOT NULL AND deleted = 0"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rss_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("rssitem.id"), nullable=True
    )
    series_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("series.id"), nullable=False, index=True
    )
    mikan_subgroup_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    # Subscription + filter behaviour
    group_name: Mapped[str] = mapped_column(
        String, nullable=False, default="Unknown"
    )
    dpi: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    subtitle: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    eps_collect: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filter: Mapped[str] = mapped_column(
        String, nullable=False, default="720,\\d+-\\d+"
    )
    rss_link: Mapped[str] = mapped_column(String, nullable=False, default="")
    added: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rule_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pending_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    global_filter_matches: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )

    # New v2 fields
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    path_override: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    observed_groups: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Canonical Mikan bangumi-page URL (e.g.
    # "https://mikanani.me/Home/Bangumi/3901#1243"). Populated when the
    # bangumi is resolved via the pending-resolution flow; lets later RSS
    # items for the same show short-circuit the parser/Mikan-resolver path.
    mikan_bangumi_url: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )

    series: Mapped["Series"] = relationship("Series", lazy="select")

