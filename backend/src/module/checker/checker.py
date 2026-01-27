import logging
from pathlib import Path

from module.conf import VERSION, settings
from module.downloader import DownloadClient
from module.models import Config
from module.update import version_check

logger = logging.getLogger(__name__)


class Checker:
    def __init__(self):
        pass

    @staticmethod
    def check_renamer() -> bool:
        if settings.bangumi_manage.enable:
            return True
        else:
            return False

    @staticmethod
    def check_analyser() -> bool:
        if settings.rss_parser.enable:
            return True
        else:
            return False

    @staticmethod
    def check_first_run() -> bool:
        if settings.dict() == Config().dict():
            return True
        else:
            return False

    @staticmethod
    def check_version() -> bool:
        return version_check()

    @staticmethod
    def check_database() -> bool:
        db_path = Path("data/data.db")
        if not db_path.exists():
            return False
        else:
            return True

    @staticmethod
    def check_downloader() -> bool:
        """Check if the configured downloader is reachable and can authenticate.

        Delegates to the appropriate downloader client implementation
        (qBittorrent, PikPak, etc.) for connectivity and auth checks.

        Returns:
            True if downloader is reachable and authentication succeeds.
        """
        try:
            client = DownloadClient()
            # First check if the downloader service is reachable
            if not client.check_host():
                logger.error(
                    f"[Checker] {settings.downloader.type} downloader not reachable."
                )
                return False

            # Then verify authentication works
            with client:
                if client.authed:
                    logger.debug(
                        f"[Checker] {settings.downloader.type} downloader connected."
                    )
                    return True
                else:
                    logger.error(
                        f"[Checker] {settings.downloader.type} authentication failed."
                    )
                    return False
        except Exception as e:
            logger.error(f"[Checker] Downloader check failed: {e}")
            return False

    @staticmethod
    def check_img_cache() -> bool:
        img_path = Path("data/posters")
        if img_path.exists():
            return True
        else:
            img_path.mkdir()
            return False
