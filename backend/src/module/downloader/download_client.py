import logging

from module.conf import settings
from module.models import Bangumi, Torrent
from module.network import RequestContent

from .path import TorrentPath

logger = logging.getLogger(__name__)


class DownloadClient(TorrentPath):
    def __init__(self):
        super().__init__()
        self.client = self.__getClient()
        self.authed = False

    @staticmethod
    def __getClient():
        # TODO 多下载器支持
        type = settings.downloader.type
        host = settings.downloader.host
        username = settings.downloader.username
        password = settings.downloader.password
        ssl = settings.downloader.ssl
        if type == "qbittorrent":
            from .client.qb_downloader import QbDownloader

            return QbDownloader(host, username, password, ssl)
        elif type == "pikpak":
            from .client.pikpak_downloader import PikPakDownloader

            return PikPakDownloader(username, password)
        else:
            logger.error(f"[Downloader] Unsupported downloader type: {type}")
            raise Exception(f"Unsupported downloader type: {type}")

    def __enter__(self):
        if not self.authed:
            self.auth()
        else:
            logger.error("[Downloader] Already authed.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.authed:
            self.client.logout()
            self.authed = False

    def auth(self):
        self.authed = self.client.auth()
        if self.authed:
            logger.debug("[Downloader] Authed.")
        else:
            logger.error("[Downloader] Auth failed.")

    def check_host(self):
        return self.client.check_host()

    def init_downloader(self):
        prefs = {
            "rss_auto_downloading_enabled": True,
            "rss_max_articles_per_feed": 500,
            "rss_processing_enabled": True,
            "rss_refresh_interval": 30,
        }
        self.client.prefs_init(prefs=prefs)
        try:
            self.client.add_category("BangumiCollection")
        except Exception:
            logger.debug("[Downloader] Cannot add new category, maybe already exists.")
        if settings.downloader.path == "":
            prefs = self.client.get_app_prefs()
            settings.downloader.path = self._join_path(prefs["save_path"], "Bangumi")

    def set_rule(self, data: Bangumi):
        data.rule_name = self._rule_name(data)
        data.save_path = self._gen_save_path(data)
        rule = {
            "enable": True,
            "mustContain": data.title_raw,
            "mustNotContain": "|".join(data.filter),
            "useRegex": True,
            "episodeFilter": "",
            "smartFilter": False,
            "previouslyMatchedEpisodes": [],
            "affectedFeeds": data.rss_link,
            "ignoreDays": 0,
            "lastMatch": "",
            "addPaused": False,
            "assignedCategory": "Bangumi",
            "savePath": data.save_path,
        }
        self.client.rss_set_rule(rule_name=data.rule_name, rule_def=rule)
        data.added = True
        logger.info(
            f"[Downloader] Add {data.official_title} Season {data.season} to auto download rules."
        )

    def set_rules(self, bangumi_info: list[Bangumi]):
        logger.debug("[Downloader] Start adding rules.")
        for info in bangumi_info:
            self.set_rule(info)
        logger.debug("[Downloader] Finished.")

    def get_torrent_info(self, category="Bangumi", status_filter="completed", tag=None):
        return self.client.torrents_info(
            status_filter=status_filter, category=category, tag=tag
        )

    def get_existing_hashes(self) -> set:
        """Get all existing torrent hashes from qBittorrent."""
        return self.client.get_existing_hashes()

    def rename_torrent_file(self, _hash, old_path, new_path) -> bool:
        logger.info(f"{old_path} >> {new_path}")
        return self.client.torrents_rename_file(
            torrent_hash=_hash, old_path=old_path, new_path=new_path
        )

    def delete_torrent(self, hashes):
        self.client.torrents_delete(hashes)
        logger.info("[Downloader] Remove torrents.")

    @staticmethod
    def _is_valid_torrent(content: bytes | None) -> bool:
        """Check if the content is a valid torrent file.

        A valid torrent file starts with 'd' (0x64) which is the bencode
        dictionary marker, and should have a minimum size.

        Args:
            content: The torrent file content as bytes.

        Returns:
            True if the content appears to be a valid torrent file.
        """
        if not content or len(content) < 50:
            return False
        # Torrent files start with 'd' (bencode dictionary)
        return content[0:1] == b"d"

    def add_torrent(self, torrent: Torrent | list, bangumi: Bangumi) -> bool:
        if not bangumi.save_path:
            bangumi.save_path = self._gen_save_path(bangumi)

        # Check if the downloader supports torrent file uploads
        supports_files = getattr(self.client, "supports_torrent_files", True)

        with RequestContent() as req:
            if isinstance(torrent, list):
                if len(torrent) == 0:
                    logger.debug(f"[Downloader] No torrent found: {bangumi.official_title}")
                    return False

                # For URL-only downloaders (e.g., PikPak), always pass URLs
                if not supports_files or "magnet" in torrent[0].url:
                    torrent_url = [t.url for t in torrent]
                    torrent_file = None
                else:
                    # Download torrent files and filter out invalid ones
                    torrent_file = []
                    for t in torrent:
                        content = req.get_content(t.url)
                        if self._is_valid_torrent(content):
                            torrent_file.append(content)
                        else:
                            logger.warning(
                                f"[Downloader] Skipping invalid torrent: {t.name} "
                                f"(size={len(content) if content else 0})"
                            )
                    if not torrent_file:
                        logger.warning(
                            f"[Downloader] No valid torrents for: {bangumi.official_title}"
                        )
                        return False
                    torrent_url = None
            else:
                # For URL-only downloaders (e.g., PikPak), always pass URLs
                if not supports_files or "magnet" in torrent.url:
                    torrent_url = torrent.url
                    torrent_file = None
                else:
                    torrent_file = req.get_content(torrent.url)
                    if not self._is_valid_torrent(torrent_file):
                        logger.warning(
                            f"[Downloader] Invalid torrent file: {torrent.name} "
                            f"(size={len(torrent_file) if torrent_file else 0})"
                        )
                        return False
                    torrent_url = None

        if self.client.add_torrents(
            torrent_urls=torrent_url,
            torrent_files=torrent_file,
            save_path=bangumi.save_path,
            category="Bangumi",
        ):
            logger.debug(f"[Downloader] Add torrent: {bangumi.official_title}")
            return True
        else:
            logger.debug(f"[Downloader] Torrent added before: {bangumi.official_title}")
            return False

    def move_torrent(self, hashes, location):
        self.client.move_torrent(hashes=hashes, new_location=location)

    # RSS Parts
    def add_rss_feed(self, rss_link, item_path="Mikan_RSS"):
        self.client.rss_add_feed(url=rss_link, item_path=item_path)

    def remove_rss_feed(self, item_path):
        self.client.rss_remove_item(item_path=item_path)

    def get_rss_feed(self):
        return self.client.rss_get_feeds()

    def get_download_rules(self):
        return self.client.get_download_rule()

    def get_torrent_path(self, hashes):
        return self.client.get_torrent_path(hashes)

    def set_category(self, hashes, category):
        self.client.set_category(hashes, category)

    def remove_rule(self, rule_name):
        self.client.remove_rule(rule_name)
        logger.info(f"[Downloader] Delete rule: {rule_name}")
