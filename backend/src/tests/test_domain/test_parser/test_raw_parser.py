"""Tests for raw_parser module.

This module tests the raw_parser function which handles various torrent title formats
from different fansub groups and sources.
"""

import pytest

from module.domain.parser.analyser import raw_parser


class TestRawParser:
    """Tests for raw_parser function with various real-world torrent title formats."""

    @pytest.mark.parametrize(
        "content,expected",
        [
            pytest.param(
                "[喵萌奶茶屋&LoliHouse] 鹿乃子乃子乃子虎视眈眈 / Shikanoko Nokonoko Koshitantan\n- 01 [WebRip 1080p HEVC-10bit AAC][简繁内封字幕]",
                {
                    "group": "喵萌奶茶屋&LoliHouse",
                    "title_zh": "鹿乃子乃子乃子虎视眈眈",
                    "title_en": "Shikanoko Nokonoko Koshitantan",
                    "resolution": "1080P",
                    "episode": 1,
                    "season": 1,
                },
                id="issue_794_multi_group_slash_titles",
            ),
            pytest.param(
                "[LoliHouse] 轮回七次的反派大小姐，在前敌国享受随心所欲的新婚生活\n / 7th Time Loop - 12 [WebRip 1080p HEVC-10bit AAC][简繁内封字幕][END]",
                {
                    "group": "LoliHouse",
                    "title_zh": "轮回七次的反派大小姐，在前敌国享受随心所欲的新婚生活",
                    "title_en": "7th Time Loop",
                    "resolution": "1080P",
                    "episode": 12,
                    "season": 1,
                },
                id="issue_679_newline_and_end_marker",
            ),
            pytest.param(
                "【幻樱字幕组】【4月新番】【古见同学有交流障碍症 第二季 Komi-san wa, Komyushou Desu. S02】【22】【GB_MP4】【1920X1080】",
                {
                    "title_en": "Komi-san wa, Komyushou Desu.",
                    "resolution": "1080P",
                    "episode": 22,
                    "season": 2,
                },
                id="fullwidth_brackets_with_season",
            ),
            pytest.param(
                "[百冬练习组&LoliHouse] BanG Dream! 少女乐团派对！☆PICO FEVER！ / Garupa Pico: Fever! - 26 [WebRip 1080p HEVC-10bit AAC][简繁内封字幕][END] [101.69 MB]",
                {
                    "group": "百冬练习组&LoliHouse",
                    "title_zh": "BanG Dream! 少女乐团派对！☆PICO FEVER！",
                    "resolution": "1080P",
                    "episode": 26,
                    "season": 1,
                },
                id="special_chars_and_file_size",
            ),
            pytest.param(
                "【喵萌奶茶屋】★04月新番★[夏日重现/Summer Time Rendering][11][1080p][繁日双语][招募翻译]",
                {
                    "group": "喵萌奶茶屋",
                    "title_en": "Summer Time Rendering",
                    "resolution": "1080P",
                    "episode": 11,
                    "season": 1,
                },
                id="fullwidth_with_star_decorations",
            ),
            pytest.param(
                "[Lilith-Raws] 关于我在无意间被隔壁的天使变成废柴这件事 / Otonari no Tenshi-sama - 09 [Baha][WEB-DL][1080p][AVC AAC][CHT][MP4]",
                {
                    "group": "Lilith-Raws",
                    "title_zh": "关于我在无意间被隔壁的天使变成废柴这件事",
                    "title_en": "Otonari no Tenshi-sama",
                    "resolution": "1080P",
                    "episode": 9,
                    "season": 1,
                },
                id="baha_source_with_slash_title",
            ),
            pytest.param(
                "[梦蓝字幕组]New Doraemon 哆啦A梦新番[747][2023.02.25][AVC][1080P][GB_JP][MP4]",
                {
                    "group": "梦蓝字幕组",
                    "title_zh": "哆啦A梦新番",
                    "title_en": "New Doraemon",
                    "resolution": "1080P",
                    "episode": 747,
                    "season": 1,
                },
                id="high_episode_number_with_date",
            ),
            pytest.param(
                "[MagicStar] 假面骑士Geats / 仮面ライダーギーツ EP33 [WEBDL] [1080p] [TTFC]【生】",
                {
                    "group": "MagicStar",
                    "title_zh": "假面骑士Geats",
                    "title_jp": "仮面ライダーギーツ",
                    "resolution": "1080P",
                    "episode": 33,
                    "season": 1,
                },
                id="japanese_title_with_ep_prefix",
            ),
            pytest.param(
                "【极影字幕社】★4月新番 天国大魔境 Tengoku Daimakyou 第05话 GB 720P MP4（字幕社招人内详）",
                {
                    "group": "极影字幕社",
                    "title_zh": "天国大魔境",
                    "title_en": "Tengoku Daimakyou",
                    "resolution": "720P",
                    "episode": 5,
                    "season": 1,
                },
                id="fullwidth_with_recruitment_note",
            ),
        ],
    )
    def test_raw_parser_real_world_cases(self, content: str, expected: dict) -> None:
        """Test raw_parser with real-world torrent title formats.

        These test cases are derived from actual RSS feeds and GitHub issues,
        covering various fansub group naming conventions and title formats.
        """
        info = raw_parser(content)

        # Assert expected fields
        if "group" in expected:
            assert info.group == expected["group"], f"Group mismatch for: {content}"
        if "title_zh" in expected:
            assert (
                info.title_zh == expected["title_zh"]
            ), f"title_zh mismatch for: {content}"
        if "title_en" in expected:
            assert (
                info.title_en == expected["title_en"]
            ), f"title_en mismatch for: {content}"
        if "title_jp" in expected:
            assert (
                info.title_jp == expected["title_jp"]
            ), f"title_jp mismatch for: {content}"
        if "resolution" in expected:
            assert (
                info.resolution == expected["resolution"]
            ), f"Resolution mismatch for: {content}"
        if "episode" in expected:
            assert (
                info.episode == expected["episode"]
            ), f"Episode mismatch for: {content}"
        if "season" in expected:
            assert info.season == expected["season"], f"Season mismatch for: {content}"


