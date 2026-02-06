"""Factory for creating downloader instances based on configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .interface import DownloaderProtocol

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from module.conf import Config


def create_downloader(
    config: Config, session: AsyncSession | None = None
) -> DownloaderProtocol:
    """Create a downloader instance based on configuration.

    Args:
        config: Application configuration containing downloader settings.
        session: Optional async database session (required for PikPak).

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
            session=session,
        )
    else:
        raise ValueError(
            f"Unsupported downloader type: {downloader_type}. "
            f"Supported types: qbittorrent, pikpak"
        )
