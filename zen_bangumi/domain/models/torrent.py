from datetime import datetime
from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from zen_bangumi.domain.models.base import Base


class Torrent(Base):
    __tablename__ = "torrent"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bangumi_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    rss_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    url: Mapped[str] = mapped_column(String(1000), nullable=False, default="https://example.com/torrent")
    homepage: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    downloaded: Mapped[bool] = mapped_column(nullable=False, default=False)
    hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    renamed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    renamed_file_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    pikpak_cloud_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
