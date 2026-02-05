from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlmodel import Field, SQLModel

from module.models.parsed import EpisodeType


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


class EpisodeFile(BaseModel):
    media_path: str = Field(...)
    group: str | None = Field(None)
    title: str = Field(...)
    season: int = Field(...)
    episode: float | int | None = Field(None)
    version: int | None = Field(None)
    suffix: str = Field(..., regex=r"(?i)\.(mkv|mp4|avi|wmv|webm|flv|mov|ts|m2ts)$")
    is_movie: bool = Field(False)
    episode_type: EpisodeType | None = Field(None)


class SubtitleFile(BaseModel):
    media_path: str = Field(...)
    group: str | None = Field(None)
    title: str = Field(...)
    season: int = Field(...)
    episode: float | int | None = Field(None)
    version: int | None = Field(None)
    language: str = Field(..., regex=r"(zh|zh-tw)")
    suffix: str = Field(..., regex=r"(?i)\.(ass|ssa|srt|sub|vtt)$")
    is_movie: bool = Field(False)
    episode_type: EpisodeType | None = Field(None)
