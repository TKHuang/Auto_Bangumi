"""Bangumi domain model (post-0008 lockdown).

Identity is driven by (series_id, mikan_subgroup_id) for Mikan-sourced rows
and (series_id, rss_id) for fallback rows. Display-side fields like
canonical_title, save_path, year, poster_url live on Series; the @property
accessors below delegate so that read-side callers (API routes, search,
poster) keep compiling. Plan 05 rewrites those callers to read from
`bangumi.series` directly and these shims will be removed.
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

    series: Mapped["Series"] = relationship("Series", lazy="select")

    # ---- Read-side compat shims (delegated to series, removed in Plan 05) ----

    @property
    def official_title(self) -> Optional[str]:
        return self.series.canonical_title if self.series is not None else None

    @property
    def season(self) -> int:
        return self.series.season if self.series is not None else 1

    @property
    def year(self) -> Optional[int]:
        return self.series.year if self.series is not None else None

    @property
    def save_path(self) -> Optional[str]:
        if self.path_override:
            return self.path_override
        if self.series is None:
            return None
        # root_path is <base>/<safe_title[ (year)]> — append Season N to
        # produce the full per-season save path callers expect.
        from pathlib import PurePosixPath
        return str(PurePosixPath(self.series.root_path) / f"Season {self.series.season}")

    @property
    def poster_link(self) -> Optional[str]:
        return self.series.poster_url if self.series is not None else None

