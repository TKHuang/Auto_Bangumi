"""Tests for BangumiParser."""

import pytest

from zen_bangumi.domain.parser.bangumi_parser import BangumiParser
from zen_bangumi.domain.parser.models import EpisodeType, SubtitleType


@pytest.fixture
def parser():
    """Create a BangumiParser instance."""
    return BangumiParser()


def test_parser_initialization(parser):
    """Test that parser initializes correctly."""
    assert parser is not None


def test_parse_basic_title(parser):
    """Test parsing a basic anime title."""
    result = parser.parse(
        "[Lilith-Raws] Kakkou no Iinazuke - 07 [Baha][WEB-DL][1080p][AVC AAC][CHT][MP4].mp4"
    )
    
    assert result.group == "Lilith-Raws"
    assert result.title == "Kakkou no Iinazuke"
    assert result.episode == 7.0
    assert result.resolution == "1080P"
    assert result.subtitle == SubtitleType.CHT
    assert result.source == "WEB-DL"
    assert result.video_codec == "AVC"
    assert result.audio_codec == "AAC"


def test_parse_season_episode(parser):
    """Test parsing title with season and episode."""
    result = parser.parse("[Group] Anime Title - 05 [1080p].mkv")
    
    assert result.episode == 5.0
    assert result.resolution == "1080P"


def test_parse_batch_release(parser):
    """Test parsing batch release with episode range."""
    result = parser.parse("[Group] Anime Title [01-12] [1080p].mkv")
    
    assert result.episode == 1.0
    assert result.episode_end == 12.0


def test_parse_ova(parser):
    """Test parsing OVA episode."""
    result = parser.parse("[Group] Anime Title OVA 01 [1080p].mkv")
    
    assert result.episode_type == EpisodeType.OVA
    assert result.episode == 1.0


def test_parse_chinese_title(parser):
    """Test parsing Chinese anime title."""
    result = parser.parse("[字幕组] 动画标题 第01集 [简体][1080P].mp4")
    
    assert result.episode == 1.0
    assert result.subtitle == SubtitleType.CHS
    assert result.resolution == "1080P"


def test_parse_version_suffix(parser):
    """Test parsing title with version suffix."""
    result = parser.parse("[Group] Anime Title - 05v2 [1080p].mkv")
    
    assert result.episode == 5.0
    assert result.version == 2


def test_parse_multiple_resolutions(parser):
    """Test that parser correctly identifies various resolution formats."""
    test_cases = [
        ("[Group] Title [720p].mkv", "720P"),
        ("[Group] Title [1080P].mkv", "1080P"),
        ("[Group] Title [4K].mkv", "2160P"),
        ("[Group] Title [FHD].mkv", "1080P"),
    ]
    
    for title, expected_resolution in test_cases:
        result = parser.parse(title)
        assert result.resolution == expected_resolution


def test_parse_subtitle_types(parser):
    """Test parsing various subtitle types."""
    test_cases = [
        ("[Group] Title [CHS].mkv", SubtitleType.CHS),
        ("[Group] Title [CHT].mkv", SubtitleType.CHT),
        ("[Group] Title [简体].mkv", SubtitleType.CHS),
        ("[Group] Title [繁体].mkv", SubtitleType.CHT),
        ("[Group] Title [简繁].mkv", SubtitleType.CHS_CHT),
    ]
    
    for title, expected_subtitle in test_cases:
        result = parser.parse(title)
        assert result.subtitle == expected_subtitle
