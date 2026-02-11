"""Torrent schema models (pure Pydantic/SQLModel schemas — NOT ORM tables).

The real ORM tables live in module.domain.models.torrent.
These schemas are used for API serialization and sync-layer data containers.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Torrent(SQLModel, table=False):
    model_config = {"from_attributes": True}

    id: Optional[int] = Field(default=None)
    bangumi_id: Optional[int] = Field(default=None)
    rss_id: Optional[int] = Field(default=None)
    name: str = Field(default="")
    url: str = Field(default="https://example.com/torrent")
    homepage: Optional[str] = Field(default=None)
    downloaded: bool = Field(default=False)
    hash: Optional[str] = Field(default=None)
    renamed_at: Optional[datetime] = Field(default=None)
    renamed_file_count: Optional[int] = Field(default=None)
    pikpak_cloud_path: Optional[str] = Field(default=None)


class TorrentUpdate(SQLModel):
    downloaded: bool = Field(default=False)
