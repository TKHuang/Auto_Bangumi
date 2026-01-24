"""Shared test fixtures for parser tests.

This module provides common fixtures used across all parser test files.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from module.parser.analyser.bangumi_parser import BangumiParser


# --- Parser Fixtures ---


@pytest.fixture
def parser() -> BangumiParser:
    """Create a BangumiParser instance for tests.

    Returns a fresh instance for each test to ensure clean state.
    Scope is 'function' (default) for test isolation.
    """
    return BangumiParser()


# --- Test Data Fixtures ---


@pytest.fixture
def sample_torrent_names() -> dict[str, list[str]]:
    """Common sample torrent names organized by category.

    Returns a dictionary mapping category names to lists of sample torrent titles.
    """
    return {
        "simple": [
            "[Group] Title - 01 [1080p]",
            "[SubGroup] Anime Name - 12 [720P][HEVC]",
            "[Fansub] Show Title - 05 [1080P][AVC AAC]",
        ],
        "chinese_groups": [
            "[喵萌奶茶屋] 动漫名称 - 01 [1080p][简日双语]",
            "[幻樱字幕组] 番剧标题 - 05 [BIG5_MP4][1920X1080]",
            "[织梦字幕组] 新番名 - 03 [1080P][AVC][简日双语]",
        ],
        "multi_group": [
            "[喵萌奶茶屋&LoliHouse] Title - 01 [1080p]",
            "[SweetSub&LoliHouse] Anime - 01 [WebRip 1080p HEVC-10bit AAC]",
            "[百冬练习组&LoliHouse] Show - 01 [WebRip 1080p HEVC-10bit AAC]",
        ],
        "fullwidth_brackets": [
            "【动漫国字幕组】★01月新番[标题][01][1080P][繁体][MP4]",
            "【幻樱字幕组】【4月新番】【动漫标题】【01】【GB_MP4】【1920X1080】",
            "【极影字幕社】★4月新番 动漫名 Title 第01话 GB 720P MP4",
        ],
        "with_season": [
            "[Group] Title S02 - 01 [1080p]",
            "[Group] Anime 第二季 - 05 [720P]",
            "[Group] Show Season 2 - 12 [1080p]",
        ],
        "with_slash_titles": [
            "[Group] 中文名 / English Name - 01 [1080p]",
            "[LoliHouse] 日文名 / Romaji / English - 01 [WebRip 1080p HEVC-10bit AAC]",
            "[ANi] Chinese / English Title - 03 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]",
        ],
    }


@pytest.fixture
def sample_codec_strings() -> dict[str, list[str]]:
    """Sample codec strings for testing codec detection.

    Returns a dictionary mapping codec categories to lists of test strings.
    """
    return {
        "hevc": ["HEVC", "hevc", "H.265", "H265", "x265", "X265", "HEVC-10bit"],
        "avc": ["AVC", "avc", "H.264", "H264", "x264", "X264", "AVC-8bit"],
        "audio": ["AAC", "FLAC", "AC3", "DTS", "EAC3", "OPUS", "DTS-HD"],
    }


@pytest.fixture
def sample_resolution_strings() -> dict[str, list[tuple[str, str]]]:
    """Sample resolution strings for testing resolution extraction.

    Returns a dictionary mapping resolution categories to lists of
    (input_string, expected_resolution) tuples.
    """
    return {
        "standard": [
            ("1080p", "1080P"),
            ("1080P", "1080P"),
            ("720p", "720P"),
            ("720P", "720P"),
            ("2160p", "2160P"),
            ("480p", "480P"),
        ],
        "dimension": [
            ("1920x1080", "1080P"),
            ("1920X1080", "1080P"),
            ("1280x720", "720P"),
            ("1280X720", "720P"),
            ("3840x2160", "2160P"),
        ],
        "alias": [
            ("4K", "2160P"),
            ("4k", "2160P"),
            ("UHD", "2160P"),
            ("FHD", "1080P"),
            ("HD", "720P"),
        ],
    }


@pytest.fixture
def sample_subtitle_strings() -> dict[str, list[str]]:
    """Sample subtitle type strings for testing subtitle detection.

    Returns a dictionary mapping subtitle categories to lists of test strings.
    """
    return {
        "chs": ["简体", "简中", "CHS", "GB", "简体中文", "简日双语", "简繁内封字幕"],
        "cht": ["繁体", "繁中", "CHT", "BIG5", "繁體", "繁體中文"],
        "jp": ["日语", "JP", "日文", "日本語"],
        "en": ["英语", "EN", "ENG", "English"],
        "combined": ["CHS_JP", "GB_JP", "简繁日内封字幕", "简繁内封字幕"],
    }


@pytest.fixture
def sample_source_strings() -> dict[str, list[str]]:
    """Sample source type strings for testing source detection.

    Returns a dictionary mapping source categories to lists of test strings.
    """
    return {
        "web": ["WEB-DL", "WebRip", "WebDL", "WEBDL", "WEB"],
        "bluray": ["BDRip", "BluRay", "Blu-ray", "BD", "BDRemux"],
        "tv": ["HDTV", "TVRip", "HDTVRIP"],
        "dvd": ["DVDRip", "DVD", "DVDR"],
        "streaming": ["Baha", "CR", "B-Global", "ABEMA", "Bilibili", "AT-X"],
    }


@pytest.fixture
def edge_case_titles() -> dict[str, Any]:
    """Load edge case titles from JSON fixture file.

    Returns the parsed JSON data from edge_case_titles.json.
    """
    fixture_path = Path(__file__).parent / "fixtures" / "edge_case_titles.json"
    if fixture_path.exists():
        with open(fixture_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"test_cases": []}


@pytest.fixture
def sample_season_strings() -> dict[str, list[tuple[str, int]]]:
    """Sample season strings for testing season extraction.

    Returns a dictionary mapping season format categories to lists of
    (input_string, expected_season) tuples.
    """
    return {
        "s_format": [
            ("S01", 1),
            ("S02", 2),
            ("S2", 2),
            ("s01", 1),
            ("S10", 10),
        ],
        "season_format": [
            ("Season 1", 1),
            ("Season 2", 2),
            ("Season 10", 10),
            ("season 1", 1),
        ],
        "chinese_season": [
            ("第一季", 1),
            ("第二季", 2),
            ("第三季", 3),
        ],
        "ordinal": [
            ("1st Season", 1),
            ("2nd Season", 2),
            ("3rd Season", 3),
        ],
    }


# --- Path Fixtures ---


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory.

    Returns the Path to backend/src/test/fixtures/.
    """
    return Path(__file__).parent / "fixtures"
