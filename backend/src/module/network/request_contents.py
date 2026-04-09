import logging
import re
import xml.etree.ElementTree as ET

import defusedxml.ElementTree as DefusedET

from module.conf import settings
from module.models import Torrent

from .request_url import RequestURL
from .site import rss_parser

logger = logging.getLogger(__name__)


class RequestContent(RequestURL):
    def _get_filter(self, _filter: str = None) -> str | None:
        # Handle filter: None uses default, empty string means no filter
        if _filter is None:
            return "|".join(settings.rss_parser.filter)
        elif _filter == "":
            # Empty string means don't filter anything
            return None
        else:
            return _filter.replace(",", "|")

    def get_torrents(
        self,
        _url: str,
        _filter: str = None,
        limit: int = None,
        retry: int = 3,
    ) -> list[Torrent]:
        soup = self.get_xml(_url, retry)
        if soup is not None:
            torrent_titles, torrent_urls, torrent_homepage = rss_parser(soup)
            torrents: list[Torrent] = []
            
            _filter = self._get_filter(_filter)
            
            for _title, torrent_url, homepage in zip(
                torrent_titles, torrent_urls, torrent_homepage
            ):
                # Only apply filter if it's not None
                if _filter is None or re.search(_filter, _title, re.IGNORECASE) is None:
                    # Extract hash from URL or magnet
                    _hash = None
                    if "Download/" in torrent_url:
                        # Mikanani URL: /Download/YYYYMMDD/{HASH}.torrent
                        match = re.search(r"Download/\d+/([A-Fa-f0-9]{40})\.torrent", torrent_url)
                        if match:
                            _hash = match.group(1).lower()
                    elif "magnet:?" in torrent_url:
                        # Magnet link: magnet:?xt=urn:btih:{HASH}
                        match = re.search(r"btih:([A-Fa-f0-9]{40})", torrent_url)
                        if match:
                            _hash = match.group(1).lower()
                    
                    torrents.append(
                        Torrent(name=_title, url=torrent_url, homepage=homepage, hash=_hash)
                    )
                if isinstance(limit, int):
                    if len(torrents) >= limit:
                        break
            return torrents
        else:
            logger.warning(f"[Network] Failed to get torrents: {_url}")
            return []

    def get_torrents_with_filter(
        self,
        _url: str,
        _filter: str = None,
        title_raw: str = None,
        retry: int = 3,
    ) -> list[dict]:
        """Get torrents from RSS with optional filtering.

        Args:
            _url: RSS URL to fetch torrents from
            _filter: Regex pattern to exclude torrents (mark as filtered=True)
            title_raw: If provided, only include torrents that parse to this title_raw
            retry: Number of retries for network requests
        """
        soup = self.get_xml(_url, retry)
        if soup is not None:
            torrent_titles, torrent_urls, torrent_homepage = rss_parser(soup)
            torrents: list[dict] = []
            
            _filter = self._get_filter(_filter)
            
            # Lazy import to avoid circular dependency
            raw_parser = None
            BangumiParsingError = None
            if title_raw:
                from module.domain.value_objects import BangumiParsingError
                from module.domain.parser.title_parser import TitleParser
                raw_parser = TitleParser()

            for _title, torrent_url, homepage in zip(
                torrent_titles, torrent_urls, torrent_homepage
            ):
                # If title_raw is specified, filter to only matching torrents
                if title_raw and raw_parser:
                    try:
                        parsed = raw_parser.raw_parser(_title)
                        if not parsed:
                            continue
                        # Use substring matching instead of strict equality
                        # Different subgroups format titles differently, e.g.:
                        #   "Modaete yo, Adam-kun (BDRip 1080p HEVC FLAC)" vs "Modaete yo, Adam-kun"
                        # If either title contains the other, consider it a match
                        if title_raw not in parsed.title_raw and parsed.title_raw not in title_raw:
                            continue
                    except BangumiParsingError:
                        # Unparseable torrents cannot be filtered by title_raw - skip them
                        # This follows the established pattern in test_rss_parsing_integration.py
                        continue
                
                filtered = False
                if _filter and re.search(_filter, _title, re.IGNORECASE):
                    filtered = True

                _hash = None
                match = re.search(r"Download/\d+/([A-Fa-f0-9]{40})\.torrent", torrent_url)
                if match:
                    _hash = match.group(1).lower()
                else:
                    match = re.search(r"btih:([A-Fa-f0-9]{40})", torrent_url)
                    if match:
                        _hash = match.group(1).lower()

                torrents.append({
                    "name": _title,
                    "url": torrent_url,
                    "homepage": homepage,
                    "filter": filtered,
                    "hash": _hash,
                })
            return torrents
        else:
            logger.warning(f"[Network] Failed to get torrents: {_url}")
            return []

    def get_xml(self, _url, retry: int = 3) -> ET.Element | None:
        """Parse XML from URL with XXE protection.

        Uses defusedxml to prevent XML External Entity (XXE) attacks
        from malicious RSS feeds.

        Returns None if URL is not valid XML (e.g., HTML page).
        """
        req = self.get_url(_url, retry)
        if req:
            try:
                return DefusedET.fromstring(req.text)
            except ET.ParseError:
                logger.warning(f"[Request] URL is not valid XML/RSS: {_url}")
                return None
        return None

    # API JSON
    def get_json(self, _url) -> dict:
        req = self.get_url(_url)
        if req:
            return req.json()

    def post_json(self, _url, data: dict) -> dict:
        return self.post_url(_url, data).json()

    def post_data(self, _url, data: dict) -> dict:
        return self.post_url(_url, data)

    def post_files(self, _url, data: dict, files: dict) -> dict:
        return self.post_form(_url, data, files)

    def get_html(self, _url):
        return self.get_url(_url).text

    def get_content(self, _url):
        req = self.get_url(_url)
        if req:
            return req.content

    def check_connection(self, _url):
        return self.check_url(_url)

    def get_rss_title(self, _url):
        soup = self.get_xml(_url)
        if soup is not None:
            title_elem = soup.find("./channel/title")
            if title_elem is not None:
                title = title_elem.text
                # Strip common RSS provider prefixes
                if title and title.startswith("Mikan Project - "):
                    title = title[len("Mikan Project - "):]
                # Strip search result prefix from Mikan search RSS feeds
                if title and title.startswith("搜索结果: "):
                    title = title[len("搜索结果: "):]
                return title
        return None
