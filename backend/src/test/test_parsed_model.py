"""Tests for ParsedBangumi model and SubtitleType enum."""

import pytest

from module.models.parsed import ParsedBangumi, SubtitleType


class TestSubtitleType:
    """Tests for SubtitleType enum."""

    def test_enum_values(self):
        """Test that all enum values are correct strings."""
        assert SubtitleType.CHS.value == "CHS"
        assert SubtitleType.CHT.value == "CHT"
        assert SubtitleType.CHS_CHT.value == "CHS_CHT"
        assert SubtitleType.CHS_JP.value == "CHS_JP"
        assert SubtitleType.CHT_JP.value == "CHT_JP"
        assert SubtitleType.CHS_CHT_JP.value == "CHS_CHT_JP"
        assert SubtitleType.JP.value == "JP"
        assert SubtitleType.EN.value == "EN"
        assert SubtitleType.UNKNOWN.value == "UNKNOWN"

    def test_enum_is_str(self):
        """Test that SubtitleType values are strings (str Enum)."""
        for st in SubtitleType:
            assert isinstance(st.value, str)
            assert isinstance(st, str)

    def test_enum_iteration(self):
        """Test that we can iterate over all enum values."""
        values = list(SubtitleType)
        assert len(values) == 9
        expected = [
            SubtitleType.CHS,
            SubtitleType.CHT,
            SubtitleType.CHS_CHT,
            SubtitleType.CHS_JP,
            SubtitleType.CHT_JP,
            SubtitleType.CHS_CHT_JP,
            SubtitleType.JP,
            SubtitleType.EN,
            SubtitleType.UNKNOWN,
        ]
        assert values == expected

    def test_enum_string_comparison(self):
        """Test that enum values can be compared to strings."""
        assert SubtitleType.CHS == "CHS"
        assert SubtitleType.CHT == "CHT"

    def test_enum_from_string(self):
        """Test creating enum from string value."""
        assert SubtitleType("CHS") == SubtitleType.CHS
        assert SubtitleType("JP") == SubtitleType.JP
        assert SubtitleType("UNKNOWN") == SubtitleType.UNKNOWN


class TestParsedBangumiDefaults:
    """Tests for ParsedBangumi default values."""

    def test_minimal_init(self):
        """Test initialization with only required field (raw)."""
        parsed = ParsedBangumi(raw="[Group] Title - 01 [1080p].mkv")
        assert parsed.raw == "[Group] Title - 01 [1080p].mkv"
        assert parsed.group is None
        assert parsed.title is None
        assert parsed.alt_titles == []
        assert parsed.season == 1
        assert parsed.episode is None
        assert parsed.episode_end is None
        assert parsed.resolution is None
        assert parsed.subtitle is None
        assert parsed.video_codec is None
        assert parsed.audio_codec is None
        assert parsed.source is None
        assert parsed.container is None
        assert parsed.is_movie is False
        assert parsed.extra_info == []

    def test_default_season_is_one(self):
        """Test that default season is 1."""
        parsed = ParsedBangumi(raw="test")
        assert parsed.season == 1

    def test_default_is_movie_is_false(self):
        """Test that default is_movie is False."""
        parsed = ParsedBangumi(raw="test")
        assert parsed.is_movie is False

    def test_default_alt_titles_is_empty_list(self):
        """Test that default alt_titles is empty list."""
        parsed = ParsedBangumi(raw="test")
        assert parsed.alt_titles == []
        assert isinstance(parsed.alt_titles, list)

    def test_default_extra_info_is_empty_list(self):
        """Test that default extra_info is empty list."""
        parsed = ParsedBangumi(raw="test")
        assert parsed.extra_info == []
        assert isinstance(parsed.extra_info, list)

    def test_mutable_defaults_are_independent(self):
        """Test that mutable default values are independent per instance."""
        parsed1 = ParsedBangumi(raw="test1")
        parsed2 = ParsedBangumi(raw="test2")

        parsed1.alt_titles.append("Alt1")
        parsed1.extra_info.append("Extra1")

        assert parsed1.alt_titles == ["Alt1"]
        assert parsed2.alt_titles == []
        assert parsed1.extra_info == ["Extra1"]
        assert parsed2.extra_info == []


