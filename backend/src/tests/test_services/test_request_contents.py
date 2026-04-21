import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from module.models import Torrent
from module.network.request_contents import RequestContent


SAMPLE_RSS_XML = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Mikan Project - Test Bangumi</title>
    <item>
      <title>[SubGroup] Test Anime - 01 [1080p]</title>
      <link>https://mikanani.me/Home/Episode/abc123</link>
      <enclosure url="https://mikanani.me/Download/20240101/deadbeefdeadbeefdeadbeefdeadbeefdeadbeef.torrent" type="application/x-bittorrent"/>
    </item>
    <item>
      <title>[SubGroup] Test Anime - 02 [1080p]</title>
      <link>https://mikanani.me/Home/Episode/def456</link>
      <enclosure url="https://mikanani.me/Download/20240102/cafebabecafebabecafebabecafebabecafebabe.torrent" type="application/x-bittorrent"/>
    </item>
    <item>
      <title>[SubGroup] Test Anime - 01-12 [1080p][Batch]</title>
      <link>https://mikanani.me/Home/Episode/ghi789</link>
      <enclosure url="https://mikanani.me/Download/20240103/1111111111111111111111111111111111111111.torrent" type="application/x-bittorrent"/>
    </item>
  </channel>
</rss>"""

SAMPLE_RSS_NO_ENCLOSURE = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>[SubGroup] Anime - 01</title>
      <link>magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&amp;tr=http://tracker</link>
    </item>
  </channel>
</rss>"""


def _make_mock_response(text, status_code=200):
    resp = MagicMock()
    resp.text = text
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"key": "value"}
    resp.content = b"binary content"
    return resp


class TestGetFilter:
    def test_none_uses_settings_filter(self):
        with patch("module.network.request_contents.settings") as mock_settings:
            mock_settings.rss_parser.filter = ["720", "\\d+-\\d+"]
            rc = RequestContent.__new__(RequestContent)
            result = rc._get_filter(None)
            assert result == "720|\\d+-\\d+"

    def test_empty_string_returns_none(self):
        rc = RequestContent.__new__(RequestContent)
        result = rc._get_filter("")
        assert result is None

    def test_comma_separated_converted_to_pipe(self):
        rc = RequestContent.__new__(RequestContent)
        result = rc._get_filter("720,1080")
        assert result == "720|1080"

    def test_single_value_unchanged(self):
        rc = RequestContent.__new__(RequestContent)
        result = rc._get_filter("720")
        assert result == "720"


class TestGetXml:
    def test_valid_xml_returns_element(self):
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=_make_mock_response(SAMPLE_RSS_XML))
        result = rc.get_xml("http://example.com/rss")
        assert isinstance(result, ET.Element)
        assert result.tag == "rss"

    def test_invalid_xml_returns_none(self):
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=_make_mock_response("<not valid xml"))
        result = rc.get_xml("http://example.com/bad")
        assert result is None

    def test_network_failure_returns_none(self):
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=None)
        result = rc.get_xml("http://example.com/fail")
        assert result is None


class TestGetTorrents:
    def _setup_rc(self, xml_text):
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=_make_mock_response(xml_text))
        return rc

    def test_returns_torrent_list_from_valid_rss(self):
        rc = self._setup_rc(SAMPLE_RSS_XML)
        with patch("module.network.request_contents.settings") as mock_settings:
            mock_settings.rss_parser.filter = []
            torrents = rc.get_torrents("http://example.com/rss", _filter="")
        assert len(torrents) == 3
        assert all(isinstance(t, Torrent) for t in torrents)

    def test_filter_excludes_matching_torrents(self):
        rc = self._setup_rc(SAMPLE_RSS_XML)
        with patch("module.network.request_contents.settings") as mock_settings:
            mock_settings.rss_parser.filter = []
            # Filter out batch releases matching \d+-\d+
            torrents = rc.get_torrents("http://example.com/rss", _filter="\\d+-\\d+")
        # The batch "01-12" item matches the filter so it's excluded
        assert len(torrents) == 2
        assert all("Batch" not in t.name for t in torrents)

    def test_limit_caps_results(self):
        rc = self._setup_rc(SAMPLE_RSS_XML)
        with patch("module.network.request_contents.settings") as mock_settings:
            mock_settings.rss_parser.filter = []
            torrents = rc.get_torrents("http://example.com/rss", _filter="", limit=1)
        assert len(torrents) == 1

    def test_extracts_hash_from_mikan_url(self):
        rc = self._setup_rc(SAMPLE_RSS_XML)
        with patch("module.network.request_contents.settings") as mock_settings:
            mock_settings.rss_parser.filter = []
            torrents = rc.get_torrents("http://example.com/rss", _filter="")
        assert torrents[0].hash == "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
        assert torrents[1].hash == "cafebabecafebabecafebabecafebabecafebabe"

    def test_extracts_hash_from_magnet_link(self):
        rc = self._setup_rc(SAMPLE_RSS_NO_ENCLOSURE)
        with patch("module.network.request_contents.settings") as mock_settings:
            mock_settings.rss_parser.filter = []
            torrents = rc.get_torrents("http://example.com/rss", _filter="")
        assert len(torrents) == 1
        assert torrents[0].hash == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    def test_network_failure_returns_empty_list(self):
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=None)
        with patch("module.network.request_contents.settings"):
            torrents = rc.get_torrents("http://example.com/fail")
        assert torrents == []

    def test_none_filter_uses_settings(self):
        rc = self._setup_rc(SAMPLE_RSS_XML)
        with patch("module.network.request_contents.settings") as mock_settings:
            # "Batch" filter should exclude the batch item
            mock_settings.rss_parser.filter = ["Batch"]
            torrents = rc.get_torrents("http://example.com/rss", _filter=None)
        assert len(torrents) == 2


