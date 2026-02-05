"""Downloader services - download client abstraction."""

from .factory import create_downloader
from .interface import (
    DownloaderProtocol,
    TorrentFile,
    TorrentInfo,
)

__all__ = [
    "DownloaderProtocol",
    "TorrentInfo",
    "TorrentFile",
    "create_downloader",
]