class TestParsedBangumiInitialization:
    """Tests for ParsedBangumi initialization with all fields."""

    def test_full_initialization(self):
        """Test initialization with all fields provided."""
        parsed = ParsedBangumi(
            raw="[Group] Title / Alt Title - 01 [1080p][HEVC][AAC][WEB-DL].mkv",
            group="Group",
            title="Title",
            alt_titles=["Alt Title", "Other Title"],
            season=2,
            episode=1,
            episode_end=12,
            resolution="1080P",
            subtitle=SubtitleType.CHS_CHT,
            video_codec="HEVC",
            audio_codec="AAC",
            source="WEB-DL",
            container="MKV",
            is_movie=False,
            extra_info=["10bit", "Ma10p"],
        )

        assert (
            parsed.raw
            == "[Group] Title / Alt Title - 01 [1080p][HEVC][AAC][WEB-DL].mkv"
        )
        assert parsed.group == "Group"
        assert parsed.title == "Title"
        assert parsed.alt_titles == ["Alt Title", "Other Title"]
        assert parsed.season == 2
        assert parsed.episode == 1
        assert parsed.episode_end == 12
        assert parsed.resolution == "1080P"
        assert parsed.subtitle == SubtitleType.CHS_CHT
        assert parsed.video_codec == "HEVC"
        assert parsed.audio_codec == "AAC"
        assert parsed.source == "WEB-DL"
        assert parsed.container == "MKV"
        assert parsed.is_movie is False
        assert parsed.extra_info == ["10bit", "Ma10p"]

    def test_movie_initialization(self):
        """Test initialization for a movie."""
        parsed = ParsedBangumi(
            raw="[Group] Movie Title [1080p].mkv",
            group="Group",
            title="Movie Title",
            is_movie=True,
        )

        assert parsed.title == "Movie Title"
        assert parsed.is_movie is True
        assert parsed.episode is None

    def test_with_subtitle_type(self):
        """Test initialization with various subtitle types."""
        for st in SubtitleType:
            parsed = ParsedBangumi(raw="test", subtitle=st)
            assert parsed.subtitle == st


class TestParsedBangumiToDict:
    """Tests for ParsedBangumi.to_dict() serialization."""

    def test_to_dict_minimal(self):
        """Test to_dict with minimal fields."""
        parsed = ParsedBangumi(raw="test")
        result = parsed.to_dict()

        assert result == {
            "raw": "test",
            "group": None,
            "title": None,
            "alt_titles": [],
            "season": 1,
            "episode": None,
            "episode_end": None,
            "resolution": None,
            "subtitle": None,
            "video_codec": None,
            "audio_codec": None,
            "source": None,
            "container": None,
            "is_movie": False,
            "extra_info": [],
        }

    def test_to_dict_full(self):
        """Test to_dict with all fields."""
        parsed = ParsedBangumi(
            raw="[Test] Anime - 05 [1080p].mkv",
            group="Test",
            title="Anime",
            alt_titles=["アニメ"],
            season=3,
            episode=5,
            episode_end=None,
            resolution="1080P",
            subtitle=SubtitleType.CHS_JP,
            video_codec="HEVC",
            audio_codec="FLAC",
            source="BDRip",
            container="MKV",
            is_movie=False,
            extra_info=["10bit"],
        )
        result = parsed.to_dict()

        assert result["raw"] == "[Test] Anime - 05 [1080p].mkv"
        assert result["group"] == "Test"
        assert result["title"] == "Anime"
        assert result["alt_titles"] == ["アニメ"]
        assert result["season"] == 3
        assert result["episode"] == 5
        assert result["episode_end"] is None
        assert result["resolution"] == "1080P"
        assert result["subtitle"] == "CHS_JP"
        assert result["video_codec"] == "HEVC"
        assert result["audio_codec"] == "FLAC"
        assert result["source"] == "BDRip"
        assert result["container"] == "MKV"
        assert result["is_movie"] is False
        assert result["extra_info"] == ["10bit"]

    def test_to_dict_subtitle_value_extraction(self):
        """Test that subtitle enum value is extracted correctly."""
        for st in SubtitleType:
            parsed = ParsedBangumi(raw="test", subtitle=st)
            result = parsed.to_dict()
            assert result["subtitle"] == st.value

    def test_to_dict_none_subtitle(self):
        """Test that None subtitle stays None in dict."""
        parsed = ParsedBangumi(raw="test", subtitle=None)
        result = parsed.to_dict()
        assert result["subtitle"] is None

    def test_to_dict_returns_dict(self):
        """Test that to_dict returns a dict type."""
        parsed = ParsedBangumi(raw="test")
        result = parsed.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_batch_episode(self):
        """Test to_dict with batch episode range."""
        parsed = ParsedBangumi(
            raw="[Group] Anime - 01-12 [1080p].mkv",
            episode=1,
            episode_end=12,
        )
        result = parsed.to_dict()

        assert result["episode"] == 1
        assert result["episode_end"] == 12