class TestRawParserEdgeCases:
    """Tests for edge cases that previously had parsing issues.

    These tests verify that previously problematic title formats now parse correctly.
    """

    @pytest.mark.edge_case
    def test_nier_automata_colon_in_title(self) -> None:
        """NieR:Automata title with colon should parse correctly.

        Tests all-bracket format with mixed CJK/Latin title containing colon.
        """
        content = "[织梦字幕组][尼尔：机械纪元 NieR Automata Ver1.1a][02集][1080P][AVC][简日双语]"
        info = raw_parser(content)
        assert info.group == "织梦字幕组"
        assert info.title_zh == "尼尔：机械纪元"
        assert info.title_en == "NieR Automata Ver1.1a"
        assert info.resolution == "1080P"
        assert info.episode == 2
        assert info.season == 1

    @pytest.mark.edge_case
    def test_sugar_apple_tilde_title(self) -> None:
        """English title with tilde decoration should parse correctly.

        Tests preservation of ~ characters in title names.
        """
        content = "【喵萌奶茶屋】★07月新番★[银砂糖师与黑妖精 ~ Sugar Apple Fairy Tale ~][13][1080p][简日双语][招募翻译]"
        info = raw_parser(content)
        assert info.group == "喵萌奶茶屋"
        assert info.title_zh == "银砂糖师与黑妖精"
        assert info.title_en == "~ Sugar Apple Fairy Tale ~"
        assert info.resolution == "1080P"
        assert info.episode == 13
        assert info.season == 1

    @pytest.mark.edge_case
    def test_16bit_number_at_start(self) -> None:
        """Title starting with numbers should parse correctly.

        Tests intentionally mixed CJK/Latin titles that should not be split.
        """
        content = "[ANi]  16bit 的感动 ANOTHER LAYER - 01 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]"
        info = raw_parser(content)
        assert info.group == "ANi"
        assert info.title_zh == "16bit 的感动 ANOTHER LAYER"
        assert info.resolution == "1080P"
        assert info.episode == 1
        assert info.season == 1

    @pytest.mark.edge_case
    def test_movie_release_with_decorator(self) -> None:
        """Movie release with ★剧场版 decorator should parse correctly.

        Tests handling of decorators like ★剧场版 between group bracket and title bracket.
        The title bracket contains two Chinese names separated by /.
        """
        content = "【豌豆字幕组&风之圣殿字幕组】★剧场版[电锯人 / 链锯人 蕾塞篇][简体][1080P][MP4]"
        info = raw_parser(content)
        assert info.group == "豌豆字幕组&风之圣殿字幕组"
        assert info.title_zh == "链锯人 蕾塞篇"
        # Second Chinese title should be detected as alt title (also Chinese, not Japanese)
        # Note: Both 电锯人 and 链锯人 蕾塞篇 are Chinese titles for Chainsaw Man
        assert info.title_jp is None or info.title_jp == ""
        assert info.resolution == "1080P"
        assert info.season == 1


