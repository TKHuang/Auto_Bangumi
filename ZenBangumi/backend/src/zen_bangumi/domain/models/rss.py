from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from zen_bangumi.domain.models.base import Base


class RSSItem(Base):
    __tablename__ = "rssitem"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, default="https://mikanani.me")
    aggregate: Mapped[bool] = mapped_column(nullable=False, default=False)
    parser: Mapped[str] = mapped_column(String(50), nullable=False, default="mikan")
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    last_update: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
