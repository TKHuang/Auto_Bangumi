import logging
from pathlib import Path

from module.models import EpisodeFile, SubtitleFile
from module.models.parsed import SubtitleType
from module.domain.parser.analyser.bangumi_parser import BangumiParser

logger = logging.getLogger(__name__)

PLATFORM = "Unix"

# Subtitle language mapping from SubtitleType to EpisodeFile language codes
SUBTITLE_LANG_MAP = {
    SubtitleType.CHT: "zh-tw",
    SubtitleType.CHS_CHT: "zh-tw",
    SubtitleType.CHT_JP: "zh-tw",
    SubtitleType.CHS_CHT_JP: "zh-tw",
    SubtitleType.CHS: "zh",
    SubtitleType.CHS_JP: "zh",
    SubtitleType.JP: None,
    SubtitleType.EN: None,
    SubtitleType.UNKNOWN: None,
}


def get_path_basename(torrent_path: str) -> str:
    """
    Returns the basename of a path string.

    :param torrent_path: A string representing a path to a file.
    :type torrent_path: str
    :return: A string representing the basename of the given path.
    :rtype: str
    """
    return Path(torrent_path).name


def _extract_simple_title(filename: str) -> str | None:
    """Extract title from simple formats like 'Title S01E01.mp4'.

    Fallback for when BangumiParser doesn't find a title.
    """
    import re

    # Remove file extension
    name = Path(filename).stem

    # Try to extract title before S##E## pattern
    match = re.match(r"^(.+?)\s+S\d+E\d+", name, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Try to extract title before - ## pattern
    match = re.match(r"^(.+?)\s+-\s+\d+", name)
    if match:
        return match.group(1).strip()

    return None


def torrent_parser(
    torrent_path: str,
    torrent_name: str | None = None,
    season: int | None = None,
    file_type: str = "media",
) -> EpisodeFile | SubtitleFile:
    """Parse torrent file path to extract episode/subtitle information.

    Uses BangumiParser to extract metadata from filenames.

    Args:
        torrent_path: Full path to the torrent file
        torrent_name: Optional torrent name to parse (if different from path basename)
        season: Optional explicit season override
        file_type: Either "media" or "subtitle"

    Returns:
        EpisodeFile or SubtitleFile based on file_type
    """
    # Get basename from path
    media_path_basename = get_path_basename(torrent_path)

    # Determine which name to parse (prefer torrent_name if provided)
    parse_name = torrent_name if torrent_name else media_path_basename

    # Use BangumiParser to parse the filename
    parser = BangumiParser()
    parsed = parser.parse(parse_name)

    # Extract title
    title = parsed.title

    # Validate title - if it looks like just a file extension, it's bad
    def _is_bad_title(t: str | None) -> bool:
        if not t:
            return True
        t_lower = t.strip().lower()
        # Title that's just an extension like ".mp4" or empty
        if t_lower.startswith(".") or not t_lower:
            return True
        return False

    if _is_bad_title(title):
        # Try simple title extraction as fallback
        simple_title = _extract_simple_title(parse_name)
        if simple_title and not _is_bad_title(simple_title):
            title = simple_title
        else:
            # Last resort: use the raw filename without extension
            stem = Path(parse_name).stem
            # If stem contains episode type markers, try to extract clean title
            # e.g., "Golden Kamuy[OAD]" -> "Golden Kamuy"
            # e.g., "Golden Kamuy OAD 01" -> "Golden Kamuy"
            import re

            # First remove bracketed markers like [OAD], [OVA], [SP]
            clean_stem = re.sub(r"\[(?:OAD|OVA\d*|SP\d*|Special)\]", "", stem).strip()
            # Then remove unbracketed trailing markers like "OAD 01", "OVA", "SP 02"
            # This prevents accumulation bug when re-parsing already renamed files
            # Loop to handle accumulated cases like "Title OAD 01 OAD 01"
            prev_stem = None
            while clean_stem != prev_stem:
                prev_stem = clean_stem
                clean_stem = re.sub(
                    r"\s+(?:OAD|OVA|SP|Special)\s*-?\s*\d*$",
                    "",
                    clean_stem,
                    flags=re.IGNORECASE,
                ).strip()
            title = clean_stem if clean_stem else stem

    # Use explicit season if provided, otherwise use parsed season
    final_season = season if season is not None else parsed.season

    # Extract episode (handle both single and batch ranges)
    # For torrent files, we typically use the start episode
    episode = parsed.episode

    # If episode not found by BangumiParser, try simple S##E## extraction
    if episode is None:
        import re

        match = re.search(r"S\d+E(\d+)", parse_name, re.IGNORECASE)
        if match:
            episode = int(match.group(1))

    # Get file extension
    suffix = Path(torrent_path).suffix

    if file_type == "media":
        return EpisodeFile(
            media_path=torrent_path,
            group=parsed.group,
            title=title,
            season=final_season,
            episode=episode,
            version=parsed.version,
            suffix=suffix,
            is_movie=parsed.is_movie,
            episode_type=parsed.episode_type,
        )
    elif file_type == "subtitle":
        # Map SubtitleType to language code
        language = SUBTITLE_LANG_MAP.get(parsed.subtitle)

        # If no language detected from subtitle markers, try basename parsing
        if language is None:
            # Check for language markers in filename
            lower_name = media_path_basename.lower()
            if any(marker in lower_name for marker in ["tc", "cht", "繁", "zh-tw"]):
                language = "zh-tw"
            elif any(marker in lower_name for marker in ["sc", "chs", "简", "zh"]):
                language = "zh"

        return SubtitleFile(
            media_path=torrent_path,
            group=parsed.group,
            title=title,
            season=final_season,
            language=language,
            episode=episode,
            version=parsed.version,
            suffix=suffix,
            is_movie=parsed.is_movie,
            episode_type=parsed.episode_type,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ep = torrent_parser("/不时用俄语小声说真心话的邻桌艾莉同学/Season 1/不时用俄语小声说真心话的邻桌艾莉同学 S01E02.mp4")
    logger.info(ep)

    ep = torrent_parser(
        "/downloads/Bangumi/关于我转生变成史莱姆这档事 (2018)/Season 3/[ANi] 關於我轉生變成史萊姆這檔事 第三季 - 48.5 [1080P][Baha][WEB-DL][AAC AVC][CHT].mp4"
    )
    logger.info(ep)

    ep = torrent_parser(
        "/downloads/Bangumi/关于我转生变成史莱姆这档事 (2018)/Season 3/[ANi] 關於我轉生變成史萊姆這檔事 第三季 - 48.5 [1080P][Baha][WEB-DL][AAC AVC][CHT].srt",
        file_type="subtitle",
    )
    logger.info(ep)
