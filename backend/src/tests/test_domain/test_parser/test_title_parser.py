from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from module.conf import settings
from module.domain.parser.title_parser import TitleParser


class TestTitleParser:
    def test_parse_without_openai(self):
        text = "[梦蓝字幕组]New Doraemon 哆啦A梦新番[747][2023.02.25][AVC][1080P][GB_JP][MP4]"
        result = TitleParser.raw_parser(text)
        assert result.group_name == "梦蓝字幕组"
        assert result.title_raw == "New Doraemon"
        assert result.dpi == "1080P"
        assert result.season == 1
        assert result.subtitle == "CHS_JP"  # Normalized from GB_JP (GB = CHS)

    @pytest.mark.skipif(
        not settings.experimental_openai.enable,
        reason="OpenAI is not enabled in settings",
    )
    def test_parse_with_openai(self):
        text = "[梦蓝字幕组]New Doraemon 哆啦A梦新番[747][2023.02.25][AVC][1080P][GB_JP][MP4]"
        result = TitleParser.raw_parser(text)
        assert result.group_name == "梦蓝字幕组"
        assert result.title_raw == "New Doraemon"
        assert result.dpi == "1080P"
        assert result.season == 1
        assert result.subtitle == "GB_JP"


class TestMikanParserWithRss:
    """TitleParser.mikan_parser_with_rss reads Mikan pages via parse_mikan_page."""

    FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "mikan"
    HOMEPAGE = "https://mikanani.me/Home/Episode/abc"

    def _run(self, html: str):
        req = MagicMock()
        req.__enter__.return_value = req
        req.get_html.return_value = html
        req.get_content.return_value = b"img"
        with patch(
            "module.domain.parser.title_parser.RequestContent", return_value=req
        ), patch(
            "module.domain.parser.title_parser.save_image",
            return_value="posters/x.jpg",
        ) as save:
            result = TitleParser.mikan_parser_with_rss(self.HOMEPAGE)
        return result, req, save

    def test_subscribe_button_fixture(self):
        html = (self.FIXTURES / "episode_page_subscribe_button.html").read_text()
        result, req, save = self._run(html)
        assert result.official_title == "身为悲剧始作俑者的最强邪恶BOSS女王为民竭心尽力。 第二季"
        assert result.season_rss_link == (
            "https://mikanani.me/RSS/Bangumi?bangumiId=3906&subgroupid=370"
        )
        assert result.poster_link == "posters/x.jpg"
        req.get_content.assert_called_once_with(
            "https://mikanani.me/images/Bangumi/202410/730372c2.jpg"
        )
        save.assert_called_once_with(b"img", "jpg")

    def test_no_ref_fixture_returns_empty_result(self):
        html = (self.FIXTURES / "episode_page_no_ref.html").read_text()
        result, _, _ = self._run(html)
        assert result.season_rss_link is None
        assert isinstance(result.official_title, str)
        assert isinstance(result.poster_link, str)

    def test_zero_bangumi_id_does_not_raise(self):
        html = (
            '<div class="bangumi-title"><a href="/Home/Bangumi/0">Show</a></div>'
            '<a data-bangumiid="0" data-subtitlegroupid="370">x</a>'
        )
        result, _, _ = self._run(html)
        assert result.official_title == "Show"
        assert result.season_rss_link is None
