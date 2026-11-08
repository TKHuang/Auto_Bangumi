"""Tests for the search service.

The network boundary (RequestContent) is replaced by a fake that serves real,
trimmed Mikan HTML fixtures and records every request.
"""

import asyncio
import json
import threading
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

import pytest

from module.mikan.parser import build_season_rss_url
from module.models import Torrent
from module.rss import RSSAnalyser
from module.searcher.provider import search_url
from module.services.search import get_providers, search

_FIX = Path(__file__).parent.parent / "fixtures" / "mikan"
_BASE = "https://mikanani.me"


def _load(name: str) -> str:
    return (_FIX / name).read_text(encoding="utf-8")


def _search(keyword: str) -> str:
    return f"{_BASE}/Home/Search?{urlencode({'searchstr': keyword})}"


def _search_page(ids: list[int]) -> str:
    items = "".join(
        f'<li><a href="/Home/Bangumi/{i}" target="_blank">'
        f'<span data-src="/images/Bangumi/2026/{i}.jpg?width=400" class="b-lazy"></span>'
        f'<div class="an-text" title="Show {i}" style="">Show {i}</div></a></li>'
        for i in ids
    )
    return f'<ul class="list-inline an-ul">{items}</ul>'


class FakeRequestContent:
    def __init__(self, pages: dict[str, str], torrents: list[Torrent] | None = None):
        self.pages = pages
        self.torrents = torrents or []
        self.html_urls: list[str] = []
        self.content_urls: list[str] = []
        self.torrent_urls: list[str] = []
        self.gates: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def __call__(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get_html(self, url: str) -> str:
        with self._lock:
            self.html_urls.append(url)
        gate = self.gates.get(url)
        if gate is not None:
            gate.wait(timeout=5)
        return self.pages.get(url, "<html></html>")

    def get_content(self, url: str) -> bytes:
        with self._lock:
            self.content_urls.append(url)
        return url.encode()

    def get_torrents(self, url: str, *args, **kwargs) -> list[Torrent]:
        self.torrent_urls.append(url)
        return self.torrents


@pytest.fixture
def poster_dir(tmp_path, monkeypatch):
    (tmp_path / "data" / "posters").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


async def _collect(gen) -> list[dict]:
    return [json.loads(item) async for item in gen]


class TestGetProviders:
    def test_returns_provider_list(self):
        providers = get_providers()
        assert "mikan" in providers

    def test_returns_all_configured_providers(self):
        with patch("module.services.search.SEARCH_CONFIG", {"mikan": "u1", "nyaa": "u2"}):
            assert get_providers() == ["mikan", "nyaa"]


class TestSearchMikan:
    @pytest.mark.asyncio
    async def test_one_hit_per_subgroup_with_real_rss_link(self, poster_dir):
        fake = FakeRequestContent(
            {
                _search("僵尸"): _load("search_page.html"),
                f"{_BASE}/Home/Bangumi/4076": _load("bangumi_page_4076.html"),
            }
        )
        with patch("module.services.search.RequestContent", fake):
            hits = await _collect(search(["僵尸"], provider="mikan"))

        assert sorted((h["group_name"], h["rss_link"]) for h in hits) == sorted(
            [
                ("绿茶字幕组", build_season_rss_url(4076, 1236)),
                ("Kirara Fantasia", build_season_rss_url(4076, 615)),
                ("生肉/不明字幕", build_season_rss_url(4076, 202)),
                ("天月动漫&发布组", build_season_rss_url(4076, 534)),
            ]
        )
        assert {h["official_title"] for h in hits} == {"僵尸搜寻中"}
        assert {h["season"] for h in hits} == {1}
        poster = hits[0]["poster_link"]
        assert poster.startswith("posters/")
        assert (poster_dir / "data" / poster).exists()
        assert {h["poster_link"] for h in hits} == {poster}

        assert len(fake.html_urls) == 1 + 4
        assert fake.content_urls == [f"{_BASE}/images/Bangumi/202610/25a3140f.jpg"]
        assert fake.torrent_urls == []

    @pytest.mark.asyncio
    async def test_season_parsed_from_mikan_title(self, poster_dir):
        page = _search_page([3821]).replace("Show 3821", "葬送的芙莉莲 第二季")
        fake = FakeRequestContent(
            {
                _search("芙莉莲"): page,
                f"{_BASE}/Home/Bangumi/3821": _load("bangumi_page_4076.html"),
            }
        )
        with patch("module.services.search.RequestContent", fake):
            hits = await _collect(search(["芙莉莲"], provider="mikan"))

        assert hits
        assert {h["season"] for h in hits} == {2}

    @pytest.mark.asyncio
    async def test_broad_keyword_fetches_at_most_ten_bangumi_pages(self, poster_dir):
        fake = FakeRequestContent(
            {_search("a"): _search_page(list(range(1, 16)))}
        )
        with patch("module.services.search.RequestContent", fake):
            assert await _collect(search(["a"], provider="mikan")) == []

        assert len(fake.html_urls) == 1 + 10

    @pytest.mark.asyncio
    async def test_streams_hits_before_slow_bangumi_page_finishes(self, poster_dir):
        slow = f"{_BASE}/Home/Bangumi/2"
        fake = FakeRequestContent(
            {
                _search("a"): _search_page([2, 1]),
                f"{_BASE}/Home/Bangumi/1": _load("bangumi_page_4076.html"),
                slow: _load("bangumi_page_3141_joint_group.html"),
            }
        )
        gate = threading.Event()
        fake.gates[slow] = gate
        with patch("module.services.search.RequestContent", fake):
            gen = search(["a"], provider="mikan")
            first = json.loads(await asyncio.wait_for(gen.__anext__(), timeout=3))
            assert first["rss_link"].startswith(f"{_BASE}/RSS/Bangumi?bangumiId=1&")
            gate.set()
            rest = await _collect(gen)

        assert len(rest) == 3 + 2

    @pytest.mark.asyncio
    async def test_unreachable_search_page_yields_nothing(self, poster_dir):
        class Down(FakeRequestContent):
            def get_html(self, url):
                raise AttributeError("'NoneType' object has no attribute 'text'")

        with patch("module.services.search.RequestContent", Down({})):
            assert await _collect(search(["a"], provider="mikan")) == []


class TestSearchTorrentProviders:
    @staticmethod
    def _torrent(name: str) -> Torrent:
        return Torrent(name=name, url=f"magnet:?xt={name}", homepage=None)

    @pytest.mark.asyncio
    async def test_dedupes_before_tmdb_lookup(self):
        torrents = [
            self._torrent("[Lilith-Raws] Sousou no Frieren - 01 [Baha][WEB-DL][1080p][AVC AAC][CHT][MP4]"),
            self._torrent("[Lilith-Raws] Sousou no Frieren - 02 [Baha][WEB-DL][1080p][AVC AAC][CHT][MP4]"),
            self._torrent("[Lilith-Raws] Sousou no Frieren - 03 [Baha][WEB-DL][1080p][AVC AAC][CHT][MP4]"),
            self._torrent("[ANi] Sousou no Frieren - 01 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]"),
        ]
        fake = FakeRequestContent({}, torrents=torrents)
        with (
            patch("module.services.search.RequestContent", fake),
            patch.object(
                RSSAnalyser,
                "tmdb_parser",
                return_value=("葬送的芙莉莲", 1, "2023", "posters/f.jpg"),
            ) as tmdb,
        ):
            hits = await _collect(search(["Frieren"], provider="nyaa"))

        assert tmdb.call_count == 2
        assert sorted(h["group_name"] for h in hits) == ["ANi", "Lilith-Raws"]
        for h in hits:
            assert h["official_title"] == "葬送的芙莉莲"
            assert h["rss_link"] == search_url("nyaa", [h["group_name"], "葬送的芙莉莲"]).url
        assert fake.torrent_urls == [search_url("nyaa", ["Frieren"]).url]

    @pytest.mark.asyncio
    async def test_skips_unparseable_torrents(self):
        fake = FakeRequestContent({}, torrents=[self._torrent("not a release name")])
        with (
            patch("module.services.search.RequestContent", fake),
            patch.object(RSSAnalyser, "tmdb_parser") as tmdb,
        ):
            assert await _collect(search(["x"], provider="dmhy")) == []
        tmdb.assert_not_called()


class TestSearchValidation:
    @pytest.mark.asyncio
    async def test_invalid_provider_raises_error(self):
        with pytest.raises(ValueError, match="Provider 'invalid' is not supported"):
            async for _ in search(["test"], provider="invalid"):
                pass
