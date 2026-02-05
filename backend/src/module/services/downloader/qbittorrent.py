"""qBittorrent downloader adapter implementing DownloaderProtocol.

Wraps qbittorrent-api Client with async methods using asyncio.to_thread().
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, cast

from qbittorrentapi import Client, LoginFailed
from qbittorrentapi.exceptions import (
    APIConnectionError,
    Conflict409Error,
    Forbidden403Error,
)

from .interface import TorrentFile, TorrentInfo

if TYPE_CHECKING:
    from qbittorrentapi.torrents import TorrentDictionary

logger = logging.getLogger(__name__)


class QBittorrentDownloader:
    """qBittorrent downloader implementation using qbittorrent-api library."""

    supports_torrent_files: bool = True

    def __init__(self, host: str, username: str, password: str, ssl: bool):
        self._client: Client = Client(
            host=host,
            username=username,
            password=password,
            VERIFY_WEBUI_CERTIFICATE=ssl,
            DISABLE_LOGGING_DEBUG_OUTPUT=True,
            REQUESTS_ARGS={"timeout": (3.1, 10)},
        )
        self.host: str = host
        self.username: str = username

    async def auth(self, retry: int = 3) -> bool:
        """Authenticate with qBittorrent server with retry logic."""
        times = 0
        while times < retry:
            try:
                await asyncio.to_thread(self._client.auth_log_in)
                return True
            except LoginFailed:
                logger.error(
                    f"Can't login qBittorrent Server {self.host} by {self.username}, retry in 5 seconds."
                )
                await asyncio.sleep(5)
                times += 1
            except Forbidden403Error:
                logger.error("Login refused by qBittorrent Server")
                logger.info("Please release the IP in qBittorrent Server")
                break
            except APIConnectionError:
                logger.error("Cannot connect to qBittorrent Server")
                logger.info("Please check the IP and port in WebUI settings")
                await asyncio.sleep(10)
                times += 1
            except Exception as e:
                logger.error(f"Unknown error: {e}")
                break
        return False

    async def logout(self) -> None:
        """Logout from qBittorrent server."""
        await asyncio.to_thread(self._client.auth_log_out)

    async def check_host(self) -> bool:
        """Check if qBittorrent host is reachable."""
        try:
            await asyncio.to_thread(self._client.app_version)
            return True
        except APIConnectionError:
            return False

    async def add_torrents(
        self,
        urls: list[str] | None = None,
        save_path: str | None = None,
        torrent_files: list[bytes] | None = None,
    ) -> bool:
        """Add torrents to qBittorrent."""
        resp = await asyncio.to_thread(
            self._client.torrents_add,
            is_paused=False,
            urls=urls,
            torrent_files=torrent_files,
            save_path=save_path,
            category="Bangumi",
            use_auto_torrent_management=False,
            content_layout="NoSubFolder",
        )
        return resp == "Ok."

    async def torrents_info(
        self,
        status_filter: str | None = None,
        category: str | None = None,
        tag: str | None = None,
    ) -> list[TorrentInfo]:
        """Get torrent information from qBittorrent."""
        torrents: Any = await asyncio.to_thread(
            self._client.torrents_info,
            status_filter=status_filter,  # type: ignore[arg-type]
            category=category,
            tag=tag,
        )

        result: list[TorrentInfo] = []
        for t in torrents:
            try:
                t_dict = dict(t)
                if not t_dict:
                    raise ValueError("Empty dict")
            except (TypeError, ValueError):
                t_dict = {
                    "hash": getattr(t, "hash", ""),
                    "name": getattr(t, "name", ""),
                    "state": getattr(t, "state", ""),
                    "progress": getattr(t, "progress", 0.0),
                    "save_path": getattr(t, "save_path", ""),
                    "size": getattr(t, "size", 0),
                    "files": getattr(t, "files", []),
                }

            files_data = t_dict.get("files", [])
            files: list[TorrentFile] = []
            if isinstance(files_data, list):
                for f in files_data:
                    try:
                        f_dict = dict(f)
                        if not f_dict:
                            raise ValueError("Empty dict")
                    except (TypeError, ValueError):
                        f_dict = {
                            "name": getattr(f, "name", ""),
                            "size": getattr(f, "size", 0),
                        }
                    files.append(
                        TorrentFile(
                            name=str(f_dict.get("name", "")),
                            size=int(f_dict.get("size", 0)),
                            path=str(f_dict.get("name", "")),
                        )
                    )

            result.append(
                TorrentInfo(
                    hash=str(t_dict.get("hash", "")),
                    name=str(t_dict.get("name", "")),
                    state=str(t_dict.get("state", "")),
                    progress=float(t_dict.get("progress", 0.0)),
                    save_path=str(t_dict.get("save_path", "")),
                    size=int(t_dict.get("size", 0)),
                    files=files,
                )
            )
        return result

    async def torrents_rename_file(
        self, hash: str, old_path: str, new_path: str
    ) -> bool:
        """Rename a file within a torrent."""
        try:
            await asyncio.to_thread(
                self._client.torrents_rename_file,
                torrent_hash=hash,
                old_path=old_path,
                new_path=new_path,
            )
            return True
        except Conflict409Error:
            logger.debug(f"Conflict409Error: {old_path} >> {new_path}")
            return False

    async def torrents_delete(
        self, hashes: list[str], delete_files: bool = True
    ) -> bool:
        """Delete torrents from qBittorrent."""
        await asyncio.to_thread(
            self._client.torrents_delete,
            delete_files=delete_files,
            torrent_hashes=hashes,
        )
        return True

    async def move_torrent(self, hashes: list[str], new_location: str) -> bool:
        """Move torrent to a new location."""
        await asyncio.to_thread(
            self._client.torrents_set_location,
            new_location,
            hashes,
        )
        return True

    async def get_torrent_path(self, hash: str) -> str | None:
        """Get the save path of a torrent."""
        torrents: Any = await asyncio.to_thread(
            self._client.torrents_info,
            hashes=hash,
        )
        if torrents:
            t = torrents[0]
            try:
                t_dict = dict(t)
                if not t_dict:
                    raise ValueError("Empty dict")
                save_path = t_dict.get("save_path")
            except (TypeError, ValueError):
                save_path = getattr(t, "save_path", None)
            return str(save_path) if save_path else None
        return None

    async def rss_add_feed(self, url: str, item_path: str) -> None:
        """Add RSS feed to qBittorrent."""
        try:
            await asyncio.to_thread(self._client.rss_add_feed, url, item_path)
        except Conflict409Error:
            logger.warning(f"[Downloader] RSS feed {url} already exists")

    async def rss_remove_item(self, item_path: str) -> None:
        """Remove RSS item from qBittorrent."""
        try:
            await asyncio.to_thread(self._client.rss_remove_item, item_path)
        except Conflict409Error:
            logger.warning(f"[Downloader] RSS item {item_path} does not exist")

    async def rss_get_feeds(self) -> dict[str, Any]:
        """Get all RSS feeds from qBittorrent."""
        return await asyncio.to_thread(self._client.rss_items)

    async def rss_set_rule(self, rule_name: str, rule_def: dict[str, Any]) -> None:
        """Set RSS download rule in qBittorrent."""
        await asyncio.to_thread(self._client.rss_set_rule, rule_name, rule_def)

    async def get_download_rule(self) -> dict[str, Any]:
        """Get all RSS download rules from qBittorrent."""
        return await asyncio.to_thread(self._client.rss_rules)

    async def remove_rule(self, rule_name: str) -> None:
        """Remove RSS download rule from qBittorrent."""
        await asyncio.to_thread(self._client.rss_remove_rule, rule_name)

    async def add_category(self, category: str) -> None:
        """Add category to qBittorrent."""
        await asyncio.to_thread(self._client.torrents_createCategory, name=category)

    async def set_category(self, hash: str, category: str) -> None:
        """Set category for a torrent."""
        try:
            await asyncio.to_thread(
                self._client.torrents_set_category,
                category,
                hashes=hash,
            )
        except Conflict409Error:
            logger.warning(f"[Downloader] Category {category} does not exist")
            await self.add_category(category)
            await asyncio.to_thread(
                self._client.torrents_set_category,
                category,
                hashes=hash,
            )

    async def add_tag(self, hash: str, tag: str) -> None:
        """Add tag to a torrent."""
        await asyncio.to_thread(
            self._client.torrents_add_tags,
            tags=tag,
            hashes=hash,
        )

    async def get_existing_hashes(self, category: str = "Bangumi") -> set[str]:
        """Get all existing torrent hashes for the given category."""
        try:
            torrents: Any = await asyncio.to_thread(
                self._client.torrents_info,
                category=category,
            )
            hashes: set[str] = set()
            for t in torrents:
                try:
                    t_dict = dict(t)
                    if not t_dict:
                        raise ValueError("Empty dict")
                    hash_val = t_dict.get("hash")
                except (TypeError, ValueError):
                    hash_val = getattr(t, "hash", None)
                if hash_val:
                    hashes.add(str(hash_val))
            return hashes
        except Exception as e:
            logger.warning(f"[Downloader] Failed to get existing hashes: {e}")
            return set()

    async def check_connection(self) -> str:
        """Check connection and return qBittorrent version."""
        return await asyncio.to_thread(self._client.app_version)
