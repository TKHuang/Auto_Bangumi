from module.models import Bangumi, RSSItem, Torrent
from module.network import RequestContent
from module.rss import RSSAnalyser

from .provider import search_url

SEARCH_KEY = [
    "group_name",
    "official_title",
]


class SearchTorrent(RequestContent, RSSAnalyser):
    def search_torrents(self, rss_item: RSSItem) -> list[Torrent]:
        return self.get_torrents(rss_item.url)
        # torrents = self.get_torrents(rss_item.url)
        # return torrents

    @staticmethod
    def special_url(data: Bangumi, site: str) -> RSSItem:
        keywords = [getattr(data, key) for key in SEARCH_KEY if getattr(data, key)]
        url = search_url(site, keywords)
        return url

    def search_season(self, data: Bangumi, site: str = "mikan") -> list[Torrent]:
        rss_item = self.special_url(data, site)
        torrents = self.search_torrents(rss_item)
        _title_raw = data.title_raw
        return [torrent for torrent in torrents if _title_raw and _title_raw in torrent.name]