class TestBatchReleaseWithEndMarkers:
    """Tests for batch release parsing with END/Fin/Complete markers.

    These tests verify that batch episode ranges with end markers like
    [01-08Fin], [01-08 Fin], [01~24 END], [01-12 COMPLETE] are correctly
    recognized as metadata brackets and parsed properly.
    """

    @pytest.mark.parametrize(
        "content,expected",
        [
            # Batch range with Fin marker (no space) - Season 2
            pytest.param(
                "[TestSub] 测试动画 第二季 / Test Anime 2 [01-08Fin][1080p][简繁内封]",
                {
                    "group": "TestSub",
                    "title_zh": "测试动画 第二季",
                    "title_en": "Test Anime 2",
                    "resolution": "1080P",
                    "episode": 1,  # Start of batch
                    "season": 2,
                },
                id="batch_fin_no_space",
            ),
            # Batch range with Fin marker and space
            pytest.param(
                "[TestSub] 测试动画 / Test Anime [01-08 Fin][1080p][简体内嵌]",
                {
                    "group": "TestSub",
                    "title_zh": "测试动画",
                    "title_en": "Test Anime",
                    "resolution": "1080P",
                    "episode": 1,  # Start of batch
                    "season": 1,
                },
                id="batch_fin_with_space",
            ),
            # Batch range with END marker
            pytest.param(
                "[TestSub] 测试动画 / Test Anime [01-12END][720p][简繁内封]",
                {
                    "group": "TestSub",
                    "title_zh": "测试动画",
                    "title_en": "Test Anime",
                    "resolution": "720P",
                    "episode": 1,  # Start of batch
                    "season": 1,
                },
                id="batch_end_no_space",
            ),
            # Batch range with END marker and space
            pytest.param(
                "[TestSub] 测试动画 / Test Anime [01-24 END][1080p][简体内嵌]",
                {
                    "group": "TestSub",
                    "title_zh": "测试动画",
                    "title_en": "Test Anime",
                    "resolution": "1080P",
                    "episode": 1,  # Start of batch
                    "season": 1,
                },
                id="batch_end_with_space",
            ),
            # Batch range with COMPLETE marker
            pytest.param(
                "[TestSub] 测试动画 / Test Anime [01-12 COMPLETE][1080p][简繁内封]",
                {
                    "group": "TestSub",
                    "title_zh": "测试动画",
                    "title_en": "Test Anime",
                    "resolution": "1080P",
                    "episode": 1,  # Start of batch
                    "season": 1,
                },
                id="batch_complete",
            ),
            # Batch range with tilde separator
            pytest.param(
                "[TestSub] 测试动画 / Test Anime [01~24Fin][1080p][简繁内封]",
                {
                    "group": "TestSub",
                    "title_zh": "测试动画",
                    "title_en": "Test Anime",
                    "resolution": "1080P",
                    "episode": 1,  # Start of batch
                    "season": 1,
                },
                id="batch_tilde_fin",
            ),
            # Batch range with Chinese end marker
            pytest.param(
                "[TestSub] 测试动画 / Test Anime [01-12 完结][1080p][简繁内封]",
                {
                    "group": "TestSub",
                    "title_zh": "测试动画",
                    "title_en": "Test Anime",
                    "resolution": "1080P",
                    "episode": 1,  # Start of batch
                    "season": 1,
                },
                id="batch_chinese_end",
            ),
            # Plain batch range without end marker (control case)
            pytest.param(
                "[TestSub] 测试动画 / Test Anime [01-12][1080p][简繁内封]",
                {
                    "group": "TestSub",
                    "title_zh": "测试动画",
                    "title_en": "Test Anime",
                    "resolution": "1080P",
                    "episode": 1,  # Start of batch
                    "season": 1,
                },
                id="batch_plain",
            ),
            # Single episode (control case)
            pytest.param(
                "[TestSub] 测试动画 / Test Anime [08][1080p][简繁内封]",
                {
                    "group": "TestSub",
                    "title_zh": "测试动画",
                    "title_en": "Test Anime",
                    "resolution": "1080P",
                    "episode": 8,
                    "season": 1,
                },
                id="single_episode",
            ),
            # Single episode with version tag
            pytest.param(
                "[TestSub] 测试动画 / Test Anime [04v2][1080p][简体内嵌]",
                {
                    "group": "TestSub",
                    "title_zh": "测试动画",
                    "title_en": "Test Anime",
                    "resolution": "1080P",
                    "episode": 4,
                    "season": 1,
                },
                id="single_episode_v2",
            ),
            # Season 2 single episode
            pytest.param(
                "[TestSub] 测试动画 第二季 / Test Anime 2 [05][1080p][简繁内封]",
                {
                    "group": "TestSub",
                    "title_zh": "测试动画 第二季",
                    "title_en": "Test Anime 2",
                    "resolution": "1080P",
                    "episode": 5,
                    "season": 2,
                },
                id="season2_single_episode",
            ),
        ],
    )
    def test_batch_release_parsing(self, content: str, expected: dict) -> None:
        """Test parsing of batch releases with various END markers.

        Batch releases should have the episode bracket recognized as metadata
        (not included in title) and episode should be the START of the range.
        """
        info = raw_parser(content)

        assert info.group == expected["group"], f"Group mismatch for: {content}"
        assert (
            info.title_zh == expected["title_zh"]
        ), f"title_zh mismatch for: {content}"
        assert (
            info.title_en == expected["title_en"]
        ), f"title_en mismatch for: {content}"
        assert (
            info.resolution == expected["resolution"]
        ), f"Resolution mismatch for: {content}"
        assert info.episode == expected["episode"], f"Episode mismatch for: {content}"
        assert info.season == expected["season"], f"Season mismatch for: {content}"


