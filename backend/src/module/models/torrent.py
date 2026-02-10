from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Torrent(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True, alias="id")
    bangumi_id: Optional[int] = Field(None, alias="refer_id", foreign_key="bangumi.id")
    rss_id: Optional[int] = Field(None, alias="rss_id", foreign_key="rssitem.id")
    name: str = Field("", alias="name")
    url: str = Field("https://example.com/torrent", alias="url")
    homepage: Optional[str] = Field(None, alias="homepage")
    downloaded: bool = Field(False, alias="downloaded")
    hash: Optional[str] = Field(None, alias="hash")
    renamed_at: Optional[datetime] = Field(None, alias="renamed_at")
    renamed_file_count: Optional[int] = Field(None, alias="renamed_file_count")
    pikpak_cloud_path: Optional[str] = Field(None, alias="pikpak_cloud_path")


class TorrentUpdate(SQLModel):
    downloaded: bool = Field(False, alias="downloaded")
