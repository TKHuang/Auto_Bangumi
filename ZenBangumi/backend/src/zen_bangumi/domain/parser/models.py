"""Parsed bangumi models and enumerations."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


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


class ParsedBangumi(BaseModel):
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
    alt_titles: list[str] = Field(default_factory=list)
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
    extra_info: list[str] = Field(default_factory=list)

    class Config:
        """Pydantic model configuration."""

        use_enum_values = False  # Keep enum objects, not values