class TestEpisodeWithParenthesizedTitle:
    """Tests for episode numbers followed by parenthesized episode titles.

    Pattern: "Title - 00(Episode Title)" where the parentheses contain episode-specific text.
    """

    @pytest.mark.parametrize(
        "content,expected",
        [
            # Episode 0 with parenthesized subtitle
            pytest.param(
                "[TestSub] Test Anime - 00(Prologue) [WebRip 1080p HEVC-10bit AAC].mkv",
                {
                    "group": "TestSub",
                    "title_en": "Test Anime",
                    "resolution": "1080P",
                    "episode": 0,
                    "season": 1,
                },
                id="episode_00_with_parenthesized_title",
            ),
            # Episode with longer parenthesized subtitle
            pytest.param(
                "[TestSub] Test Anime - 05(The Beginning of the End) [1080p].mkv",
                {
                    "group": "TestSub",
                    "title_en": "Test Anime",
                    "resolution": "1080P",
                    "episode": 5,
                    "season": 1,
                },
                id="episode_with_long_parenthesized_title",
            ),
        ],
    )
    def test_episode_with_parenthesized_title(
        self, content: str, expected: dict
    ) -> None:
        """Test parsing of episodes with parenthesized episode titles.

        The parenthesized content should be recognized as episode metadata,
        not included in the anime title.
        """
        info = raw_parser(content)

        assert info.group == expected["group"], f"Group mismatch for: {content}"
        assert (
            info.title_en == expected["title_en"]
        ), f"title_en mismatch for: {content}"
        assert (
            info.resolution == expected["resolution"]
        ), f"Resolution mismatch for: {content}"
        assert info.episode == expected["episode"], f"Episode mismatch for: {content}"
        assert info.season == expected["season"], f"Season mismatch for: {content}"