class TestGetTorrentsWithFilter:
    def _setup_rc(self, xml_text):
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=_make_mock_response(xml_text))
        return rc

    def test_returns_dicts_with_filter_field(self):
        rc = self._setup_rc(SAMPLE_RSS_XML)
        with patch("module.network.request_contents.settings") as mock_settings:
            mock_settings.rss_parser.filter = []
            results = rc.get_torrents_with_filter("http://example.com/rss", _filter="")
        assert len(results) == 3
        assert all(isinstance(r, dict) for r in results)
        assert all("filter" in r for r in results)

    def test_filter_marks_matching_as_filtered(self):
        rc = self._setup_rc(SAMPLE_RSS_XML)
        with patch("module.network.request_contents.settings") as mock_settings:
            mock_settings.rss_parser.filter = []
            results = rc.get_torrents_with_filter("http://example.com/rss", _filter="Batch")
        filtered = [r for r in results if r["filter"]]
        unfiltered = [r for r in results if not r["filter"]]
        assert len(filtered) == 1
        assert "Batch" in filtered[0]["name"]
        assert len(unfiltered) == 2

    def test_network_failure_returns_empty_list(self):
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=None)
        with patch("module.network.request_contents.settings"):
            results = rc.get_torrents_with_filter("http://example.com/fail")
        assert results == []


class TestGetRssTitle:
    def test_extracts_title_and_strips_mikan_prefix(self):
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=_make_mock_response(SAMPLE_RSS_XML))
        title = rc.get_rss_title("http://example.com/rss")
        assert title == "Test Bangumi"

    def test_returns_none_on_network_failure(self):
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=None)
        title = rc.get_rss_title("http://example.com/fail")
        assert title is None

    def test_returns_title_without_prefix_as_is(self):
        xml = """<?xml version="1.0"?><rss><channel><title>My Custom Feed</title></channel></rss>"""
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=_make_mock_response(xml))
        title = rc.get_rss_title("http://example.com/rss")
        assert title == "My Custom Feed"

    def test_strips_search_result_prefix_from_mikan_search_rss(self):
        xml = '<?xml version="1.0"?><rss><channel><title>Mikan Project - 搜索结果: 能帮我弄干净吗？</title></channel></rss>'
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=_make_mock_response(xml))
        title = rc.get_rss_title("http://example.com/rss")
        assert title == "Mikan Project - 能帮我弄干净吗？"

    def test_strips_search_result_prefix_without_space(self):
        xml = '<?xml version="1.0"?><rss><channel><title>Mikan Project - 搜索结果:淫獄</title></channel></rss>'
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=_make_mock_response(xml))
        title = rc.get_rss_title("http://example.com/rss")
        assert title == "Mikan Project - 淫獄"

    def test_returns_none_when_no_title_element(self):
        xml = """<?xml version="1.0"?><rss><channel></channel></rss>"""
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=_make_mock_response(xml))
        title = rc.get_rss_title("http://example.com/rss")
        assert title is None


class TestGetJson:
    def test_returns_json_from_response(self):
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=_make_mock_response(""))
        result = rc.get_json("http://example.com/api")
        assert result == {"key": "value"}

    def test_returns_none_on_failure(self):
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=None)
        result = rc.get_json("http://example.com/api")
        assert result is None


class TestGetContent:
    def test_returns_binary_content(self):
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=_make_mock_response(""))
        result = rc.get_content("http://example.com/file")
        assert result == b"binary content"

    def test_returns_none_on_failure(self):
        rc = RequestContent.__new__(RequestContent)
        rc.get_url = MagicMock(return_value=None)
        result = rc.get_content("http://example.com/fail")
        assert result is None
