"""Abstract downloader interface and data models.

Defines the contract for downloader implementations (qBittorrent, PikPak, etc.)
using Protocol for structural subtyping.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class TorrentFile:
    """Represents a single file within a torrent."""

    name: str
    size: int
    path: str


@dataclass
class TorrentInfo:
    """Represents torrent metadata and status."""

    hash: str
    name: str
    state: str
    progress: float
    save_path: str
    size: int
    files: list[TorrentFile]


class DownloaderProtocol(Protocol):
    """Abstract protocol for downloader implementations.

    All methods are async and must be implemented by concrete downloaders
    (qBittorrent, PikPak, etc.).
    """

    async def auth(self) -> bool:
        """Authenticate with the downloader service.

        Returns:
            True if authentication successful, False otherwise.
        """
        ...

    async def check_host(self) -> bool:
        """Check if the downloader host is reachable and responsive.

        Returns:
            True if host is reachable, False otherwise.
        """
        ...

    async def add_torrents(
        self,
        urls: list[str] | None = None,
        save_path: str | None = None,
        torrent_files: list[bytes] | None = None,
    ) -> bool:
        """Add torrents to the downloader.

        Args:
            urls: List of torrent URLs or magnet links.
            save_path: Directory to save downloaded files.
            torrent_files: List of torrent file contents (bytes).

        Returns:
            True if torrents were added successfully, False otherwise.
        """
        ...

    async def torrents_info(
        self,
        status_filter: str | None = None,
        category: str | None = None,
        tag: str | None = None,
    ) -> list[TorrentInfo]:
        """Get information about torrents.

        Args:
            status_filter: Filter by torrent state (e.g., "completed", "downloading").
            category: Filter by category name.
            tag: Filter by tag.

        Returns:
            List of TorrentInfo objects matching the filters.
        """
        ...

    async def torrents_rename_file(
        self, hash: str, old_path: str, new_path: str
    ) -> bool:
        """Rename a file within a torrent.

        Args:
            hash: Torrent hash.
            old_path: Current file path within the torrent.
            new_path: New file path.

        Returns:
            True if rename was successful, False otherwise.
        """
        ...

    async def torrents_delete(
        self, hashes: list[str], delete_files: bool = True
    ) -> bool:
        """Delete torrents from the downloader.

        Args:
            hashes: List of torrent hashes to delete.
            delete_files: If True, also delete downloaded files.

        Returns:
            True if deletion was successful, False otherwise.
        """
        ...

    async def move_torrent(
        self, hashes: list[str], new_location: str
    ) -> bool:
        """Move torrent to a new location.

        Args:
            hashes: List of torrent hashes to move.
            new_location: New save path for the torrents.

        Returns:
            True if move was successful, False otherwise.
        """
        ...

    async def get_torrent_path(self, hash: str) -> str | None:
        """Get the save path of a torrent.

        Args:
            hash: Torrent hash.

        Returns:
            Save path of the torrent, or None if not found.
        """
        ...
