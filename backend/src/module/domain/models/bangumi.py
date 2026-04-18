"""Bangumi domain model."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, VersionMixin

if TYPE_CHECKING:
    from .series import Series


class Bangumi(Base, TimestampMixin, VersionMixin):
    """Bangumi (anime series) entity.

    Represents a tracked anime series with its metadata and download rules.
    """

    __tablename__ = "bangumi"

    __table_args__ = (
        UniqueConstraint(
            "official_title",
            "season",
            "group_name",
            name="uq_bangumi_title_season_group",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rss_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("rssitem.id"), nullable=True
    )
    official_title: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    title_raw: Mapped[str] = mapped_column(String, nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    season_raw: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    group_name: Mapped[str] = mapped_column(String, nullable=False, default="Unknown")
    dpi: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    subtitle: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    eps_collect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filter: Mapped[str] = mapped_column(
        String, nullable=False, default="720,\\d+-\\d+"
    )
    rss_link: Mapped[str] = mapped_column(String, nullable=False, default="")
    poster_link: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    added: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rule_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    save_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pending_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    global_filter_matches: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # New identity surface (migration 0007). series_id becomes NOT NULL in 0008.
    series_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("series.id"), nullable=True, index=True
    )
    mikan_subgroup_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    path_override: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    observed_groups: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    series: Mapped[Optional["Series"]] = relationship("Series", lazy="select")
