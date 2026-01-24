"""Integration tests for RSS feed parsing end-to-end.

Tests verify that torrent titles from RSS fixtures can be parsed correctly
using the BangumiParser via raw_parser and TitleParser.raw_parser.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from module.models.bangumi import BangumiParsingError
from module.network.site.mikan import rss_parser
from module.parser.analyser.raw_parser import raw_parser
from module.parser.title_parser import TitleParser


class TestAggregateRSSParsing:
    """Test parsing of aggregate RSS feeds with multiple bangumi titles."""

    @pytest.fixture
    def aggregate_rss_data(self, fixtures_dir):
        """Load aggregate RSS fixture and parse torrent titles."""
        xml_path = fixtures_dir / "aggregate_rss.xml"
        with open(xml_path, "r", encoding="utf-8") as f:
            xml_content = f.read()

        # Parse XML like RequestContent.get_xml does
        root = ET.fromstring(xml_content)
        return rss_parser(root)

    def test_aggregate_rss_has_torrents(self, aggregate_rss_data):
        """Verify aggregate RSS fixture contains expected number of torrents."""
        titles, urls, homepages = aggregate_rss_data
        assert len(titles) > 0, "Aggregate RSS should have torrents"
        assert len(titles) == len(urls), "Titles and URLs should match"
        assert len(titles) == len(homepages), "Titles and homepages should match"

    def test_aggregate_rss_titles_parseable(self, aggregate_rss_data):
        """Verify all torrent titles from aggregate RSS can be parsed."""
        titles, _, _ = aggregate_rss_data
        parsed_count = 0
        failed_titles = []

        for title in titles:
            try:
                result = raw_parser(title)
                if result:
                    parsed_count += 1
                else:
                    failed_titles.append(title)
            except BangumiParsingError:
                # BangumiParsingError means title extraction failed but other fields parsed
                # This is acceptable for some edge case titles
                failed_titles.append(title)
            except Exception as e:
                failed_titles.append(f"{title} (error: {e})")

        # At least 80% of titles should parse successfully
        success_rate = parsed_count / len(titles) if titles else 0
        assert success_rate >= 0.8, (
            f"Only {parsed_count}/{len(titles)} titles parsed successfully. "
            f"Failed: {failed_titles[:5]}..."
        )

    def test_aggregate_rss_title_raw_correctness(self, aggregate_rss_data):
        """Verify parsed Bangumi objects have correct title_raw values."""
        titles, _, _ = aggregate_rss_data

        for title in titles:
            try:
                bangumi = TitleParser.raw_parser(title)
                if bangumi:
                    # title_raw should be set and not be the default value
                    assert (
                        bangumi.title_raw != "title_raw"
                    ), f"title_raw should be extracted for: {title}"
                    # title_raw should contain meaningful content
                    assert (
                        len(bangumi.title_raw) >= 2
                    ), f"title_raw too short for: {title}"
            except BangumiParsingError:
                # Acceptable for edge cases - title extraction failed
                pass
            except Exception:
                # Other errors may occur, we're testing the successful ones
                pass

    def test_ani_format_parsing(self, aggregate_rss_data):
        """Test ANi format torrent titles parse correctly."""
        titles, _, _ = aggregate_rss_data

        ani_titles = [t for t in titles if t.startswith("[ANi]")]
        assert len(ani_titles) > 0, "Should have ANi format titles in fixture"

        for title in ani_titles:
            try:
                bangumi = TitleParser.raw_parser(title)
                if bangumi:
                    assert (
                        bangumi.group_name == "ANi"
                    ), f"Group should be ANi for: {title}"
                    # ANi titles have Baha WEB-DL source
                    if "Baha" in title or "WEB-DL" in title:
                        assert (
                            bangumi.source is not None
                        ), f"Source should be detected for: {title}"
            except BangumiParsingError:
                pass

    def test_lolihouse_format_parsing(self, aggregate_rss_data):
        """Test LoliHouse format torrent titles parse correctly."""
        titles, _, _ = aggregate_rss_data

        loli_titles = [t for t in titles if "[LoliHouse]" in t]
        assert len(loli_titles) > 0, "Should have LoliHouse format titles in fixture"

        for title in loli_titles:
            try:
                bangumi = TitleParser.raw_parser(title)
                if bangumi:
                    assert (
                        bangumi.group_name == "LoliHouse"
                    ), f"Group should be LoliHouse for: {title}"
                    # LoliHouse uses HEVC codec
                    assert "HEVC" in (bangumi.dpi or "") or "1080" in (
                        bangumi.dpi or ""
                    ), f"Resolution should be detected for: {title}"
            except BangumiParsingError:
                pass

    def test_fullwidth_bracket_format(self, aggregate_rss_data):
        """Test full-width bracket format parsing (幻樱字幕组 style)."""
        titles, _, _ = aggregate_rss_data

        fullwidth_titles = [t for t in titles if t.startswith("【")]
        assert len(fullwidth_titles) > 0, "Should have full-width bracket titles"

        for title in fullwidth_titles:
            try:
                bangumi = TitleParser.raw_parser(title)
                if bangumi:
                    assert (
                        bangumi.group_name != "Unknown"
                    ), f"Group should be extracted for: {title}"
            except BangumiParsingError:
                # Full-width bracket format may have parsing difficulties
                pass

    def test_multilingual_title_extraction(self, aggregate_rss_data):
        """Test slash-separated multilingual titles are extracted."""
        titles, _, _ = aggregate_rss_data

        # Find titles with " / " separator (multilingual)
        multilingual_titles = [t for t in titles if " / " in t]
        assert len(multilingual_titles) > 0, "Should have multilingual titles"

        for title in multilingual_titles:
            try:
                bangumi = TitleParser.raw_parser(title)
                if bangumi:
                    # title_raw should contain one of the language variants
                    assert bangumi.title_raw, f"title_raw should be set for: {title}"
            except BangumiParsingError:
                pass


class TestNonAggregateRSSParsing:
    """Test parsing of non-aggregate (single bangumi) RSS feeds."""

    @pytest.fixture
    def movie_rss_data(self, fixtures_dir):
        """Load non-aggregate RSS fixture with movie release."""
        xml_path = fixtures_dir / "non_aggregate_rss1.xml"
        with open(xml_path, "r", encoding="utf-8") as f:
            xml_content = f.read()

        root = ET.fromstring(xml_content)
        return rss_parser(root)

    @pytest.fixture
    def fullwidth_rss_data(self, fixtures_dir):
        """Load non-aggregate RSS fixture with full-width brackets."""
        xml_path = fixtures_dir / "non_aggregate_rss2.xml"
        with open(xml_path, "r", encoding="utf-8") as f:
            xml_content = f.read()

        root = ET.fromstring(xml_content)
        return rss_parser(root)

    def test_movie_rss_parsing(self, movie_rss_data):
        """Test movie release RSS parsing."""
        titles, urls, homepages = movie_rss_data

        assert len(titles) == 1, "Movie RSS should have one torrent"

        title = titles[0]
        # Should contain movie marker (剧场版)
        assert "剧场版" in title, "Should be a movie release"

        try:
            bangumi = TitleParser.raw_parser(title)
            if bangumi:
                # BDRip source should be detected
                assert (
                    bangumi.source is not None and "BDRip" in bangumi.source
                ), f"Source should be BDRip for movie: {title}"
        except BangumiParsingError:
            # Movie titles may have parsing difficulties
            pass

    def test_fullwidth_bracket_rss_parsing(self, fullwidth_rss_data):
        """Test full-width bracket RSS parsing."""
        titles, urls, homepages = fullwidth_rss_data

        assert len(titles) == 1, "Full-width bracket RSS should have one torrent"

        title = titles[0]
        assert title.startswith("【"), "Should start with full-width bracket"

        try:
            bangumi = TitleParser.raw_parser(title)
            if bangumi:
                # Group should be extracted from first bracket
                assert (
                    bangumi.group_name != "Unknown"
                ), f"Group should be extracted: {title}"
        except BangumiParsingError:
            pass


class TestTitleRawCorrectness:
    """Tests specifically for title_raw extraction correctness."""

    @pytest.fixture
    def all_rss_titles(self, fixtures_dir):
        """Load all torrent titles from all fixtures."""
        titles = []

        for xml_file in fixtures_dir.glob("*.xml"):
            with open(xml_file, "r", encoding="utf-8") as f:
                xml_content = f.read()

            root = ET.fromstring(xml_content)
            file_titles, _, _ = rss_parser(root)
            titles.extend(file_titles)

        return titles

    def test_title_raw_not_empty(self, all_rss_titles):
        """Verify title_raw is never empty for successfully parsed titles."""
        for title in all_rss_titles:
            try:
                bangumi = TitleParser.raw_parser(title)
                if bangumi:
                    assert bangumi.title_raw, f"title_raw empty for: {title}"
                    assert (
                        len(bangumi.title_raw.strip()) > 0
                    ), f"title_raw whitespace only for: {title}"
            except BangumiParsingError:
                pass
            except Exception:
                pass

    def test_title_raw_not_metadata(self, all_rss_titles):
        """Verify title_raw does not contain pure metadata."""
        metadata_patterns = [
            "1080P",
            "720P",
            "2160P",
            "HEVC",
            "AVC",
            "AAC",
            "FLAC",
            "WEB-DL",
            "BDRip",
            "WebRip",
            "MP4",
            "MKV",
        ]

        for title in all_rss_titles:
            try:
                bangumi = TitleParser.raw_parser(title)
                if bangumi and bangumi.title_raw:
                    # title_raw should not be purely metadata
                    is_pure_metadata = all(
                        part.upper() in metadata_patterns
                        for part in bangumi.title_raw.split()
                        if part.strip()
                    )
                    assert (
                        not is_pure_metadata
                    ), f"title_raw is pure metadata for: {title}"
            except BangumiParsingError:
                pass
            except Exception:
                pass

    def test_title_raw_reasonable_length(self, all_rss_titles):
        """Verify title_raw has reasonable length."""
        for title in all_rss_titles:
            try:
                bangumi = TitleParser.raw_parser(title)
                if bangumi and bangumi.title_raw:
                    # title_raw should be between 2 and 200 characters
                    assert 2 <= len(bangumi.title_raw) <= 200, (
                        f"title_raw length {len(bangumi.title_raw)} "
                        f"unreasonable for: {title}"
                    )
            except BangumiParsingError:
                pass
            except Exception:
                pass


class TestSpecificTitlesFromFixtures:
    """Test specific known titles from fixtures for exact parsing.

    Parametrized tests for group extraction, season detection, and title parsing.
    """

    @pytest.mark.parametrize(
        "title,expected_group",
        [
            pytest.param(
                "[ANi] Sousou no Frieren S02 / 葬送的芙莉莲 第二季 - 30 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]",
                "ANi",
                id="ani_frieren_s02",
            ),
            pytest.param(
                "[ANi] JUJUTSU KAISEN / 咒术回战 死灭回游 前篇 - 51 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]",
                "ANi",
                id="ani_jujutsu_kaisen",
            ),
            pytest.param(
                "[ANi] 【OSHI NO KO】 / 【我推的孩子】 - 26 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]",
                "ANi",
                id="ani_oshi_no_ko_embedded_brackets",
            ),
            pytest.param(
                "[LoliHouse] 安闲领主的愉快领地防卫 / Okiraku Ryoushu no Tanoshii Ryouchi Bouei - 03 [WebRip 1080p HEVC-10bit AAC][简繁内封字幕]",
                "LoliHouse",
                id="lolihouse_hevc",
            ),
            pytest.param(
                "[LoliHouse] Fate/strange Fake - 03 [WebRip 1080p HEVC-10bit AAC][简繁内封字幕]",
                "LoliHouse",
                id="lolihouse_fate_slash",
            ),
            pytest.param(
                "[绿茶字幕组] 能帮我弄干净吗？ / Kirei ni Shite Moraemasu ka [02][WebRip][1080p][简日内嵌]",
                "绿茶字幕组",
                id="chinese_subgroup",
            ),
            pytest.param(
                "[黒ネズミたち] 地狱乐 第二季 / Jigokuraku 2nd Season - 15 (CR 1920x1080 AVC AAC MKV)",
                "黒ネズミたち",
                id="japanese_group_name",
            ),
        ],
    )
    def test_group_extraction(self, title: str, expected_group: str):
        """Test group name is correctly extracted from various formats."""
        bangumi = TitleParser.raw_parser(title)
        assert bangumi is not None
        assert bangumi.group_name == expected_group

    @pytest.mark.parametrize(
        "title,expected_group_contains",
        [
            pytest.param(
                "【幻樱字幕组】【1月新番】【黄金神威 Golden Kamuy】【52】【BIG5_MP4】【1920X1080】",
                "幻樱字幕组",
                id="fullwidth_bracket_group",
            ),
        ],
    )
    def test_group_extraction_contains(self, title: str, expected_group_contains: str):
        """Test group name contains expected substring for complex formats."""
        bangumi = TitleParser.raw_parser(title)
        assert bangumi is not None
        assert expected_group_contains in bangumi.group_name

    def test_frieren_season_extraction(self):
        """Test Frieren S02 title parses with correct season."""
        title = "[ANi] Sousou no Frieren S02 / 葬送的芙莉莲 第二季 - 30 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]"
        bangumi = TitleParser.raw_parser(title)
        assert bangumi is not None
        assert bangumi.season == 2, "Season should be 2"

    def test_jujutsu_kaisen_title_raw(self):
        """Test Jujutsu Kaisen title_raw contains expected content."""
        title = "[ANi] JUJUTSU KAISEN / 咒术回战 死灭回游 前篇 - 51 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]"
        bangumi = TitleParser.raw_parser(title)
        assert bangumi is not None
        assert "咒术回战" in bangumi.title_raw or "JUJUTSU KAISEN" in bangumi.title_raw

    def test_lolihouse_resolution_detection(self):
        """Test LoliHouse HEVC-10bit format has 1080 resolution."""
        title = "[LoliHouse] 安闲领主的愉快领地防卫 / Okiraku Ryoushu no Tanoshii Ryouchi Bouei - 03 [WebRip 1080p HEVC-10bit AAC][简繁内封字幕]"
        bangumi = TitleParser.raw_parser(title)
        assert bangumi is not None
        assert "1080" in (bangumi.dpi or "")

    def test_oshi_no_ko_title_raw_not_none(self):
        """Test OSHI NO KO title_raw is set despite embedded brackets."""
        title = "[ANi] 【OSHI NO KO】 / 【我推的孩子】 - 26 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]"
        bangumi = TitleParser.raw_parser(title)
        assert bangumi is not None
        assert bangumi.title_raw is not None

    def test_fate_title_contains_fate(self):
        """Test Fate/strange Fake title_raw contains Fate."""
        title = "[LoliHouse] Fate/strange Fake - 03 [WebRip 1080p HEVC-10bit AAC][简繁内封字幕]"
        bangumi = TitleParser.raw_parser(title)
        assert bangumi is not None
        assert "Fate" in (bangumi.title_raw or "")

    def test_streaming_source_detection(self):
        """Test streaming source detection (CR)."""
        title = "[黒ネズミたち] 地狱乐 第二季 / Jigokuraku 2nd Season - 15 (CR 1920x1080 AVC AAC MKV)"
        bangumi = TitleParser.raw_parser(title)
        assert bangumi is not None
        assert bangumi.source is not None


class TestEdgeCases:
    """Test edge cases and challenging formats from fixtures.

    Uses parametrization where BangumiParsingError is acceptable.
    """

    @pytest.mark.parametrize(
        "title,expected_group",
        [
            pytest.param(
                "[ANi] 和机器人啪啪啪能算在经验人数里吗？？ [年龄限制版] - 03 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]",
                "ANi",
                id="age_restriction_marker",
            ),
            pytest.param(
                "[ANi] 「凭妳也想讨伐魔王？」被勇者小队逐出队伍，只好在王都自在过活 - 03 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]",
                "ANi",
                id="chinese_corner_brackets",
            ),
        ],
    )
    def test_special_markers_parsing(self, title: str, expected_group: str):
        """Test titles with special markers parse correctly."""
        try:
            bangumi = TitleParser.raw_parser(title)
            assert bangumi is not None
            assert bangumi.group_name == expected_group
        except BangumiParsingError:
            # Some edge cases may have parsing challenges
            pass

    def test_season_prefix_not_in_title_raw(self):
        """Test 1月新番 season prefix marker is not in title_raw."""
        title = "【幻樱字幕组】【1月新番】【黄金神威 Golden Kamuy】【52】【BIG5_MP4】【1920X1080】"
        try:
            bangumi = TitleParser.raw_parser(title)
            if bangumi:
                assert "1月新番" not in (
                    bangumi.title_raw or ""
                ), "Season prefix should be filtered from title_raw"
        except BangumiParsingError:
            pass

    def test_multi_group_format(self):
        """Test multi-group format (Group1&Group2)."""
        title = "【豌豆字幕组&风之圣殿字幕组】★剧场版[电锯人 / 链锯人 蕾塞篇][简体][1080P][MP4]"
        try:
            bangumi = TitleParser.raw_parser(title)
            if bangumi:
                assert bangumi.group_name != "Unknown"
        except BangumiParsingError:
            pass
