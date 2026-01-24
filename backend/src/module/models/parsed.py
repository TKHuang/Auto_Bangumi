from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


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
        resolution: Video resolution (e.g., "1080P", "720P").
        subtitle: The subtitle type.
        video_codec: Video codec (e.g., "HEVC", "AVC").
        audio_codec: Audio codec (e.g., "AAC", "FLAC").
        source: Source/rip type (e.g., "WEB-DL", "BDRip").
        container: Container format (e.g., "MKV", "MP4").
        is_movie: Whether this is a movie/OVA/special.
        extra_info: Additional extracted information.
    """

    raw: str
    group: Optional[str] = None
    title: Optional[str] = None
    alt_titles: list[str] = field(default_factory=list)
    season: int = 1
    episode: Optional[float] = None
    episode_end: Optional[float] = None
    resolution: Optional[str] = None
    subtitle: Optional[SubtitleType] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    source: Optional[str] = None
    container: Optional[str] = None
    is_movie: bool = False
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
            "resolution": self.resolution,
            "subtitle": self.subtitle.value if self.subtitle else None,
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "source": self.source,
            "container": self.container,
            "is_movie": self.is_movie,
            "extra_info": self.extra_info,
        }
