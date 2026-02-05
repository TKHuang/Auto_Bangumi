"""Renamer service for automatic file renaming and organization."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.events.bus import event_bus
from module.domain.models.bangumi import Bangumi
from module.domain.models.torrent import Torrent, TorrentState
from module.domain.parser.title_parser import TitleParser
from module.domain.state_machine.torrent_state import TorrentStateMachine
from module.models.torrent import EpisodeFile, SubtitleFile
from module.repositories.bangumi import BangumiRepository
from module.repositories.torrent import TorrentRepository

if TYPE_CHECKING:
    from module.services.downloader.interface import DownloaderProtocol

logger = logging.getLogger(__name__)


class RenamerService:
    def __init__(
        self,
        session: AsyncSession,
        rename_method: str = "advance",
    ):
        self.session = session
        self.rename_method = rename_method
        self.parser = TitleParser()
        self.torrent_repo = TorrentRepository(session)
        self.bangumi_repo = BangumiRepository(session)

    @staticmethod
    def generate_rename_path(
        file_info: EpisodeFile | SubtitleFile,
        bangumi_name: str,
        method: str,
    ) -> str:
        is_subtitle = isinstance(file_info, SubtitleFile)

        if file_info.is_movie or file_info.episode is None:
            if method == "none" or method == "subtitle_none":
                return file_info.media_path
            elif method == "pn" or method == "subtitle_pn":
                base_name = file_info.title
                if is_subtitle:
                    return f"{base_name}.{file_info.language}{file_info.suffix}"
                return f"{base_name}{file_info.suffix}"
            elif method == "advance" or method == "subtitle_advance":
                base_name = bangumi_name
                if is_subtitle:
                    return f"{base_name}.{file_info.language}{file_info.suffix}"
                return f"{base_name}{file_info.suffix}"
            elif method == "normal" or method == "subtitle_normal":
                logger.warning("[Renamer] Normal rename method is deprecated.")
                return file_info.media_path
            else:
                logger.error(f"[Renamer] Unknown rename method: {method}")
                return file_info.media_path

        season = f"0{file_info.season}" if file_info.season < 10 else file_info.season
        ep_value = file_info.episode
        if ep_value == int(ep_value):
            ep_value = int(ep_value)
        episode = f"0{ep_value}" if ep_value < 10 else ep_value

        version_suffix = f"v{file_info.version}" if file_info.version else ""

        if file_info.episode_type is not None:
            ep_type = file_info.episode_type.value
            if method == "none" or method == "subtitle_none":
                return file_info.media_path
            elif method == "pn" or method == "subtitle_pn":
                base_name = f"{file_info.title} {ep_type} {episode}{version_suffix}"
                if is_subtitle:
                    return f"{base_name}.{file_info.language}{file_info.suffix}"
                return f"{base_name}{file_info.suffix}"
            elif method == "advance" or method == "subtitle_advance":
                base_name = f"{bangumi_name} {ep_type} {episode}{version_suffix}"
                if is_subtitle:
                    return f"{base_name}.{file_info.language}{file_info.suffix}"
                return f"{base_name}{file_info.suffix}"
            elif method == "normal" or method == "subtitle_normal":
                logger.warning("[Renamer] Normal rename method is deprecated.")
                return file_info.media_path
            else:
                logger.error(f"[Renamer] Unknown rename method: {method}")
                return file_info.media_path

        if method == "none" or method == "subtitle_none":
            return file_info.media_path
        elif method == "pn" or method == "subtitle_pn":
            base_name = (
                f"{file_info.title} S{season}E{episode}{version_suffix}"
            )
            if is_subtitle:
                return f"{base_name}.{file_info.language}{file_info.suffix}"
            return f"{base_name}{file_info.suffix}"
        elif method == "advance" or method == "subtitle_advance":
            base_name = f"{bangumi_name} S{season}E{episode}{version_suffix}"
            if is_subtitle:
                return f"{base_name}.{file_info.language}{file_info.suffix}"
            return f"{base_name}{file_info.suffix}"
        elif method == "normal" or method == "subtitle_normal":
            logger.warning("[Renamer] Normal rename method is deprecated.")
            return file_info.media_path
        else:
            logger.error(f"[Renamer] Unknown rename method: {method}")
            return file_info.media_path

    async def rename_all(
        self, downloader: DownloaderProtocol
    ) -> list[dict[str, Any]]:
        logger.debug("[Renamer] Start rename_all process.")

        unrenamed_torrents = await self.torrent_repo.get_unrenamed()
        if not unrenamed_torrents:
            logger.debug("[Renamer] No unrenamed torrents found.")
            return []

        unrenamed_hashes = {t.hash.lower() for t in unrenamed_torrents if t.hash}
        all_torrent_info = await downloader.torrents_info()
        torrents_to_rename = [
            t for t in all_torrent_info if t.hash.lower() in unrenamed_hashes
        ]

        logger.info(
            f"[Renamer] Processing {len(torrents_to_rename)} unrenamed torrents "
            f"(filtered from {len(all_torrent_info)} total)"
        )

        renamed_results: list[dict[str, Any]] = []

        for torrent_info in torrents_to_rename:
            db_torrent = next(
                (t for t in unrenamed_torrents if t.hash and t.hash.lower() == torrent_info.hash.lower()),
                None,
            )
            if not db_torrent:
                continue

            if not db_torrent.bangumi_id:
                logger.warning(
                    f"[Renamer] Torrent {db_torrent.id} has no bangumi_id"
                )
                continue
            
            bangumi = await self.bangumi_repo.get_by_id(db_torrent.bangumi_id)
            if not bangumi:
                logger.warning(
                    f"[Renamer] Bangumi {db_torrent.bangumi_id} not found for torrent {db_torrent.id}"
                )
                continue

            sm = TorrentStateMachine.from_str(db_torrent.state.value)
            try:
                sm.start_rename()
                db_torrent.state = TorrentState.RENAMING
                await self.session.flush()
                await event_bus.publish(
                    "torrent.state_changed",
                    {
                        "torrent_id": db_torrent.id,
                        "old_state": TorrentState.COMPLETED.value,
                        "new_state": TorrentState.RENAMING.value,
                    },
                )
            except Exception as e:
                logger.error(
                    f"[Renamer] Failed to transition torrent {db_torrent.id} to RENAMING: {e}"
                )
                continue

            media_files, subtitle_files = self._classify_files(torrent_info.files)

            logger.info(
                f"[Renamer] Torrent: name='{torrent_info.name}', "
                f"hash={torrent_info.hash[:16] if torrent_info.hash else 'None'}..., "
                f"files={len(torrent_info.files)}, media={len(media_files)}"
            )

            success = False
            file_count = 0

            if len(media_files) == 1:
                success, file_count = await self._rename_single_file(
                    torrent_info,
                    media_files[0],
                    bangumi,
                    downloader,
                )
                if success and subtitle_files:
                    await self._rename_subtitles(
                        torrent_info,
                        subtitle_files,
                        bangumi,
                        downloader,
                    )
            elif len(media_files) > 1:
                success, file_count = await self._rename_collection(
                    torrent_info,
                    media_files,
                    bangumi,
                    downloader,
                )
                if success and subtitle_files:
                    await self._rename_subtitles(
                        torrent_info,
                        subtitle_files,
                        bangumi,
                        downloader,
                    )
            else:
                logger.warning(
                    f"[Renamer] Torrent {db_torrent.id} has no media files"
                )

            if success:
                sm.finish_rename()
                db_torrent.state = TorrentState.RENAMED
                db_torrent.renamed_at = datetime.now(timezone.utc)
                db_torrent.renamed_file_count = file_count
                await self.session.flush()

                await event_bus.publish(
                    "torrent.renamed",
                    {"torrent_id": db_torrent.id, "file_count": file_count},
                )

                renamed_results.append(
                    {"torrent_id": db_torrent.id, "file_count": file_count}
                )
                logger.info(
                    f"[Renamer] Successfully renamed torrent {db_torrent.id} with {file_count} files"
                )
            else:
                db_torrent.state = TorrentState.COMPLETED
                await self.session.flush()
                logger.warning(
                    f"[Renamer] Failed to rename torrent {db_torrent.id}, restored to COMPLETED"
                )

        await self.session.commit()
        logger.debug(
            f"[Renamer] Rename_all process finished. Renamed {len(renamed_results)} torrents."
        )
        return renamed_results

    async def rename_bangumi(
        self,
        downloader: DownloaderProtocol,
        bangumi_id: int,
        retrigger: bool = False,
    ) -> list[dict[str, Any]]:
        logger.info(
            f"[Renamer] Start rename_bangumi for bangumi_id={bangumi_id}, retrigger={retrigger}"
        )

        bangumi = await self.bangumi_repo.get_by_id(bangumi_id)
        if not bangumi:
            logger.warning(f"[Renamer] Bangumi {bangumi_id} not found")
            return []

        if retrigger:
            await self.torrent_repo.clear_rename_status(bangumi_id)
            
            for t in await self.torrent_repo.get_by_bangumi(bangumi_id):
                if t.state == TorrentState.RENAMED:
                    t.state = TorrentState.COMPLETED
            
            await self.session.commit()
            logger.info(
                f"[Renamer] Cleared rename status for all torrents of bangumi {bangumi_id}"
            )

        bangumi_torrents = await self.torrent_repo.get_by_bangumi(bangumi_id)
        if not bangumi_torrents:
            logger.warning(f"[Renamer] No torrents found for bangumi {bangumi_id}")
            return []

        target_hashes = {t.hash.lower() for t in bangumi_torrents if t.hash}
        all_torrent_info = await downloader.torrents_info()
        torrents_to_process = [
            t for t in all_torrent_info if t.hash.lower() in target_hashes
        ]

        logger.info(
            f"[Renamer] Found {len(torrents_to_process)} torrents for bangumi {bangumi_id}"
        )

        target_save_path = bangumi.save_path
        hashes_to_move = []
        if target_save_path:
            for info in torrents_to_process:
                if info.save_path != target_save_path:
                    logger.info(
                        f"[Renamer] Season folder changed: '{info.save_path}' -> '{target_save_path}'"
                    )
                    hashes_to_move.append(info.hash)

        if hashes_to_move and target_save_path:
            logger.info(
                f"[Renamer] Moving {len(hashes_to_move)} torrents to '{target_save_path}'"
            )
            move_success = await downloader.move_torrent(
                hashes_to_move, target_save_path
            )
            if not move_success:
                logger.error(
                    f"[Renamer] Failed to move torrents to '{target_save_path}'"
                )
            else:
                logger.info(
                    f"[Renamer] Successfully moved {len(hashes_to_move)} torrents"
                )
                all_torrent_info = await downloader.torrents_info()
                torrents_to_process = [
                    t for t in all_torrent_info if t.hash.lower() in target_hashes
                ]

        renamed_results: list[dict[str, Any]] = []

        for torrent_info in torrents_to_process:
            db_torrent = next(
                (
                    t
                    for t in bangumi_torrents
                    if t.hash and t.hash.lower() == torrent_info.hash.lower()
                ),
                None,
            )
            if not db_torrent:
                continue

            sm = TorrentStateMachine.from_str(db_torrent.state.value)
            if db_torrent.state == TorrentState.COMPLETED:
                try:
                    sm.start_rename()
                    db_torrent.state = TorrentState.RENAMING
                    await self.session.flush()
                    await event_bus.publish(
                        "torrent.state_changed",
                        {
                            "torrent_id": db_torrent.id,
                            "old_state": TorrentState.COMPLETED.value,
                            "new_state": TorrentState.RENAMING.value,
                        },
                    )
                except Exception as e:
                    logger.error(
                        f"[Renamer] Failed to transition torrent {db_torrent.id} to RENAMING: {e}"
                    )
                    continue
            elif db_torrent.state != TorrentState.RENAMED:
                logger.warning(
                    f"[Renamer] Skipping torrent {db_torrent.id} in state {db_torrent.state}"
                )
                continue

            media_files, subtitle_files = self._classify_files(torrent_info.files)

            success = False
            file_count = 0

            if len(media_files) == 1:
                success, file_count = await self._rename_single_file(
                    torrent_info,
                    media_files[0],
                    bangumi,
                    downloader,
                )
                if success and subtitle_files:
                    await self._rename_subtitles(
                        torrent_info,
                        subtitle_files,
                        bangumi,
                        downloader,
                    )
            elif len(media_files) > 1:
                success, file_count = await self._rename_collection(
                    torrent_info,
                    media_files,
                    bangumi,
                    downloader,
                )
                if success and subtitle_files:
                    await self._rename_subtitles(
                        torrent_info,
                        subtitle_files,
                        bangumi,
                        downloader,
                    )

            if success:
                sm.finish_rename()
                db_torrent.state = TorrentState.RENAMED
                db_torrent.renamed_at = datetime.now(timezone.utc)
                db_torrent.renamed_file_count = file_count
                await self.session.flush()

                await event_bus.publish(
                    "torrent.renamed",
                    {"torrent_id": db_torrent.id, "file_count": file_count},
                )

                renamed_results.append(
                    {"torrent_id": db_torrent.id, "file_count": file_count}
                )
            else:
                if db_torrent.state == TorrentState.RENAMING:
                    db_torrent.state = TorrentState.COMPLETED
                    await self.session.flush()

        await self.session.commit()
        logger.info(
            f"[Renamer] Rename_bangumi finished for bangumi {bangumi_id}. "
            f"Renamed {len(renamed_results)} torrents."
        )
        return renamed_results

    async def _rename_single_file(
        self,
        torrent_info: Any,
        media_path: str,
        bangumi: Bangumi,
        downloader: DownloaderProtocol,
    ) -> tuple[bool, int]:
        ep = self.parser.torrent_parser(
            torrent_name=torrent_info.name,
            torrent_path=media_path,
            season=bangumi.season,
        )
        if not ep:
            logger.warning(
                f"[Renamer] Failed to parse: torrent_name={torrent_info.name}, "
                f"media_path={media_path}"
            )
            return False, 0

        new_path = self.generate_rename_path(ep, bangumi.official_title, self.rename_method)
        logger.info(
            f"[Renamer] Rename check: '{media_path}' -> '{new_path}' "
            f"(parsed season={ep.season}, target season={bangumi.season})"
        )

        if media_path == new_path:
            logger.debug(f"[Renamer] Skipped (same path): {media_path}")
            return True, 1

        success = await downloader.torrents_rename_file(
            torrent_info.hash, media_path, new_path
        )
        if not success:
            logger.warning(f"[Renamer] rename_torrent_file failed: {media_path}")
            return False, 0

        return True, 1

    async def _rename_collection(
        self,
        torrent_info: Any,
        media_files: list[str],
        bangumi: Bangumi,
        downloader: DownloaderProtocol,
    ) -> tuple[bool, int]:
        renamed_count = 0
        for media_path in media_files:
            if not self._is_media_file(media_path):
                continue

            ep = self.parser.torrent_parser(
                torrent_path=media_path,
                season=bangumi.season,
            )
            if not ep:
                logger.warning(f"[Renamer] Failed to parse: {media_path}")
                continue

            new_path = self.generate_rename_path(ep, bangumi.official_title, self.rename_method)
            if media_path == new_path:
                continue

            success = await downloader.torrents_rename_file(
                torrent_info.hash, media_path, new_path
            )
            if success:
                renamed_count += 1
            else:
                logger.warning(f"[Renamer] {media_path} rename failed")
                return False, 0

        return renamed_count > 0, renamed_count

    async def _rename_subtitles(
        self,
        torrent_info: Any,
        subtitle_files: list[str],
        bangumi: Bangumi,
        downloader: DownloaderProtocol,
    ) -> None:
        subtitle_method = "subtitle_" + self.rename_method
        for subtitle_path in subtitle_files:
            sub = self.parser.torrent_parser(
                torrent_path=subtitle_path,
                torrent_name=torrent_info.name,
                season=bangumi.season,
                file_type="subtitle",
            )
            if not sub:
                logger.warning(f"[Renamer] Failed to parse subtitle: {subtitle_path}")
                continue

            new_path = self.generate_rename_path(sub, bangumi.official_title, subtitle_method)
            if subtitle_path == new_path:
                continue

            success = await downloader.torrents_rename_file(
                torrent_info.hash, subtitle_path, new_path
            )
            if not success:
                logger.warning(f"[Renamer] {subtitle_path} rename failed")

    def _classify_files(
        self, files: list[Any]
    ) -> tuple[list[str], list[str]]:
        media_files = []
        subtitle_files = []
        for f in files:
            file_name = f.name
            if self._is_media_file(file_name):
                media_files.append(file_name)
            elif self._is_subtitle_file(file_name):
                subtitle_files.append(file_name)
        return media_files, subtitle_files

    @staticmethod
    def _is_media_file(path: str) -> bool:
        media_exts = (".mkv", ".mp4", ".avi", ".wmv", ".webm", ".flv", ".mov", ".ts", ".m2ts")
        return path.lower().endswith(media_exts)

    @staticmethod
    def _is_subtitle_file(path: str) -> bool:
        subtitle_exts = (".ass", ".ssa", ".srt", ".sub", ".vtt")
        return path.lower().endswith(subtitle_exts)
