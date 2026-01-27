import logging
import re

from module.conf import settings
from module.downloader import DownloadClient
from module.models import EpisodeFile, Notification, SubtitleFile
from module.parser import TitleParser

logger = logging.getLogger(__name__)


class Renamer(DownloadClient):
    def __init__(self):
        super().__init__()
        self._parser = TitleParser()
        self.check_pool = {}

    @staticmethod
    def print_result(torrent_count, rename_count):
        if rename_count != 0:
            logger.info(
                f"Finished checking {torrent_count} files' name, renamed {rename_count} files."
            )
        logger.debug(f"Checked {torrent_count} files")

    @staticmethod
    def gen_path(
            file_info: EpisodeFile | SubtitleFile, bangumi_name: str, method: str
    ) -> str:
        # Handle movies (no episode number expected)
        if file_info.is_movie:
            if method == "none" or method == "subtitle_none":
                return file_info.media_path
            elif method == "pn":
                return f"{file_info.title}{file_info.suffix}"
            elif method == "advance":
                return f"{bangumi_name}{file_info.suffix}"
            elif method == "normal":
                logger.warning("[Renamer] Normal rename method is deprecated.")
                return file_info.media_path
            elif method == "subtitle_pn":
                return f"{file_info.title}.{file_info.language}{file_info.suffix}"
            elif method == "subtitle_advance":
                return f"{bangumi_name}.{file_info.language}{file_info.suffix}"
            else:
                logger.error(f"[Renamer] Unknown rename method: {method}")
                return file_info.media_path

        # Handle None episode for non-movie content - log warning and return original path
        if file_info.episode is None:
            logger.warning(
                f"[Renamer] Episode is None for file: {file_info.media_path}, "
                f"title={file_info.title}, season={file_info.season}"
            )
            return file_info.media_path

        season = f"0{file_info.season}" if file_info.season < 10 else file_info.season
        # Convert episode to int if it's a whole number to avoid ".0" suffix in filename
        ep_value = file_info.episode
        if ep_value == int(ep_value):
            ep_value = int(ep_value)
        episode = f"0{ep_value}" if ep_value < 10 else ep_value

        # Add version suffix if present (e.g., "v2" for version 2)
        version_suffix = f"v{file_info.version}" if file_info.version else ""

        # Handle special episode types (OAD, OVA, SP)
        # Format: "{title} {type} {episode}.{suffix}" e.g., "Golden Kamuy OAD 01.mp4"
        if file_info.episode_type is not None:
            ep_type = file_info.episode_type.value  # OAD, OVA, or SP
            if method == "none" or method == "subtitle_none":
                return file_info.media_path
            elif method == "pn":
                return f"{file_info.title} {ep_type} {episode}{version_suffix}{file_info.suffix}"
            elif method == "advance":
                return f"{bangumi_name} {ep_type} {episode}{version_suffix}{file_info.suffix}"
            elif method == "normal":
                logger.warning("[Renamer] Normal rename method is deprecated.")
                return file_info.media_path
            elif method == "subtitle_pn":
                return f"{file_info.title} {ep_type} {episode}{version_suffix}.{file_info.language}{file_info.suffix}"
            elif method == "subtitle_advance":
                return f"{bangumi_name} {ep_type} {episode}{version_suffix}.{file_info.language}{file_info.suffix}"
            else:
                logger.error(f"[Renamer] Unknown rename method: {method}")
                return file_info.media_path

        # Handle regular episodes with S##E## format
        if method == "none" or method == "subtitle_none":
            return file_info.media_path
        elif method == "pn":
            return f"{file_info.title} S{season}E{episode}{version_suffix}{file_info.suffix}"
        elif method == "advance":
            return f"{bangumi_name} S{season}E{episode}{version_suffix}{file_info.suffix}"
        elif method == "normal":
            logger.warning("[Renamer] Normal rename method is deprecated.")
            return file_info.media_path
        elif method == "subtitle_pn":
            return f"{file_info.title} S{season}E{episode}{version_suffix}.{file_info.language}{file_info.suffix}"
        elif method == "subtitle_advance":
            return f"{bangumi_name} S{season}E{episode}{version_suffix}.{file_info.language}{file_info.suffix}"
        else:
            logger.error(f"[Renamer] Unknown rename method: {method}")
            return file_info.media_path

    def rename_file(
            self,
            torrent_name: str,
            media_path: str,
            bangumi_name: str,
            method: str,
            season: int,
            _hash: str,
            **kwargs,
    ):
        ep = self._parser.torrent_parser(
            torrent_name=torrent_name,
            torrent_path=media_path,
            season=season,
        )
        if ep:
            # Log debug info for troubleshooting (only warn for non-movies)
            if ep.episode is None and not ep.is_movie:
                logger.warning(
                    f"[Renamer] Parsed file has no episode number: "
                    f"torrent_name={torrent_name}, media_path={media_path}, "
                    f"title={ep.title}, season={ep.season}"
                )
            new_path = self.gen_path(ep, bangumi_name, method=method)
            if media_path != new_path:
                if new_path not in self.check_pool.keys():
                    if self.rename_torrent_file(
                        _hash=_hash, old_path=media_path, new_path=new_path
                    ):
                        return Notification(
                            official_title=bangumi_name,
                            season=ep.season,
                            episode=ep.episode,
                            is_movie=ep.is_movie,
                        )
        else:
            logger.warning(
                f"[Renamer] Parse failed: torrent_name={torrent_name}, media_path={media_path}"
            )
            if settings.bangumi_manage.remove_bad_torrent:
                self.delete_torrent(hashes=_hash)
        return None

    def rename_collection(
            self,
            media_list: list[str],
            bangumi_name: str,
            season: int,
            method: str,
            _hash: str,
            **kwargs,
    ):
        for media_path in media_list:
            if self.is_ep(media_path):
                ep = self._parser.torrent_parser(
                    torrent_path=media_path,
                    season=season,
                )
                if ep:
                    new_path = self.gen_path(ep, bangumi_name, method=method)
                    if media_path != new_path:
                        renamed = self.rename_torrent_file(
                            _hash=_hash, old_path=media_path, new_path=new_path
                        )
                        if not renamed:
                            logger.warning(f"[Renamer] {media_path} rename failed")
                            # Delete bad torrent.
                            if settings.bangumi_manage.remove_bad_torrent:
                                self.delete_torrent(_hash)
                                break

    def rename_subtitles(
            self,
            subtitle_list: list[str],
            torrent_name: str,
            bangumi_name: str,
            season: int,
            method: str,
            _hash,
            **kwargs,
    ):
        method = "subtitle_" + method
        for subtitle_path in subtitle_list:
            sub = self._parser.torrent_parser(
                torrent_path=subtitle_path,
                torrent_name=torrent_name,
                season=season,
                file_type="subtitle",
            )
            if sub:
                new_path = self.gen_path(sub, bangumi_name, method=method)
                if subtitle_path != new_path:
                    renamed = self.rename_torrent_file(
                        _hash=_hash, old_path=subtitle_path, new_path=new_path
                    )
                    if not renamed:
                        logger.warning(f"[Renamer] {subtitle_path} rename failed")

    def rename(self) -> list[Notification]:
        # Get torrent info
        logger.debug("[Renamer] Start rename process.")
        rename_method = settings.bangumi_manage.rename_method
        torrents_info = self.get_torrent_info()
        renamed_info: list[Notification] = []
        for info in torrents_info:
            media_list, subtitle_list = self.check_files(info)
            bangumi_name, season = self._path_to_bangumi(info.save_path)
            kwargs = {
                "torrent_name": info.name,
                "bangumi_name": bangumi_name,
                "method": rename_method,
                "season": season,
                "_hash": info.hash,
            }
            # Rename single media file
            if len(media_list) == 1:
                notify_info = self.rename_file(media_path=media_list[0], **kwargs)
                if notify_info:
                    renamed_info.append(notify_info)
                # Rename subtitle file
                if len(subtitle_list) > 0:
                    self.rename_subtitles(subtitle_list=subtitle_list, **kwargs)
            # Rename collection
            elif len(media_list) > 1:
                logger.info("[Renamer] Start rename collection")
                self.rename_collection(media_list=media_list, **kwargs)
                if len(subtitle_list) > 0:
                    self.rename_subtitles(subtitle_list=subtitle_list, **kwargs)
                self.set_category(info.hash, "BangumiCollection")
            else:
                logger.warning(f"[Renamer] {info.name} has no media file")
        logger.debug("[Renamer] Rename process finished.")
        return renamed_info

    def compare_ep_version(self, torrent_name: str, torrent_hash: str):
        if re.search(r"v\d.", torrent_name):
            pass
        else:
            self.delete_torrent(hashes=torrent_hash)


if __name__ == "__main__":
    from module.conf import setup_logger

    settings.log.debug_enable = True
    setup_logger()
    with Renamer() as renamer:
        renamer.rename()
