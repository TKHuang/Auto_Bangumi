"""RSS domain model."""

from typing import Optional

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, VersionMixin


class RSSItem(Base, TimestampMixin, VersionMixin):
    """RSS feed entity."""

    __tablename__ = "rssitem"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    url: Mapped[str] = mapped_column(
        String, nullable=False, default="https://mikanani.me"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    aggregate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parser: Mapped[str] = mapped_column(String, nullable=False, default="mikan")
    last_update: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
