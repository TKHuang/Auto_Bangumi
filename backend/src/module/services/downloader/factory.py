"""Factory for creating downloader instances based on configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .interface import DownloaderProtocol

if TYPE_CHECKING:
    from module.conf import Config


def create_downloader(config: Config) -> DownloaderProtocol:
    """Create a downloader instance based on configuration.

    Args:
        config: Application configuration containing downloader settings.

    Returns:
        A downloader instance implementing DownloaderProtocol.

    Raises:
        ValueError: If downloader type is not supported.
    """
    downloader_type = config.downloader.type.lower()

    if downloader_type == "qbittorrent":
        from module.services.downloader.qbittorrent import QBittorrentDownloader

        return QBittorrentDownloader(
            host=config.downloader.host,
            username=config.downloader.username,
            password=config.downloader.password,
            ssl=config.downloader.ssl,
        )
    elif downloader_type == "pikpak":
        from module.services.downloader.pikpak import PikPakDownloader

        return PikPakDownloader(
            username=config.downloader.username,
            password=config.downloader.password,
        )
    else:
        raise ValueError(
            f"Unsupported downloader type: {downloader_type}. "
            f"Supported types: qbittorrent, pikpak"
        )
