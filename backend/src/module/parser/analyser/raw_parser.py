import logging

from module.models import Episode
from module.models.bangumi import BangumiParsingError
from module.parser.analyser.bangumi_parser import BangumiParser

logger = logging.getLogger(__name__)


def raw_parser(raw: str) -> Episode | None:
    """Parse raw torrent title using BangumiParser.

    This function uses the new BangumiParser internally to parse torrent titles
    and maps the result to the Episode model for backward compatibility.

    Args:
        raw: The raw torrent title string to parse.

    Returns:
        Episode object with parsed information, or None if parsing fails.

    Raises:
        BangumiParsingError: When title extraction fails but other fields are parsed.
    """
    # Normalize full-width brackets to half-width for better compatibility
    normalized = raw.replace("【", "[").replace("】", "]")

    parser = BangumiParser()
    parsed = parser.parse(normalized)

    # Map ParsedBangumi to Episode fields
    # Determine individual title fields from title and alt_titles
    # Priority: CJK title as title_zh/title_jp, Latin title as title_en
    title_en = None
    title_zh = None
    title_jp = None

    # Helper to detect if string contains CJK characters
    def is_cjk(text: str) -> bool:
        if not text:
            return False
        # Check for Chinese, Japanese (Hiragana/Katakana), Korean characters
        for char in text:
            code_point = ord(char)
            if (
                0x4E00 <= code_point <= 0x9FFF  # CJK Unified Ideographs
                or 0x3040 <= code_point <= 0x309F  # Hiragana
                or 0x30A0 <= code_point <= 0x30FF  # Katakana
                or 0xAC00 <= code_point <= 0xD7AF
            ):  # Hangul
                return True
        return False

    # Helper to detect if string contains Japanese-specific characters (Hiragana/Katakana)
    def is_japanese(text: str) -> bool:
        if not text:
            return False
        for char in text:
            code_point = ord(char)
            if (
                0x3040 <= code_point <= 0x309F  # Hiragana
                or 0x30A0 <= code_point <= 0x30FF  # Katakana
            ):
                return True
        return False

    # Helper to detect if string is primarily Latin script
    def is_latin(text: str) -> bool:
        if not text:
            return False
        # Check if text contains significant Latin characters
        latin_count = sum(1 for c in text if c.isalpha() and ord(c) < 0x0800)
        return latin_count >= 3  # At least 3 Latin letters

    # Helper to split mixed CJK/Latin titles
    def split_mixed_title(title: str) -> tuple[str | None, str | None]:
        """Split title containing both CJK and Latin characters.

        Returns (latin_part, cjk_part) tuple.

        Note: Only split titles that have clear language boundaries.
        Mixed titles like "16bit 的感动 ANOTHER LAYER" should NOT be split
        as they are intentionally mixed and should be kept as CJK title.
        """
        if not title:
            return None, None

        # Check if this is an intentionally mixed title (CJK words interspersed with Latin)
        # If so, don't split - keep as CJK title
        words = title.split()
        word_types = []  # Track type of each word: 'cjk', 'latin', 'other'
        for word in words:
            has_cjk = is_cjk(word)
            has_latin = is_latin(word)
            if has_cjk:
                word_types.append("cjk")
            elif has_latin:
                word_types.append("latin")
            else:
                word_types.append("other")

        # Check for pattern: latin/other followed by cjk followed by latin
        # This indicates an intentionally mixed title (e.g., "16bit 的感动 ANOTHER LAYER")
        cjk_indices = [i for i, t in enumerate(word_types) if t == "cjk"]
        if cjk_indices:
            first_cjk = min(cjk_indices)
            last_cjk = max(cjk_indices)
            # If there's Latin before AND after CJK, it's likely intentionally mixed
            has_latin_before = any(word_types[i] == "latin" for i in range(first_cjk))
            has_latin_after = any(
                word_types[i] == "latin" for i in range(last_cjk + 1, len(word_types))
            )
            if has_latin_before and has_latin_after:
                # Intentionally mixed - keep as CJK title
                return None, title

        # Standard split: try to separate Latin and CJK parts
        # Preserve symbols (like ~) that decorate titles
        latin_parts = []
        cjk_parts = []
        symbol_buffer = []  # Buffer for symbols between language transitions

        for i, word in enumerate(words):
            word_is_cjk = is_cjk(word)
            word_is_latin = is_latin(word)

            if word_is_cjk:
                # Flush symbol buffer to CJK if CJK parts exist
                if symbol_buffer and cjk_parts:
                    cjk_parts.extend(symbol_buffer)
                symbol_buffer = []
                cjk_parts.append(word)
            elif word_is_latin:
                # Flush symbol buffer to Latin if Latin parts exist
                if symbol_buffer and latin_parts:
                    latin_parts.extend(symbol_buffer)
                elif symbol_buffer:
                    # Symbols before first Latin word - include them
                    latin_parts.extend(symbol_buffer)
                symbol_buffer = []
                latin_parts.append(word)
            else:
                # Symbol or other character - buffer it
                # Could be decorator like ~ or punctuation
                symbol_buffer.append(word)

        # Handle trailing symbols - add to Latin if Latin parts exist
        if symbol_buffer and latin_parts:
            latin_parts.extend(symbol_buffer)
        elif symbol_buffer and cjk_parts:
            cjk_parts.extend(symbol_buffer)

        latin_title = " ".join(latin_parts) if latin_parts else None
        cjk_title = "".join(cjk_parts) if cjk_parts else None

        return latin_title, cjk_title

    # Helper to clean brackets from titles (workaround for BangumiParser bug)
    def clean_brackets(title: str) -> str:
        """Remove leading/trailing brackets from title."""
        if not title:
            return title
        # Strip leading [ or ] and trailing [ or ]
        title = title.strip()
        while title and (title[0] in "[]【】" or title[-1] in "[]【】"):
            if title[0] in "[]【】":
                title = title[1:]
            if title and title[-1] in "[]【】":
                title = title[:-1]
            title = title.strip()
        return title

    # Process title and alt_titles to extract language-specific titles
    # If there are alt_titles, it means "/" separator was found - use that split
    if parsed.alt_titles:
        # Title and alt_titles already separated by BangumiParser
        # Assign based on language detection
        for idx, title in enumerate([parsed.title] + parsed.alt_titles):
            if not title:
                continue

            # Clean any brackets from title (workaround for BangumiParser parsing issues)
            title = clean_brackets(title)
            if not title:
                continue

            has_latin = is_latin(title)
            has_cjk = is_cjk(title)

            if has_latin and has_cjk:
                # Mixed title - prefer as Chinese title (old parser behavior)
                if not title_zh:
                    title_zh = title
            elif has_latin and not title_en:
                title_en = title
            elif has_cjk:
                if not title_zh:
                    title_zh = title
                elif not title_jp and is_japanese(title):
                    # Only assign to title_jp if it contains Japanese characters
                    # (Hiragana/Katakana), otherwise it's likely another Chinese title
                    title_jp = title
    else:
        # No alt_titles - single title that might be mixed
        title = parsed.title
        if title:
            # Clean brackets from title (workaround for BangumiParser parsing issues)
            title = clean_brackets(title)

        if not title:
            pass  # No title at all
        else:
            has_latin = is_latin(title)
            has_cjk = is_cjk(title)

            if has_latin and has_cjk:
                # Mixed title - try to split it
                latin, cjk = split_mixed_title(title)
                if latin and not title_en:
                    title_en = latin
                if cjk and not title_zh:
                    title_zh = cjk
            elif has_latin and not title_en:
                title_en = title
            elif has_cjk:
                if not title_zh:
                    title_zh = title

    # Check if all title fields are empty - raise BangumiParsingError for manual input
    if not title_en and not title_zh and not title_jp:
        partial_data = {
            "raw_title": raw,
            "group": parsed.group,
            "season": parsed.season,
            "resolution": parsed.resolution,
            "subtitle": parsed.subtitle.value if parsed.subtitle else None,
        }
        raise BangumiParsingError(
            raw_title=raw,
            partial_data=partial_data,
            msg_en="Failed to extract title from torrent name. Please provide title manually.",
            msg_zh="无法从种子名称中提取标题。请手动输入标题。",
        )

    # Convert episode to int (Episode model expects int, but ParsedBangumi uses float)
    episode = int(parsed.episode) if parsed.episode is not None else 0

    # Map subtitle enum to string value
    subtitle = parsed.subtitle.value if parsed.subtitle else None

    # Season raw is not provided by ParsedBangumi, use empty string for compatibility
    season_raw = ""

    return Episode(
        title_en=title_en,
        title_zh=title_zh,
        title_jp=title_jp,
        season=parsed.season,
        season_raw=season_raw,
        episode=episode,
        sub=subtitle,
        group=parsed.group,
        resolution=parsed.resolution,
        source=parsed.source,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    title = "[动漫国字幕组&LoliHouse] THE MARGINAL SERVICE - 08 [WebRip 1080p HEVC-10bit AAC][简繁内封字幕]"
    logger.info(raw_parser(title))
