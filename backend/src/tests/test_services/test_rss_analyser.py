"""RSSAnalyser.analyse_torrents: title_raw matching on a real feed."""

import xml.etree.ElementTree as ET
from unittest.mock import patch

from module.models import RSSItem
from module.network.request_contents import RequestContent
from module.rss.analyser import RSSAnalyser

FEED = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><title>Mikan Project - Test</title>
<item><title>[SubGroup] Test Anime - 01 [1080p]</title>
<link>https://mikanani.me/Home/Episode/a1</link>
<enclosure url="https://mikanani.me/Download/20240101/deadbeefdeadbeefdeadbeefdeadbeefdeadbeef.torrent"/></item>
<item><title>[SubGroup] Other Show - 01 [1080p]</title>
<link>https://mikanani.me/Home/Episode/a2</link>
<enclosure url="https://mikanani.me/Download/20240102/cafebabecafebabecafebabecafebabecafebabe.torrent"/></item>
<item><title>no episode here</title>
<link>https://mikanani.me/Home/Episode/a3</link>
<enclosure url="https://mikanani.me/Download/20240103/1111111111111111111111111111111111111111.torrent"/></item>
</channel></rss>"""


def _analyse(title_raw):
    rss = RSSItem(url="http://example.com/rss", parser="mikan")
    with (
        patch.object(RequestContent, "get_xml", return_value=ET.fromstring(FEED)),
        patch("module.network.request_contents.settings") as mock_settings,
    ):
        mock_settings.rss_parser.filter = []
        return RSSAnalyser().analyse_torrents(rss, _filter="", title_raw=title_raw)


def test_analyse_torrents_title_raw_matches_substring():
    names = [t["name"] for t in _analyse("Test Anime")]
    assert names == ["[SubGroup] Test Anime - 01 [1080p]"]


def test_analyse_torrents_skips_unparseable():
    names = [t["name"] for t in _analyse("no episode")]
    assert names == []


def test_analyse_torrents_without_title_raw_returns_all():
    assert len(_analyse(None)) == 3
