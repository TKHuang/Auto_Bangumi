"""Tests for ParsedBangumi model and SubtitleType enum."""

import pytest

from module.domain.value_objects import ParsedBangumi, SubtitleType


class TestParsedBangumiDefaults:
    """Tests for ParsedBangumi default values."""

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


class TestParsedBangumiToDict:
    """Tests for ParsedBangumi.to_dict() serialization."""

    @pytest.mark.parametrize(
        "parsed, expected",
        [
            pytest.param(
                ParsedBangumi(raw="test"),
                {
                    "raw": "test",
                    "group": None,
                    "title": None,
                    "alt_titles": [],
                    "season": 1,
                    "episode": None,
                    "episode_end": None,
                    "version": None,
                    "resolution": None,
                    "subtitle": None,
                    "video_codec": None,
                    "audio_codec": None,
                    "source": None,
                    "container": None,
                    "is_movie": False,
                    "episode_type": None,
                    "extra_info": [],
                },
                id="minimal",
            ),
            pytest.param(
                ParsedBangumi(
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
                ),
                {
                    "raw": "[Test] Anime - 05 [1080p].mkv",
                    "group": "Test",
                    "title": "Anime",
                    "alt_titles": ["アニメ"],
                    "season": 3,
                    "episode": 5,
                    "episode_end": None,
                    "version": None,
                    "resolution": "1080P",
                    # Subtitle enum must serialize to its string value, not
                    # the enum member.
                    "subtitle": "CHS_JP",
                    "video_codec": "HEVC",
                    "audio_codec": "FLAC",
                    "source": "BDRip",
                    "container": "MKV",
                    "is_movie": False,
                    "episode_type": None,
                    "extra_info": ["10bit"],
                },
                id="full",
            ),
            pytest.param(
                ParsedBangumi(
                    raw="[Group] Anime - 01-12 [1080p].mkv",
                    episode=1,
                    episode_end=12,
                ),
                {
                    "raw": "[Group] Anime - 01-12 [1080p].mkv",
                    "group": None,
                    "title": None,
                    "alt_titles": [],
                    "season": 1,
                    "episode": 1,
                    "episode_end": 12,
                    "version": None,
                    "resolution": None,
                    "subtitle": None,
                    "video_codec": None,
                    "audio_codec": None,
                    "source": None,
                    "container": None,
                    "is_movie": False,
                    "episode_type": None,
                    "extra_info": [],
                },
                id="batch_episode",
            ),
        ],
    )
    def test_to_dict(self, parsed: ParsedBangumi, expected: dict):
        assert parsed.to_dict() == expected

    def test_to_dict_subtitle_value_extraction(self):
        """Test that every SubtitleType enum value is extracted correctly."""
        for st in SubtitleType:
            parsed = ParsedBangumi(raw="test", subtitle=st)
            result = parsed.to_dict()
            assert result["subtitle"] == st.value
