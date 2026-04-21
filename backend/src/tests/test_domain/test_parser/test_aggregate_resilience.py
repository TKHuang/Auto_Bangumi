"""Aggregate-RSS parsing resilience.

Regression: a single torrent that triggers ``BangumiParsingError`` (e.g. a
release with ``★``-delimited fields) used to abort the whole aggregate batch
in ``RSSAnalyser.torrents_to_data``, causing every other show in the feed
to disappear from the WebUI's review dialog.

The expected behaviour: per-torrent errors are skipped with a debug log and
the rest of the feed is still grouped into Bangumi previews.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from module.domain.value_objects import BangumiParsingError
from module.domain.parser.analyser.mikan_parser import MikanParserResult
from module.models import Bangumi, RSSItem, Torrent
from module.rss.analyser import RSSAnalyser


@pytest.mark.unit
def test_torrents_to_data_skips_unparseable_in_aggregate():
    rss = RSSItem(
        id=1,
        name="agg",
        url="https://example.test/agg",
        aggregate=True,
        parser="mikan",
        enabled=True,
    )
    torrents = [
        Torrent(name="[ANi] Show A - 01 [1080P]", url="m1", homepage="h1"),
        Torrent(name="bad ★ release ★ name", url="m2", homepage="h2"),
        Torrent(name="[ANi] Show B - 01 [1080P]", url="m3", homepage="h3"),
    ]

    analyser = RSSAnalyser()

    def fake_raw_parser(raw: str):
        if "★" in raw:
            raise BangumiParsingError(
                msg_en="Failed to extract title from torrent name. "
                       "Please provide title manually.",
                msg_zh="无法从种子名称中提取标题。",
                raw_title=raw,
                partial_data={"group": None, "season": 1,
                              "resolution": "1080P", "subtitle": None},
            )
        return Bangumi(
            official_title=raw.split(" - ")[0].strip("[]"),
            title_raw=raw.split(" - ")[0],
            season=1,
            group_name="ANi",
            filter="",
        )

    with patch.object(RSSAnalyser, "raw_parser", staticmethod(fake_raw_parser)):
        with patch.object(RSSAnalyser, "official_title_parser", lambda *a, **k: None):
            result = analyser.torrents_to_data(torrents, rss, full_parse=True)

    titles = [b.official_title for b in result]
    assert len(result) == 2, f"expected 2 surviving bangumi, got {titles}"
    assert "ANi] Show A" in titles
    assert "ANi] Show B" in titles


@pytest.mark.unit
def test_torrents_to_data_surfaces_star_delimited_mikan_item_for_review():
    rss = RSSItem(
        id=1,
        name="agg",
        url="https://mikanani.me/RSS/MyBangumi?token=test",
        aggregate=True,
        parser="mikan",
        enabled=True,
    )
    torrent = Torrent(
        name=(
            "六四位元字幕组★哪里有温柔对待阿宅的辣妹！？ "
            "Otaku ni Yasashii Gal wa Inai★02★1920x1080★AVC AAC MP4★繁体中文"
        ),
        url="https://mikanani.me/Download/20260416/0738c550bda7fa8709f837b904ee3ade6e1bf3b4.torrent",
        homepage="https://mikanani.me/Home/Episode/0738c550bda7fa8709f837b904ee3ade6e1bf3b4",
        hash="0738c550bda7fa8709f837b904ee3ade6e1bf3b4",
    )

    analyser = RSSAnalyser()

    with patch.object(
        RSSAnalyser,
        "mikan_parser_with_rss",
        return_value=MikanParserResult(
            poster_link="https://example.test/poster.jpg",
            official_title="没有辣妹会对阿宅温柔!?",
            season_rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=3901&subgroupid=1243",
        ),
    ):
        result = analyser.torrents_to_data([torrent], rss, full_parse=True)

    assert len(result) == 1
    assert result[0].official_title == "没有辣妹会对阿宅温柔!?"
    assert result[0].title_raw == torrent.name
    assert result[0].group_name == "六四位元字幕组"
    assert result[0].rss_link == "https://mikanani.me/RSS/Bangumi?bangumiId=3901&subgroupid=1243"
    assert result[0].pending_review is True
