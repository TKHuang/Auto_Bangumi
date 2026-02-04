from typing import Optional

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from zen_bangumi.domain.models.base import Base, VersionMixin


class Bangumi(Base, VersionMixin):
    __tablename__ = "bangumi"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rss_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    official_title: Mapped[str] = mapped_column(String(255), nullable=False, default="official_title")
    year: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    title_raw: Mapped[str] = mapped_column(String(255), nullable=False, default="title_raw")
    season: Mapped[int] = mapped_column(nullable=False, default=1)
    season_raw: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    group_name: Mapped[str] = mapped_column(String(100), nullable=False, default="Unknown")
    dpi: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    subtitle: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    eps_collect: Mapped[bool] = mapped_column(nullable=False, default=False)
    offset: Mapped[int] = mapped_column(nullable=False, default=0)
    filter: Mapped[str] = mapped_column(String(100), nullable=False, default="720,\\d+-\\d+")
    rss_link: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    poster_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    added: Mapped[bool] = mapped_column(nullable=False, default=False)
    rule_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    save_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    deleted: Mapped[bool] = mapped_column(nullable=False, default=False)
    pending_review: Mapped[bool] = mapped_column(nullable=False, default=False)
    global_filter_matches: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        UniqueConstraint("official_title", "season", "group_name", name="uq_bangumi_identity"),
    )
