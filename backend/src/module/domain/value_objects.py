"""Value objects for the Auto_Bangumi domain layer.

This module contains all pure data classes (Pydantic models, dataclasses, enums, exceptions)
that represent immutable domain concepts without database coupling.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ==================== Enums ====================


class SubtitleType(str, Enum):
    """Subtitle language type enumeration.

    Represents the various subtitle language configurations commonly found
    in anime fansub releases.
    """

    CHS = "CHS"  # Simplified Chinese
    CHT = "CHT"  # Traditional Chinese
    CHS_CHT = "CHS_CHT"  # Both Simplified and Traditional Chinese
    CHS_JP = "CHS_JP"  # Simplified Chinese and Japanese
    CHT_JP = "CHT_JP"  # Traditional Chinese and Japanese
    CHS_CHT_JP = "CHS_CHT_JP"  # Both Chinese variants and Japanese
    JP = "JP"  # Japanese only
    EN = "EN"  # English only
    UNKNOWN = "UNKNOWN"  # Unknown or undetected subtitle type


class EpisodeType(str, Enum):
    """Episode type enumeration.

    Represents special episode types commonly found in anime releases.
    Regular TV episodes have no special type (None).
    """

    OAD = "OAD"  # Original Animation DVD
    OVA = "OVA"  # Original Video Animation
    SP = "SP"  # Special episode


# ==================== Parsed Bangumi ====================


@dataclass
class ParsedBangumi:
    """Parsed bangumi/torrent information.

    A structured representation of parsed torrent name information,
    containing all metadata extracted from torrent titles.

    Attributes:
        raw: The original raw torrent title string.
        group: The fansub group name.
        title: The main title of the anime.
        alt_titles: Alternative titles (e.g., multilingual titles).
        season: The season number (default: 1).
        episode: The episode number.
        episode_end: The ending episode number for batch releases.
        version: Episode version (e.g., 2 for v2 releases).
        resolution: Video resolution (e.g., "1080P", "720P").
        subtitle: The subtitle type.
        video_codec: Video codec (e.g., "HEVC", "AVC").
        audio_codec: Audio codec (e.g., "AAC", "FLAC").
        source: Source/rip type (e.g., "WEB-DL", "BDRip").
        container: Container format (e.g., "MKV", "MP4").
        is_movie: Whether this is a movie (劇場版/映画).
        episode_type: Special episode type (OAD, OVA, SP) or None for regular.
        extra_info: Additional extracted information.
    """

    raw: str
    group: Optional[str] = None
    title: Optional[str] = None
    alt_titles: list[str] = field(default_factory=list)
    season: int = 1
    episode: Optional[float] = None
    episode_end: Optional[float] = None
    version: Optional[int] = None
    resolution: Optional[str] = None
    subtitle: Optional[SubtitleType] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    source: Optional[str] = None
    container: Optional[str] = None
    is_movie: bool = False
    episode_type: Optional[EpisodeType] = None
    extra_info: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize the ParsedBangumi to a dictionary.

        Returns:
            A dictionary representation of the parsed bangumi data.
        """
        return {
            "raw": self.raw,
            "group": self.group,
            "title": self.title,
            "alt_titles": self.alt_titles,
            "season": self.season,
            "episode": self.episode,
            "episode_end": self.episode_end,
            "version": self.version,
            "resolution": self.resolution,
            "subtitle": self.subtitle.value if self.subtitle else None,
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "source": self.source,
            "container": self.container,
            "is_movie": self.is_movie,
            "episode_type": self.episode_type.value if self.episode_type else None,
            "extra_info": self.extra_info,
        }


# ==================== Torrent File Models ====================


class EpisodeFile(BaseModel):
    media_path: str = Field(...)
    group: str | None = Field(None)
    title: str = Field(...)
    season: int = Field(...)
    episode: float | int | None = Field(None)
    version: int | None = Field(None)
    suffix: str = Field(..., pattern=r"(?i)\.(mkv|mp4|avi|wmv|webm|flv|mov|ts|m2ts)$")
    is_movie: bool = Field(False)
    episode_type: EpisodeType | None = Field(None)


class SubtitleFile(BaseModel):
    media_path: str = Field(...)
    group: str | None = Field(None)
    title: str = Field(...)
    season: int = Field(...)
    episode: float | int | None = Field(None)
    version: int | None = Field(None)
    language: str = Field(..., pattern=r"(zh|zh-tw)")
    suffix: str = Field(..., pattern=r"(?i)\.(ass|ssa|srt|sub|vtt)$")
    is_movie: bool = Field(False)
    episode_type: EpisodeType | None = Field(None)


# ==================== Bangumi Domain Models ====================


class Notification(BaseModel):
    official_title: str = Field(..., alias="official_title", title="番剧名")
    season: int = Field(..., alias="season", title="番剧季度")
    episode: Optional[int] = Field(None, alias="episode", title="番剧集数")
    is_movie: bool = Field(False, alias="is_movie", title="是否为剧场版")
    poster_path: Optional[str] = Field(None, alias="poster_path", title="番剧海报路径")


@dataclass
class Episode:
    title_en: Optional[str]
    title_zh: Optional[str]
    title_jp: Optional[str]
    season: int
    season_raw: str
    episode: int
    sub: str
    group: str
    resolution: str
    source: str


class BangumiParsingError(Exception):
    """Exception raised when automatic bangumi parsing fails to extract title information.
    
    This exception is raised when the raw parser returns an Episode with all title fields empty,
    allowing callers to distinguish this specific failure from other errors.
    """
    
    def __init__(
        self,
        raw_title: str,
        partial_data: dict,
        msg_en: str,
        msg_zh: str,
    ) -> None:
        self.raw_title = raw_title
        self.partial_data = partial_data
        self.msg_en = msg_en
        self.msg_zh = msg_zh
        super().__init__(msg_en)


# ==================== API Response Models ====================


class ResponseModel(BaseModel):
    status: bool = Field(..., json_schema_extra={"example": True})
    status_code: int = Field(..., json_schema_extra={"example": 200})
    msg_en: str
    msg_zh: str
    error_type: str | None = Field(default=None, description="Error type identifier")
    existing_bangumi: dict | None = Field(
        default=None, description="Existing bangumi data for duplicate errors"
    )


class APIResponse(BaseModel):
    status: bool = Field(..., json_schema_extra={"example": True})
    msg_en: str = Field(..., json_schema_extra={"example": "Success"})
    msg_zh: str = Field(..., json_schema_extra={"example": "成功"})


# ==================== Path Utilities ====================


def gen_save_path(base_path: str, official_title: str, season: int, year: Optional[str] = None) -> str:
    """Generate save path: <base>/<title[ (year)]>/Season <n>."""
    from pathlib import PurePosixPath

    folder = f"{official_title} ({year})" if year else official_title
    return str(PurePosixPath(base_path) / folder / f"Season {season}")
