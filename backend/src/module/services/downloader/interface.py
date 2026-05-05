"""Abstract downloader interface and data models.

Defines the contract for downloader implementations (qBittorrent, PikPak, etc.)
using Protocol for structural subtyping.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class RenameOutcome(str, Enum):
    """Outcome of a single rename request against the downloader.

    The renamer used to receive a bare ``bool`` here, which forced the PikPak
    adapter to lie ("name conflict" → ``True``) so the upper layer wouldn't
    delete the torrent. The DB then marked those files as renamed even though
    they were still sitting under their raw filenames in PikPak — silent data
    loss for any media-library scraper.

    A three-state outcome lets:
      * ``OK``       — renamer marks ``renamed_at`` and bumps the file count.
      * ``CONFLICT`` — renamer keeps the torrent unrenamed AND records the
                       collision so a UI can show it. Will not auto-retry.
      * ``ERROR``    — transient/unknown failure; renamer retries next tick.
    """

    OK = "ok"
    CONFLICT = "conflict"
    ERROR = "error"


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
        cloud_paths: dict[str, str] | None = None,
    ) -> list[TorrentInfo]:
        """Get information about torrents.

        Args:
            status_filter: Filter by torrent state (e.g., "completed", "downloading").
            category: Filter by category name.
            tag: Filter by tag.
            cloud_paths: Pre-built hash→path map. PikPak uses this to avoid
                        DB queries; qBittorrent ignores it.

        Returns:
            List of TorrentInfo objects matching the filters.
        """
        ...

    async def torrents_rename_file(
        self, hash: str, old_path: str, new_path: str
    ) -> "RenameOutcome":
        """Rename a file within a torrent.

        Args:
            hash: Torrent hash.
            old_path: Current file path within the torrent.
            new_path: New file path.

        Returns:
            ``RenameOutcome.OK`` on success (or no-op when already named),
            ``RenameOutcome.CONFLICT`` when ``new_path`` is already taken by
            another file in the destination folder, or ``RenameOutcome.ERROR``
            for any other failure.
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

    async def get_existing_hashes(self, category: str | None = None) -> set[str]:
        """Get hashes of all torrents currently tracked by the downloader.

        Args:
            category: Optional category/folder filter.

        Returns:
            Set of lowercase torrent hashes.
        """
        ...

    async def get_hash_status_map(self, category: str | None = None) -> dict[str, str]:
        """Get a mapping of torrent hashes to their current state.

        Unlike get_existing_hashes() which only returns hash presence,
        this method includes the downloader-reported state for each torrent
        (e.g. 'completed', 'error', 'downloading').

        Args:
            category: Optional category/folder filter.

        Returns:
            Dict mapping lowercase torrent hash to state string.
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
