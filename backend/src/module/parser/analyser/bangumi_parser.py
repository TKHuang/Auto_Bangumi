"""Bangumi/Torrent title parser with comprehensive fansub format support."""

import re
from dataclasses import dataclass
from typing import Optional

from module.models.parsed import EpisodeType, ParsedBangumi, SubtitleType


@dataclass
class BracketContent:
    """Represents content extracted from a bracket pair."""

    content: str
    start: int
    end: int
    bracket_type: str  # "fullwidth", "halfwidth", "parenthesis"


class BangumiParser:
    """Parser for anime torrent titles with comprehensive fansub format support.

    This parser handles various torrent naming conventions used by different
    fansub groups, including:
    - Full-width brackets【】
    - Half-width brackets []
    - Parentheses ()
    - Mixed bracket styles

    All regex patterns are pre-compiled in the constructor for performance.
    """

    def __init__(self) -> None:
        """Initialize parser with pre-compiled regex patterns."""
        # Bracket extraction patterns
        self._fullwidth_bracket_re = re.compile(r"【([^【】]*)】")
        self._halfwidth_bracket_re = re.compile(r"\[([^\[\]]*)\]")
        self._parenthesis_re = re.compile(r"\(([^()]*)\)")

        # Group identification patterns
        self._multi_group_re = re.compile(r"[&＆×]")
        self._group_indicators = re.compile(
            r"字幕|sub|fansub|rip|raws?|encode|translation",
            re.IGNORECASE,
        )

        # Subtitle language detection patterns
        # Simplified Chinese markers
        self._subtitle_chs_re = re.compile(
            r"简体|简中|简日|简日双语|CHS|GB_?MP4|GB|SC", re.IGNORECASE
        )
        # Traditional Chinese markers
        self._subtitle_cht_re = re.compile(
            r"繁体|繁中|繁日|繁日双语|CHT|BIG5_?MP4|BIG5|TC", re.IGNORECASE
        )
        # Both Simplified and Traditional markers
        self._subtitle_chs_cht_re = re.compile(
            r"简繁|繁简|简体&繁体|繁体&简体|简繁双语|繁简双语|CHS_?CHT|CHT_?CHS",
            re.IGNORECASE,
        )
        # Japanese markers
        self._subtitle_jp_re = re.compile(r"日语|日文|日本語|日字|JPN?(?:_?SUB)?", re.IGNORECASE)
        # English markers
        self._subtitle_en_re = re.compile(r"英语|英文|ENG?(?:_?SUB)?", re.IGNORECASE)
        # Combined CHS+JP markers
        self._subtitle_chs_jp_re = re.compile(r"简日|GB_?JP|CHS_?JP", re.IGNORECASE)
        # Combined CHT+JP markers
        self._subtitle_cht_jp_re = re.compile(r"繁日|BIG5_?JP|CHT_?JP", re.IGNORECASE)
        # Embedded/hardsub markers (indicates presence of subtitles)
        self._subtitle_embedded_re = re.compile(
            r"内嵌|內嵌|内封|內封|嵌字|hardsub|softsub|字幕", re.IGNORECASE
        )

        # Resolution patterns - ordered by specificity
        # Matches: 1080p, 720P, 2160p, etc.
        self._resolution_standard_re = re.compile(
            r"\b(2160|1080|720|480)[pP]\b", re.IGNORECASE
        )
        # Matches: 1920x1080, 1280X720, etc.
        self._resolution_dimensions_re = re.compile(r"\b(\d{3,4})[xX×](\d{3,4})\b")
        # Matches: 4K, UHD (both map to 2160P)
        self._resolution_4k_re = re.compile(r"\b(4K|UHD)\b", re.IGNORECASE)
        # Matches: FHD (maps to 1080P)
        self._resolution_fhd_re = re.compile(r"\bFHD\b", re.IGNORECASE)
        # Matches: HD (maps to 720P)
        self._resolution_hd_re = re.compile(r"\bHD\b", re.IGNORECASE)

        # Season extraction patterns
        # Standard formats: S01, S02, Season 1, Season 2, etc.
        # Also handles S##E## format (e.g., S00E01, S02E05)
        self._season_standard_re = re.compile(
            r"\bS(\d{1,2})(?:E\d+|\b)|\bSeason\s*(\d{1,2})\b", re.IGNORECASE
        )
        # Ordinal formats: 1st Season, 2nd Season, 3rd Season, etc.
        self._season_ordinal_re = re.compile(
            r"\b(\d{1,2})(?:st|nd|rd|th)\s+Season\b", re.IGNORECASE
        )
        # Chinese season marker: 第X季 (where X is Chinese or Arabic numeral)
        self._season_chinese_re = re.compile(r"第([一二三四五六七八九十\d]+)季")
        # Alternative Chinese season markers: Season in Japanese style
        self._season_part_re = re.compile(r"\bPart\s*(\d+)\b", re.IGNORECASE)
        # Roman numerals for seasons (I, II, III, IV, etc.)
        self._season_roman_re = re.compile(
            r"\b(I{1,3}|IV|VI{0,3}|IX|XI{0,2})\b(?:\s|$|]|】)"
        )

        # Chinese numeral to Arabic numeral mapping
        self._chinese_numeral_map = {
            "一": 1,
            "二": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10,
        }

        # Episode extraction patterns
        # Version suffix to remove: v2, v3, etc.
        self._episode_version_re = re.compile(r"[vV]\d+")
        # Batch range in brackets: [01-12], [01~24], [01-08Fin], [01-08 Fin]
        self._episode_batch_bracket_re = re.compile(
            r"\[(\d+(?:\.\d+)?)\s*[-~～]\s*(\d+(?:\.\d+)?)"
            r"(?:\s*(?:END|FIN|COMPLETE|完结|完結))?\]",
            re.IGNORECASE,
        )
        # Standalone batch range (with context to avoid resolution matches)
        # Excludes S (season marker) to prevent "S02 - 15" from matching as batch "02-15"
        self._episode_batch_standalone_re = re.compile(
            r"(?:^|[^\dx×XsS])(\d{1,4}(?:\.\d+)?)\s*[-~～]\s*(\d{1,4}(?:\.\d+)?)(?:[^\d]|$)"
        )
        # Single episode in brackets: [01], [12], [12.5]
        self._episode_bracket_re = re.compile(r"\[(\d+(?:\.\d+)?)\]")
        # EP/E prefix: EP01, E01, EP12.5
        self._episode_ep_prefix_re = re.compile(r"\bE[Pp]?(\d+(?:\.\d+)?)\b")
        # Chinese episode markers: 第01集, 第12话, 第12話
        self._episode_chinese_re = re.compile(r"第(\d+(?:\.\d+)?)[集话話]")
        # Chinese episode markers without 第 prefix (common in all-bracket format): [02集], [12话]
        self._episode_chinese_simple_re = re.compile(r"\[(\d+(?:\.\d+)?)[集话話]\]")
        # Hash prefix: #01, #12
        self._episode_hash_re = re.compile(r"#(\d+(?:\.\d+)?)")
        # Dash-separated episode (after title): - 01, - 12
        self._episode_dash_sep_re = re.compile(r"\s-\s*(\d+(?:\.\d+)?)\b")
        # SP prefix: SP01, SP02 (Special episodes)
        self._episode_sp_prefix_re = re.compile(
            r"\bSP\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE
        )
        # OVA/OAD with episode (with or without dash): OVA 01, OVA - 01, OAD 02
        self._episode_ova_oad_re = re.compile(
            r"\b(?:OVA|OAD)\s*-?\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE
        )
        # END/Fin/Complete markers (with underscore support for patterns like 25_END)
        # Also allows digit before END for patterns like [25END]
        self._episode_end_marker_re = re.compile(
            r"(?:_|\d|\b)(?:END|FIN|COMPLETE|完结|完結|终|終)(?:\b|$)", re.IGNORECASE
        )
        # Batch range before END marker
        self._episode_batch_end_re = re.compile(
            r"(\d+(?:\.\d+)?)\s*[-~～]\s*(\d+(?:\.\d+)?)"
        )
        # Single episode with END marker in brackets: [25_END], [25END], [25 END]
        self._episode_end_bracket_re = re.compile(
            r"\[(\d+)[\s_]?(?:END|FIN|COMPLETE|完结|完結)\]", re.IGNORECASE
        )

        # Video codec patterns - normalized to standard names
        # HEVC variants: HEVC, H.265, x265, H265
        self._video_hevc_re = re.compile(r"\b(?:HEVC|H\.?265|x265)\b", re.IGNORECASE)
        # AVC variants: AVC, H.264, x264, H264
        self._video_avc_re = re.compile(r"\b(?:AVC|H\.?264|x264)\b", re.IGNORECASE)
        # AV1 codec
        self._video_av1_re = re.compile(r"\bAV1\b", re.IGNORECASE)
        # VP9 codec
        self._video_vp9_re = re.compile(r"\bVP9\b", re.IGNORECASE)

        # Audio codec patterns
        # AAC codec
        self._audio_aac_re = re.compile(r"\bAAC\b", re.IGNORECASE)
        # FLAC codec
        self._audio_flac_re = re.compile(r"\bFLAC\b", re.IGNORECASE)
        # AC3 codec
        self._audio_ac3_re = re.compile(r"\bAC3\b", re.IGNORECASE)
        # DTS codec (including DTS-HD variants)
        self._audio_dts_re = re.compile(r"\bDTS(?:-HD)?\b", re.IGNORECASE)
        # EAC3 / E-AC-3 codec
        self._audio_eac3_re = re.compile(r"\bE[-]?AC[-]?3\b", re.IGNORECASE)
        # OPUS codec
        self._audio_opus_re = re.compile(r"\bOPUS\b", re.IGNORECASE)

        # Source/rip type patterns
        # WEB-DL and WebRip variants
        self._source_webdl_re = re.compile(r"\bWEB[-_]?DL\b", re.IGNORECASE)
        self._source_webrip_re = re.compile(r"\bWEB[-_]?Rip\b", re.IGNORECASE)
        # BluRay/BD variants
        self._source_bdrip_re = re.compile(r"\bBD[-_]?Rip\b", re.IGNORECASE)
        self._source_bluray_re = re.compile(
            r"\b(?:Blu[-_]?Ray|BD(?:Remux)?)\b", re.IGNORECASE
        )
        # HDTV
        self._source_hdtv_re = re.compile(r"\bHDTV\b", re.IGNORECASE)
        # DVDRip
        self._source_dvdrip_re = re.compile(r"\bDVD[-_]?Rip\b", re.IGNORECASE)

        # Streaming service sources
        # Crunchyroll
        self._source_cr_re = re.compile(r"\bCR\b")
        # Bahamut (Baha)
        self._source_baha_re = re.compile(r"\bBaha(?:mut)?\b", re.IGNORECASE)
        # Bilibili Global
        self._source_bglobal_re = re.compile(r"\bB[-_]?Global\b", re.IGNORECASE)
        # ABEMA
        self._source_abema_re = re.compile(r"\bABEMA\b", re.IGNORECASE)
        # Bilibili
        self._source_bilibili_re = re.compile(r"\bBilibili\b", re.IGNORECASE)
        # AT-X (Japanese TV channel)
        self._source_atx_re = re.compile(r"\bAT[-_]?X\b")

        # Title extraction patterns
        # Metadata terms to filter from title candidates
        self._metadata_terms_re = re.compile(
            r"^(?:\d+(?:P|p)|HEVC|AVC|H\.?26[45]|x26[45]|AV1|VP9|AAC|FLAC|AC3|DTS|"
            r"OPUS|EAC3|WEB[-_]?DL|WEB[-_]?Rip|BD[-_]?Rip|Blu[-_]?Ray|HDTV|DVD[-_]?Rip|"
            r"CR|Baha|ABEMA|Bilibili|MP4|MKV|AVI|CHS|CHT|BIG5|GB|SC|TC|"
            r"简体|繁体|简繁|简中|繁中|简日|繁日|内嵌|內嵌|内封|內封|字幕|"
            r"4K|UHD|FHD|HD|10bit|8bit|HDR|BDRemux|B-Global|AT-X)$",
            re.IGNORECASE,
        )

        # Movie detection patterns (real theatrical movies only)
        # Chinese movie markers: 剧场版, 劇場版, 电影, 電影
        self._movie_chinese_re = re.compile(r"[剧劇]场版|[电電]影", re.IGNORECASE)
        # Japanese movie markers: 映画, 劇場版
        self._movie_japanese_re = re.compile(r"映画|劇場版", re.IGNORECASE)
        # English movie markers: Movie, The Movie (case-insensitive)
        self._movie_english_re = re.compile(r"\bThe\s+Movie\b|\bMovie\b", re.IGNORECASE)

        # Episode type detection patterns (OAD, OVA, SP - these are NOT movies)
        # OAD markers (Original Animation DVD)
        self._episode_type_oad_re = re.compile(r"\bOAD\b", re.IGNORECASE)
        # OVA markers (Original Video Animation) - also matches OVA1, OVA2, etc.
        self._episode_type_ova_re = re.compile(r"\bOVA\d*\b", re.IGNORECASE)
        # Special/SP markers
        self._episode_type_sp_re = re.compile(r"\bSpecial\b|\bSP\d*\b", re.IGNORECASE)
        # Decorator pattern before title bracket (e.g., ★剧场版[Title], ★01月新番★[Title])
        # This matches decorators like ★剧场版, ★01月新番★, 剧场版, etc. followed by a bracket
        self._decorator_before_bracket_re = re.compile(
            r"^[★☆]*(?:[剧劇]场版|[电電]影|\d{1,2}月新番)[★☆]*\s*(?=[\[【])"
        )
        # CJK character range check
        self._cjk_range_re = re.compile(
            r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]"
        )
        # Episode indicator patterns for title boundary detection
        self._title_episode_boundary_re = re.compile(
            r"\s*(?:\[(\d+(?:\.\d+)?(?:\s*[-~～]\s*\d+(?:\.\d+)?)?)\]|"
            r"\s-\s*\d+(?:\.\d+)?(?:\s|$|\[|\()|"  # Allow ( for episode title
            r"第\d+[集话話]|"
            r"#\d+|"
            r"\bE[Pp]?\d+|"
            r"\bS\d+(?:\s*E\d+)?)"
        )

    def parse(self, raw_title: str) -> ParsedBangumi:
        """Parse a torrent title into structured data.

        Args:
            raw_title: The raw torrent title string to parse.

        Returns:
            A ParsedBangumi object containing extracted metadata.
        """
        # Normalize the title
        title = raw_title.strip().replace("\n", " ")

        # Extract brackets
        brackets = self._extract_brackets(title)

        # Identify group from first bracket
        group = self._identify_group(brackets)

        # Extract resolution
        resolution = self._extract_resolution(title)

        # Extract subtitle type
        subtitle = self._extract_subtitle(title)

        # Extract season
        season = self._extract_season(title)

        # Extract episode(s)
        episode, episode_end = self._extract_episode(title)

        # Extract codecs
        video_codec, audio_codec = self._extract_codecs(title)

        # Extract source/rip type
        source = self._extract_source(title)

        # Extract title and alternative titles
        main_title, alt_titles = self._extract_title(title, brackets)

        # Detect if this is a movie (theatrical release)
        is_movie = self._is_movie(title)

        # Extract episode type (OAD, OVA, SP)
        episode_type = self._extract_episode_type(title)

        # Extract version (v2, v3, etc.)
        version = self._extract_version(title)

        # For OAD/OVA/SP without explicit episode number, default to 1
        if episode_type is not None and episode is None:
            episode = 1

        # Build result with current implementation
        return ParsedBangumi(
            raw=raw_title,
            group=group,
            title=main_title,
            alt_titles=alt_titles,
            resolution=resolution,
            subtitle=subtitle,
            season=season,
            episode=episode,
            episode_end=episode_end,
            version=version,
            video_codec=video_codec,
            audio_codec=audio_codec,
            source=source,
            is_movie=is_movie,
            episode_type=episode_type,
        )

    def _extract_brackets(self, text: str) -> list[BracketContent]:
        """Extract content from all bracket types.

        Args:
            text: The text to extract brackets from.

        Returns:
            A list of BracketContent objects containing extracted content,
            sorted by their position in the string.
        """
        brackets: list[BracketContent] = []

        # Extract full-width brackets 【】
        for match in self._fullwidth_bracket_re.finditer(text):
            brackets.append(
                BracketContent(
                    content=match.group(1),
                    start=match.start(),
                    end=match.end(),
                    bracket_type="fullwidth",
                )
            )

        # Extract half-width brackets []
        for match in self._halfwidth_bracket_re.finditer(text):
            brackets.append(
                BracketContent(
                    content=match.group(1),
                    start=match.start(),
                    end=match.end(),
                    bracket_type="halfwidth",
                )
            )

        # Extract parentheses ()
        for match in self._parenthesis_re.finditer(text):
            brackets.append(
                BracketContent(
                    content=match.group(1),
                    start=match.start(),
                    end=match.end(),
                    bracket_type="parenthesis",
                )
            )

        # Sort by position
        brackets.sort(key=lambda b: b.start)

        return brackets

    def _identify_group(self, brackets: list[BracketContent]) -> Optional[str]:
        """Identify the fansub group from bracket contents.

        The group is typically in the first bracket. This method also handles
        multi-group formats like 'Group1&Group2'.

        Args:
            brackets: List of extracted bracket contents.

        Returns:
            The identified group name, or None if not found.
        """
        if not brackets:
            return None

        # First bracket typically contains the group
        first_bracket = brackets[0]
        content = first_bracket.content.strip()

        if not content:
            return None

        # Check for multi-group format and preserve it
        # e.g., "动漫国字幕组&LoliHouse" -> "动漫国字幕组&LoliHouse"
        return content

    def _extract_resolution(self, text: str) -> Optional[str]:
        """Extract video resolution from text.

        Supported formats:
        - Standard: 1080p, 720P, 2160p, 480p (normalized to uppercase P)
        - Dimensions: 1920x1080, 1280X720 (converted to standard format)
        - Aliases: 4K, UHD -> 2160P, FHD -> 1080P, HD -> 720P

        Args:
            text: The text to extract resolution from.

        Returns:
            Normalized resolution string (e.g., "1080P"), or None if not found.
        """
        # Dimension to resolution mapping
        dimension_map = {
            (3840, 2160): "2160P",
            (2560, 1440): "1440P",
            (1920, 1080): "1080P",
            (1280, 720): "720P",
            (854, 480): "480P",
            (640, 480): "480P",
        }

        # Try standard resolution format first (most common)
        match = self._resolution_standard_re.search(text)
        if match:
            return f"{match.group(1)}P"

        # Try dimension format (e.g., 1920x1080)
        match = self._resolution_dimensions_re.search(text)
        if match:
            width = int(match.group(1))
            height = int(match.group(2))
            # Try exact match first
            resolution = dimension_map.get((width, height))
            if resolution:
                return resolution
            # Fallback: use height to determine resolution
            if height >= 2160:
                return "2160P"
            elif height >= 1080:
                return "1080P"
            elif height >= 720:
                return "720P"
            elif height >= 480:
                return "480P"
            return None

        # Try 4K/UHD
        if self._resolution_4k_re.search(text):
            return "2160P"

        # Try FHD
        if self._resolution_fhd_re.search(text):
            return "1080P"

        # Try HD (only if not part of other words like "HDR")
        # Need to be careful here - HD should be standalone
        match = self._resolution_hd_re.search(text)
        if match:
            # Make sure it's not part of HDR, HDTV, etc.
            end = match.end()
            # Check if there's a letter after HD
            if end < len(text) and text[end].isalpha():
                return None
            return "720P"

        return None

    def _extract_subtitle(self, text: str) -> SubtitleType:
        """Extract subtitle language type from text.

        Detects various subtitle language markers commonly used by fansub groups:
        - Chinese Simplified (CHS, GB, 简体, etc.)
        - Chinese Traditional (CHT, BIG5, 繁体, etc.)
        - Japanese (JP, 日语, etc.)
        - English (EN, ENG, 英语, etc.)
        - Combined types (简繁, 简日, 繁日, etc.)

        Args:
            text: The text to extract subtitle type from.

        Returns:
            The detected SubtitleType enum value.
            Returns SubtitleType.UNKNOWN if no markers are found.
        """
        # Check for combined types first (more specific patterns)

        # Check for CHS+CHT+JP combination
        has_chs = bool(self._subtitle_chs_re.search(text))
        has_cht = bool(self._subtitle_cht_re.search(text))
        has_jp = bool(self._subtitle_jp_re.search(text))
        has_en = bool(self._subtitle_en_re.search(text))
        has_chs_cht = bool(self._subtitle_chs_cht_re.search(text))
        has_chs_jp = bool(self._subtitle_chs_jp_re.search(text))
        has_cht_jp = bool(self._subtitle_cht_jp_re.search(text))

        # Handle explicit combined types first
        if has_chs_cht:
            if has_jp or has_chs_jp or has_cht_jp:
                return SubtitleType.CHS_CHT_JP
            return SubtitleType.CHS_CHT

        if has_chs_jp:
            return SubtitleType.CHS_JP

        if has_cht_jp:
            return SubtitleType.CHT_JP

        # Handle individual markers with combinations
        if has_chs and has_cht and has_jp:
            return SubtitleType.CHS_CHT_JP

        if has_chs and has_cht:
            return SubtitleType.CHS_CHT

        if has_chs and has_jp:
            return SubtitleType.CHS_JP

        if has_cht and has_jp:
            return SubtitleType.CHT_JP

        # Handle single markers
        if has_chs:
            return SubtitleType.CHS

        if has_cht:
            return SubtitleType.CHT

        if has_jp:
            return SubtitleType.JP

        if has_en:
            return SubtitleType.EN

        # Check for embedded subtitle markers as fallback
        # (indicates subtitles exist but type is unknown)
        if self._subtitle_embedded_re.search(text):
            return SubtitleType.UNKNOWN

        return SubtitleType.UNKNOWN

    def _extract_season(self, text: str) -> int:
        """Extract season number from text.

        Supported formats:
        - Standard: S01, S02, Season 1, Season 2
        - Ordinal: 1st Season, 2nd Season, 3rd Season
        - Chinese: 第一季, 第二季, 第十二季 (supports compound numerals up to 12)
        - Part format: Part 1, Part 2
        - Roman numerals: II, III, IV (as standalone words)

        Args:
            text: The text to extract season from.

        Returns:
            The extracted season number.
            Returns 1 (default) if no season marker is found.
        """
        # Try standard format first (most common): S01, Season 1
        match = self._season_standard_re.search(text)
        if match:
            # Either group 1 (S01) or group 2 (Season 1) will match
            season_num = match.group(1) or match.group(2)
            if season_num:
                return int(season_num)

        # Try ordinal format: 1st Season, 2nd Season
        match = self._season_ordinal_re.search(text)
        if match:
            return int(match.group(1))

        # Try Chinese format: 第一季, 第二季
        match = self._season_chinese_re.search(text)
        if match:
            chinese_num = match.group(1)
            # Check if it's already an Arabic numeral
            if chinese_num.isdigit():
                return int(chinese_num)
            # Convert Chinese numeral to Arabic
            return self._chinese_to_arabic(chinese_num)

        # Try Part format: Part 1, Part 2
        match = self._season_part_re.search(text)
        if match:
            return int(match.group(1))

        # Try Roman numerals: II, III, IV
        match = self._season_roman_re.search(text)
        if match:
            return self._roman_to_arabic(match.group(1))

        # Default to season 1
        return 1

    def _chinese_to_arabic(self, chinese_num: str) -> int:
        """Convert Chinese numerals to Arabic numerals.

        Supports compound numerals up to 12 (十二).

        Args:
            chinese_num: Chinese numeral string (e.g., "一", "十", "十二")

        Returns:
            The corresponding Arabic numeral.
        """
        if not chinese_num:
            return 1

        # Handle simple single-character numerals
        if len(chinese_num) == 1:
            return self._chinese_numeral_map.get(chinese_num, 1)

        # Handle compound numerals with 十 (ten)
        if "十" in chinese_num:
            parts = chinese_num.split("十")
            if len(parts) == 2:
                tens_part = parts[0]
                ones_part = parts[1]

                # Calculate tens digit
                if tens_part == "":
                    tens = 10  # Just "十X" means 10+X
                else:
                    tens = self._chinese_numeral_map.get(tens_part, 1) * 10

                # Calculate ones digit
                if ones_part == "":
                    ones = 0  # "X十" means X*10
                else:
                    ones = self._chinese_numeral_map.get(ones_part, 0)

                return tens + ones

        # Fallback for unrecognized patterns
        return 1

    def _roman_to_arabic(self, roman: str) -> int:
        """Convert Roman numerals to Arabic numerals.

        Supports I through XII.

        Args:
            roman: Roman numeral string (e.g., "I", "II", "IV")

        Returns:
            The corresponding Arabic numeral.
        """
        roman_map = {
            "I": 1,
            "II": 2,
            "III": 3,
            "IV": 4,
            "V": 5,
            "VI": 6,
            "VII": 7,
            "VIII": 8,
            "IX": 9,
            "X": 10,
            "XI": 11,
            "XII": 12,
        }
        return roman_map.get(roman.upper(), 1)

    def _extract_episode(self, text: str) -> tuple[Optional[float], Optional[float]]:
        """Extract episode number(s) from text.

        Supported formats:
        - Bracketed: [01], [12], [01-12], [01~24]
        - Dash-separated: - 01, - 12
        - EP prefix: EP01, EP12, E01, E12
        - Chinese episode markers: 第01集, 第12话
        - Hash prefix: #01, #12
        - Batch ranges: 01-12, 01~24 (returns both start and end)
        - Version suffixes: v2, v3 (extracted and ignored for episode number)
        - END markers: END, Fin, Complete
        - Decimal episodes: 12.5, 48.5

        Args:
            text: The text to extract episode from.

        Returns:
            A tuple of (episode, episode_end).
            For single episodes: (episode, None)
            For batch ranges: (episode_start, episode_end)
            If no episode found: (None, None)
        """
        # Remove version suffixes for cleaner matching (v2, v3, etc.)
        text_clean = self._episode_version_re.sub("", text)

        # Try batch range in brackets first: [01-12], [01~24]
        match = self._episode_batch_bracket_re.search(text_clean)
        if match:
            start = self._parse_episode_number(match.group(1))
            end = self._parse_episode_number(match.group(2))
            if start is not None and end is not None:
                return (start, end)

        # Try standalone batch range: 01-12 (not in brackets, with context)
        match = self._episode_batch_standalone_re.search(text_clean)
        if match:
            start = self._parse_episode_number(match.group(1))
            end = self._parse_episode_number(match.group(2))
            if start is not None and end is not None:
                return (start, end)

        # Try single episode in brackets: [01], [12]
        match = self._episode_bracket_re.search(text_clean)
        if match:
            ep = self._parse_episode_number(match.group(1))
            if ep is not None:
                return (ep, None)

        # Try EP/E prefix: EP01, E01
        match = self._episode_ep_prefix_re.search(text_clean)
        if match:
            ep = self._parse_episode_number(match.group(1))
            if ep is not None:
                return (ep, None)

        # Try Chinese episode markers: 第01集, 第12话
        match = self._episode_chinese_re.search(text_clean)
        if match:
            ep = self._parse_episode_number(match.group(1))
            if ep is not None:
                return (ep, None)

        # Try Chinese episode markers without 第 prefix: [02集], [12话]
        match = self._episode_chinese_simple_re.search(text_clean)
        if match:
            ep = self._parse_episode_number(match.group(1))
            if ep is not None:
                return (ep, None)

        # Try hash prefix: #01, #12
        match = self._episode_hash_re.search(text_clean)
        if match:
            ep = self._parse_episode_number(match.group(1))
            if ep is not None:
                return (ep, None)

        # Try dash-separated: - 01, - 12 (common in titles)
        match = self._episode_dash_sep_re.search(text_clean)
        if match:
            ep = self._parse_episode_number(match.group(1))
            if ep is not None:
                return (ep, None)

        # Try SP prefix: SP01, SP02 (Special episodes)
        match = self._episode_sp_prefix_re.search(text_clean)
        if match:
            ep = self._parse_episode_number(match.group(1))
            if ep is not None:
                return (ep, None)

        # Try OVA/OAD with episode: OVA 01, OVA - 01, OAD 02
        match = self._episode_ova_oad_re.search(text_clean)
        if match:
            ep = self._parse_episode_number(match.group(1))
            if ep is not None:
                return (ep, None)

        # Check for END/Fin/Complete markers (indicates batch release)
        if self._episode_end_marker_re.search(text_clean):
            # Try single episode with END marker in brackets: [25_END], [25END]
            match = self._episode_end_bracket_re.search(text_clean)
            if match:
                ep = self._parse_episode_number(match.group(1))
                if ep is not None:
                    return (ep, None)

            # Try to find episode range before END marker
            match = self._episode_batch_end_re.search(text_clean)
            if match:
                start = self._parse_episode_number(match.group(1))
                end = self._parse_episode_number(match.group(2))
                if start is not None and end is not None:
                    return (start, end)

        return (None, None)

    def _extract_version(self, text: str) -> Optional[int]:
        """Extract version number from text (e.g., v2, v3).

        Args:
            text: The text to extract version from.

        Returns:
            Version number as int (e.g., 2 for v2), or None if not found.
        """
        match = self._episode_version_re.search(text)
        if match:
            # Extract the digit after 'v' or 'V'
            version_str = match.group(0)  # e.g., 'v2'
            return int(version_str[1:])  # Skip 'v', get '2'
        return None

    def _parse_episode_number(self, ep_str: str) -> Optional[float | int]:
        """Parse episode number string to int or float.

        Handles integers and decimals (e.g., "12", "12.5").
        Returns int for whole numbers, float for decimals.

        Args:
            ep_str: Episode number string.

        Returns:
            The parsed episode number as int (for whole numbers) or float (for decimals),
            or None if invalid.
        """
        if not ep_str:
            return None
        try:
            # Handle decimal episodes (12.5, 48.5)
            if "." in ep_str:
                return float(ep_str)
            return int(ep_str)
        except ValueError:
            return None

    def _extract_codecs(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Extract video and audio codecs from text.

        Detected video codecs (normalized):
        - HEVC: H.265, x265, H265
        - AVC: H.264, x264, H264
        - AV1
        - VP9

        Detected audio codecs:
        - AAC
        - FLAC
        - AC3
        - DTS (including DTS-HD)
        - EAC3 / E-AC-3
        - OPUS

        Args:
            text: The text to extract codecs from.

        Returns:
            A tuple of (video_codec, audio_codec).
            Either or both may be None if not detected.
        """
        video_codec: Optional[str] = None
        audio_codec: Optional[str] = None

        # Detect video codec (check more specific patterns first)
        if self._video_hevc_re.search(text):
            video_codec = "HEVC"
        elif self._video_avc_re.search(text):
            video_codec = "AVC"
        elif self._video_av1_re.search(text):
            video_codec = "AV1"
        elif self._video_vp9_re.search(text):
            video_codec = "VP9"

        # Detect audio codec
        if self._audio_flac_re.search(text):
            audio_codec = "FLAC"
        elif self._audio_eac3_re.search(text):
            audio_codec = "EAC3"
        elif self._audio_ac3_re.search(text):
            audio_codec = "AC3"
        elif self._audio_dts_re.search(text):
            audio_codec = "DTS"
        elif self._audio_opus_re.search(text):
            audio_codec = "OPUS"
        elif self._audio_aac_re.search(text):
            audio_codec = "AAC"

        return (video_codec, audio_codec)

    def _extract_source(self, text: str) -> Optional[str]:
        """Extract source/rip type from text.

        Detected source types (normalized):
        - Rip types: WEB-DL, WebRip, BDRip, BluRay, HDTV, DVDRip
        - Streaming services: CR, Baha, B-Global, ABEMA, Bilibili, AT-X

        Args:
            text: The text to extract source from.

        Returns:
            The detected source type string, or None if not detected.
        """
        # Check rip types first (more specific patterns)
        if self._source_webdl_re.search(text):
            return "WEB-DL"
        if self._source_webrip_re.search(text):
            return "WebRip"
        if self._source_bdrip_re.search(text):
            return "BDRip"
        if self._source_bluray_re.search(text):
            return "BluRay"
        if self._source_hdtv_re.search(text):
            return "HDTV"
        if self._source_dvdrip_re.search(text):
            return "DVDRip"

        # Check streaming services
        if self._source_cr_re.search(text):
            return "CR"
        if self._source_baha_re.search(text):
            return "Baha"
        if self._source_bglobal_re.search(text):
            return "B-Global"
        if self._source_abema_re.search(text):
            return "ABEMA"
        if self._source_bilibili_re.search(text):
            return "Bilibili"
        if self._source_atx_re.search(text):
            return "AT-X"

        return None

    def _is_movie(self, text: str) -> bool:
        """Detect if the title is a theatrical movie release.

        Detected markers:
        - Chinese movie markers: 剧场版, 劇場版, 电影, 電影
        - Japanese movie markers: 映画, 劇場版
        - English movie markers: Movie, The Movie

        Note: OVA/OAD/SP are NOT movies - they are special episode types
        and should be handled via episode_type field instead.

        Args:
            text: The text to check for movie markers.

        Returns:
            True if theatrical movie markers detected, False otherwise.
        """
        # Check Chinese movie markers
        if self._movie_chinese_re.search(text):
            return True

        # Check Japanese movie markers
        if self._movie_japanese_re.search(text):
            return True

        # Check English movie markers
        if self._movie_english_re.search(text):
            return True

        return False

    def _extract_episode_type(self, text: str) -> Optional[EpisodeType]:
        """Extract special episode type (OAD, OVA, SP) from text.

        Args:
            text: The text to check for episode type markers.

        Returns:
            EpisodeType enum value if special type detected, None for regular episodes.
        """
        # Check OAD markers first (more specific than OVA)
        if self._episode_type_oad_re.search(text):
            return EpisodeType.OAD

        # Check OVA markers
        if self._episode_type_ova_re.search(text):
            return EpisodeType.OVA

        # Check SP/Special markers
        if self._episode_type_sp_re.search(text):
            return EpisodeType.SP

        return None

    def _extract_title(
        self, text: str, brackets: list[BracketContent]
    ) -> tuple[Optional[str], list[str]]:
        """Extract main title and alternative titles from text.

        The title is typically found between the group bracket (first) and
        the episode indicator. Handles various formats:
        - Simple titles: "[Group] Title Name - 01"
        - Slash-separated multilingual: "[Group] 日本語タイトル / English Title - 01"
        - All-bracket format: "【Group】★01月新番[Title Name][01]..."
        - Embedded brackets in title: "[Group] Title (Part) Name - 01"

        Args:
            text: The text to extract title from.
            brackets: Pre-extracted bracket contents.

        Returns:
            A tuple of (main_title, alt_titles).
            main_title: The primary title (preferring CJK if available).
            alt_titles: List of alternative titles (other language versions).
        """
        if not brackets:
            return (None, [])

        # Find the title region (between first bracket and episode indicator)
        title_region = self._find_title_region(text, brackets)
        if not title_region:
            # Check for all-bracket format (title is in brackets)
            all_bracket_title = self._extract_title_from_brackets(brackets)
            if all_bracket_title:
                clean_title = self._clean_title(all_bracket_title)
                return (clean_title, []) if clean_title else (None, [])
            return (None, [])

        # Clean up the title region
        title_region = title_region.strip()
        if not title_region:
            # Check for all-bracket format
            all_bracket_title = self._extract_title_from_brackets(brackets)
            if all_bracket_title:
                clean_title = self._clean_title(all_bracket_title)
                return (clean_title, []) if clean_title else (None, [])
            return (None, [])

        # Check if this is all-bracket format (title region starts with bracket)
        # This happens when there's no plain text between group and next bracket
        if title_region.startswith("[") or title_region.startswith("【"):
            # All-bracket format - extract title from brackets instead
            all_bracket_title = self._extract_title_from_brackets(brackets)
            if all_bracket_title:
                clean_title = self._clean_title(all_bracket_title)
                return (clean_title, []) if clean_title else (None, [])
            # Fallback: still try to process this region

        # Check if title region has a decorator (e.g., ★剧场版) before a bracket
        # Examples: ★剧场版[电锯人 / 链锯人 蕾塞篇], 剧场版[Title]
        decorator_match = self._decorator_before_bracket_re.match(title_region)
        if decorator_match:
            # Strip decorator and check if remaining part starts with bracket
            remaining = title_region[decorator_match.end() :].strip()
            if remaining.startswith("[") or remaining.startswith("【"):
                # Find the content of the title bracket
                title_bracket_content = None
                for bracket in brackets[1:]:
                    content = bracket.content.strip()
                    if not content:
                        continue
                    # Skip metadata brackets
                    if self._is_metadata_bracket(content):
                        continue
                    # Skip pure episode numbers
                    if content.isdigit():
                        continue
                    # This should be the title bracket
                    title_bracket_content = content
                    break

                if title_bracket_content:
                    # Process as a normal title (supports multilingual /separated)
                    titles = self._split_multilingual_title(title_bracket_content)
                    if titles:
                        # Fall through to normal title processing below
                        title_region = title_bracket_content

        # Check for slash-separated multilingual titles
        titles = self._split_multilingual_title(title_region)

        if not titles:
            return (None, [])

        if len(titles) == 1:
            # Single title - clean and return
            clean_title = self._clean_title(titles[0])
            return (clean_title, []) if clean_title else (None, [])

        # Multiple titles - separate CJK from Latin
        cjk_titles: list[str] = []
        latin_titles: list[str] = []

        for t in titles:
            clean_t = self._clean_title(t)
            if clean_t:
                if self._contains_cjk(clean_t):
                    cjk_titles.append(clean_t)
                else:
                    latin_titles.append(clean_t)

        # Prefer CJK as main title, Latin as alternatives
        # When multiple CJK titles exist, prefer the longest one (more specific/complete)
        if cjk_titles:
            # Sort by length descending to get the longest title
            cjk_titles_sorted = sorted(cjk_titles, key=len, reverse=True)
            main_title = cjk_titles_sorted[0]
            alt_titles = cjk_titles_sorted[1:] + latin_titles
        elif latin_titles:
            main_title = latin_titles[0]
            alt_titles = latin_titles[1:]
        else:
            return (None, [])

        return (main_title, alt_titles)

    def _find_title_region(
        self, text: str, brackets: list[BracketContent]
    ) -> Optional[str]:
        """Find the region of text that likely contains the title.

        Args:
            text: The full text to search.
            brackets: Pre-extracted bracket contents.

        Returns:
            The extracted title region, or None if not found.
        """
        if not brackets:
            return None

        # Start after the first bracket (group)
        first_bracket = brackets[0]
        start_pos = first_bracket.end

        # Find the end position (episode indicator or next metadata bracket)
        end_pos = len(text)

        # Try to find episode indicator as boundary
        match = self._title_episode_boundary_re.search(text, start_pos)
        if match:
            end_pos = match.start()

        # Also check for metadata brackets between start and end
        # Use the first metadata bracket if it comes before the episode indicator
        for bracket in brackets[1:]:
            content = bracket.content.strip()
            # Skip empty brackets
            if not content:
                continue
            # Check if this bracket contains metadata
            if self._is_metadata_bracket(content):
                # Only use this bracket if it's before the current end_pos
                if bracket.start < end_pos:
                    end_pos = bracket.start
                break

        if start_pos >= end_pos:
            return None

        title_region = text[start_pos:end_pos]
        return title_region

    def _extract_title_from_brackets(
        self, brackets: list[BracketContent]
    ) -> Optional[str]:
        """Extract title from brackets (for all-bracket format).

        In formats like "【Group】★01月新番[Title][01][1080p]",
        the title is in a bracket rather than plain text.

        Args:
            brackets: Pre-extracted bracket contents.

        Returns:
            The extracted title if found in bracket format, None otherwise.
        """
        if len(brackets) < 2:
            return None

        # Seasonal marker pattern: NN月新番 (e.g., 4月新番, 01月新番, 10月新番)
        import re

        seasonal_marker_re = re.compile(r"^\d{1,2}月新番$")

        # Collect candidate title brackets (non-metadata, non-episode, non-seasonal)
        candidates: list[tuple[str, int]] = []  # (content, length)

        for bracket in brackets[1:]:
            content = bracket.content.strip()
            if not content:
                continue

            # Skip if it's metadata
            if self._is_metadata_bracket(content):
                continue

            # Skip if it's a number (episode)
            if content.isdigit():
                continue

            # Skip if it's a seasonal marker (e.g., 4月新番)
            if seasonal_marker_re.match(content):
                continue

            # Check if it contains slash (multilingual title marker)
            if "/" in content and self._contains_cjk(content):
                # Extract the CJK part as main title
                parts = content.split("/")
                for part in parts:
                    part = part.strip()
                    if self._contains_cjk(part):
                        return part
                # Fallback to first part
                return parts[0].strip()

            # Check if it contains CJK and looks like a title
            if self._contains_cjk(content) and len(content) >= 2:
                # This is a candidate - prefer longer titles
                candidates.append((content, len(content)))

        # Return the longest candidate (more likely to be the actual title)
        if candidates:
            # Sort by length descending and return the longest
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]

        return None

    def _split_multilingual_title(self, text: str) -> list[str]:
        """Split a title region into multiple titles.

        Handles formats like:
        - "日本語 / English" (single slash)
        - "日本語 // English // Alt" (double slash)
        - "日本語/English" (no space)

        Args:
            text: The title region to split.

        Returns:
            List of individual titles.
        """
        # Clean up leading special characters (★, etc.)
        text = re.sub(r"^[★☆◆◇●○▲△▼▽■□♦♠♣♥]+", "", text).strip()

        # Remove season/date prefixes like "01月新番"
        text = re.sub(r"^\d+月新番\s*", "", text).strip()

        # Remove surrounding brackets from title region
        # (for formats like "【Group】[Title][01]" where title is in brackets)
        text = re.sub(r"^\[([^\]]+)\]$", r"\1", text)  # halfwidth brackets
        text = re.sub(r"^【([^】]+)】$", r"\1", text)  # fullwidth brackets
        text = re.sub(r"^\(([^\)]+)\)$", r"\1", text)  # parentheses

        # Try double slash first (//), then single slash (/)
        # But don't split on slashes that are part of a title (like "Fate/")
        if " // " in text:
            parts = text.split(" // ")
            return [p.strip() for p in parts if p.strip()]

        # For single slash, only split if there's text on both sides
        # and the slash is between different scripts (CJK / Latin)
        if " / " in text:
            parts = text.split(" / ")
            # Validate that we have meaningful parts
            valid_parts = [p.strip() for p in parts if p.strip()]
            if len(valid_parts) >= 2:
                return valid_parts

        # Check for slash without spaces (but be careful with Fate/ style names)
        if "/" in text:
            # Don't split if slash is at the end (like "Fate/")
            # or at the start (like "/Title")
            if not text.endswith("/") and not text.startswith("/"):
                parts = text.split("/")
                # Only split if parts look like distinct titles
                # (one CJK, one Latin, or both have substance)
                valid_parts = [p.strip() for p in parts if p.strip()]
                if len(valid_parts) >= 2:
                    # Check if this looks like intentional splitting
                    has_cjk = any(self._contains_cjk(p) for p in valid_parts)
                    has_latin = any(not self._contains_cjk(p) for p in valid_parts)
                    if has_cjk and has_latin:
                        return valid_parts

        # No splitting - return as single title
        return [text] if text else []

    def _clean_title(self, title: str) -> Optional[str]:
        """Clean a title string by removing noise.

        Args:
            title: The title to clean.

        Returns:
            Cleaned title, or None if result is empty/invalid.
        """
        # Strip whitespace
        title = title.strip()

        # Remove leading/trailing special characters
        title = re.sub(r"^[-_・·]+|[-_・·]+$", "", title)

        # Remove trailing version indicators (v2, v3)
        title = re.sub(r"\s*[vV]\d+$", "", title)

        # Remove trailing season markers (S01, S02, etc.)
        title = re.sub(r"\s+S\d{1,2}$", "", title)

        # Remove trailing episode type markers with optional episode numbers
        # Handles: "Title OAD 01", "Title OVA", "Title SP 03", "Title OAD"
        # This prevents accumulation when re-parsing already renamed files
        title = re.sub(
            r"\s+(?:OAD|OVA|SP|Special)\s*-?\s*\d*$", "", title, flags=re.IGNORECASE
        )

        # Remove leading special decorators
        title = re.sub(r"^[★☆◆◇●○▲△▼▽■□♦♠♣♥]+\s*", "", title)

        # Clean up whitespace
        title = " ".join(title.split())

        # Validate result
        if not title:
            return None

        # Check if the title is just metadata
        if self._metadata_terms_re.match(title):
            return None

        return title

    def _is_metadata_bracket(self, content: str) -> bool:
        """Check if bracket content is metadata (resolution, codec, etc.).

        Args:
            content: The bracket content to check.

        Returns:
            True if content is metadata, False otherwise.
        """
        content_stripped = content.strip()
        if not content_stripped:
            return False

        # Check common metadata patterns
        if self._metadata_terms_re.match(content_stripped):
            return True

        # Check for resolution patterns
        if re.match(r"^\d{3,4}[pPxX×]\d*$", content_stripped):
            return True

        # Check for episode numbers (with optional version suffix like 03v2, 11v2)
        if re.match(r"^\d+(?:[vV]\d+)?$", content_stripped):
            return True

        # Check for codec with bit depth (HEVC-10bit, etc.)
        if re.match(
            r"^(?:HEVC|AVC|x26[45])[-_]?\d+bit$", content_stripped, re.IGNORECASE
        ):
            return True

        # Check for compound subtitle markers (e.g., "简繁内封字幕", "繁日内嵌字幕")
        # These are composed entirely of subtitle-related terms
        if self._is_compound_subtitle_marker(content_stripped):
            return True

        # Check for episode type markers (OAD, OVA, OVA1, SP, SP01, Special)
        if re.match(r"^(?:OAD|OVA\d*|SP\d*|Special)$", content_stripped, re.IGNORECASE):
            return True

        # Check for episode with END marker (e.g., 25_END, 25END, 25 END)
        if re.match(
            r"^\d+[\s_]?(?:END|FIN|COMPLETE|完结|完結)$",
            content_stripped,
            re.IGNORECASE,
        ):
            return True

        # Check for batch range with optional END marker (e.g., 01-08, 01-08Fin, 01~24 END)
        if re.match(
            r"^\d+(?:\.\d+)?\s*[-~～]\s*\d+(?:\.\d+)?"
            r"(?:\s*(?:END|FIN|COMPLETE|完结|完結))?$",
            content_stripped,
            re.IGNORECASE,
        ):
            return True

        return False

    def _is_compound_subtitle_marker(self, content: str) -> bool:
        """Check if content is a compound subtitle marker.

        Compound subtitle markers are strings composed entirely of subtitle-related
        terms like "简繁内封字幕" (CHS+CHT embedded subtitles).

        Args:
            content: The content to check.

        Returns:
            True if content is a compound subtitle marker, False otherwise.
        """
        if not content:
            return False

        # Subtitle-related characters/terms that can form compound markers
        # Each character or term in this set is subtitle-related
        subtitle_chars = set("简繁体中日内嵌封字幕双语")

        # Check if ALL characters in content are subtitle-related
        for char in content:
            if char not in subtitle_chars:
                return False

        # Must have at least 2 characters and contain 字幕 (subtitles) indicator
        return len(content) >= 2 and "字幕" in content

    def _contains_cjk(self, text: str) -> bool:
        """Check if text contains CJK characters.

        CJK includes:
        - Chinese (4e00-9fff)
        - Japanese Hiragana (3040-309f)
        - Japanese Katakana (30a0-30ff)
        - Korean (ac00-d7af)

        Args:
            text: The text to check.

        Returns:
            True if text contains CJK characters, False otherwise.
        """
        return bool(self._cjk_range_re.search(text))
