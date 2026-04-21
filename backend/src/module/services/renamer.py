"""Renamer service for automatic file renaming and organization."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.bangumi import Bangumi
from module.domain.models.torrent import Torrent
from module.domain.parser.title_parser import TitleParser
from module.domain.value_objects import (
    EpisodeFile,
    SubtitleFile,
    sanitize_path_component,
)
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

        def safe_name(name: str) -> str:
            return sanitize_path_component(name)

        if file_info.is_movie or file_info.episode is None:
            if method == "none" or method == "subtitle_none":
                return file_info.media_path
            elif method == "pn" or method == "subtitle_pn":
                base_name = safe_name(file_info.title)
                if is_subtitle:
                    return f"{base_name}.{file_info.language}{file_info.suffix}"
                return f"{base_name}{file_info.suffix}"
            elif method == "advance" or method == "subtitle_advance":
                base_name = safe_name(bangumi_name)
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
                base_name = safe_name(
                    f"{file_info.title} {ep_type} {episode}{version_suffix}"
                )
                if is_subtitle:
                    return f"{base_name}.{file_info.language}{file_info.suffix}"
                return f"{base_name}{file_info.suffix}"
            elif method == "advance" or method == "subtitle_advance":
                base_name = safe_name(
                    f"{bangumi_name} {ep_type} {episode}{version_suffix}"
                )
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
            base_name = safe_name(
                f"{file_info.title} S{season}E{episode}{version_suffix}"
            )
            if is_subtitle:
                return f"{base_name}.{file_info.language}{file_info.suffix}"
            return f"{base_name}{file_info.suffix}"
        elif method == "advance" or method == "subtitle_advance":
            base_name = safe_name(
                f"{bangumi_name} S{season}E{episode}{version_suffix}"
            )
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
        """Rename all unrenamed torrents using a 3-phase approach to minimize DB lock time.

        Phase 1 (READ): Load unrenamed torrents and bangumi metadata.
        Phase 2 (NETWORK): Perform all downloader rename API calls (no DB writes).
        Phase 3 (WRITE): Short DB transaction to persist results (milliseconds).
        """
        logger.debug("[Renamer] Start rename_all process.")

        # --- Phase 1: READ (no write lock) ---
        unrenamed_torrents = await self.torrent_repo.get_unrenamed()
        if not unrenamed_torrents:
            logger.debug("[Renamer] No unrenamed torrents found.")
            return []

        unrenamed_hashes = {t.hash.lower() for t in unrenamed_torrents if t.hash}

        # Build cloud_paths map from already-loaded DB records so torrents_info
        # doesn't need to query the DB (prevents session conflicts with
        # concurrent scheduler jobs like rss_refresh).
        cloud_paths = {
            t.hash.lower(): t.pikpak_cloud_path
            for t in unrenamed_torrents
            if t.hash and t.pikpak_cloud_path
        }

        all_torrent_info = await downloader.torrents_info(
            status_filter="completed", cloud_paths=cloud_paths,
        )
        torrents_to_rename = [
            t for t in all_torrent_info if t.hash.lower() in unrenamed_hashes
        ]

        logger.info(
            f"[Renamer] Processing {len(torrents_to_rename)} unrenamed torrents "
            f"(filtered from {len(all_torrent_info)} total)"
        )

        bangumi_cache: dict[int, Bangumi] = {}
        for db_torrent in unrenamed_torrents:
            if db_torrent.bangumi_id and db_torrent.bangumi_id not in bangumi_cache:
                bangumi = await self.bangumi_repo.get_by_id(db_torrent.bangumi_id)
                if bangumi:
                    bangumi_cache[db_torrent.bangumi_id] = bangumi

        # --- Phase 2: NETWORK I/O (no DB transaction held) ---
        rename_successes: list[tuple[int, int]] = []
        rename_conflicts: list[tuple[int, str]] = []

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

            bangumi = bangumi_cache.get(db_torrent.bangumi_id)
            if not bangumi:
                logger.warning(
                    f"[Renamer] Bangumi {db_torrent.bangumi_id} not found for torrent {db_torrent.id}"
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
            conflict_target: Optional[str] = None

            if len(media_files) == 1:
                success, file_count, conflict_target = await self._rename_single_file(
                    torrent_info,
                    media_files[0],
                    bangumi,
                    downloader,
                    all_torrent_info,
                )
                if conflict_target is not None:
                    rename_conflicts.append((db_torrent.id, conflict_target))
                    continue
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
                if subtitle_files:
                    await self._rename_subtitles(
                        torrent_info,
                        subtitle_files,
                        bangumi,
                        downloader,
                    )
                success = True
                file_count = 0

            if success:
                rename_successes.append((db_torrent.id, file_count))
                logger.info(
                    f"[Renamer] Successfully renamed torrent {db_torrent.id} with {file_count} files"
                )
            else:
                logger.warning(
                    f"[Renamer] Failed to rename torrent {db_torrent.id}"
                )

        # --- Phase 3: SHORT write transaction (milliseconds) ---
        renamed_results: list[dict[str, Any]] = []
        if rename_successes:
            unrenamed_by_id = {t.id: t for t in unrenamed_torrents}
            for torrent_id, file_count in rename_successes:
                db_torrent = unrenamed_by_id.get(torrent_id)
                if db_torrent:
                    db_torrent.downloaded = True
                    db_torrent.renamed_at = datetime.now(timezone.utc)
                    db_torrent.renamed_file_count = file_count

                renamed_results.append(
                    {"torrent_id": torrent_id, "file_count": file_count}
                )

            await self.session.commit()

        for torrent_id, target in rename_conflicts:
            renamed_results.append(
                {"torrent_id": torrent_id, "file_count": 0, "conflict": target}
            )

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

        # --- Phase 1: READ + short writes for retrigger ---
        bangumi = await self.bangumi_repo.get_by_id(bangumi_id)
        if not bangumi:
            logger.warning(f"[Renamer] Bangumi {bangumi_id} not found")
            return []

        if retrigger:
            await self.torrent_repo.clear_rename_status(bangumi_id)
            await self.session.commit()
            logger.info(
                f"[Renamer] Cleared rename status for all torrents of bangumi {bangumi_id}"
            )

        bangumi_torrents = await self.torrent_repo.get_by_bangumi(bangumi_id)
        if not bangumi_torrents:
            logger.warning(f"[Renamer] No torrents found for bangumi {bangumi_id}")
            return []

        target_hashes = {t.hash.lower() for t in bangumi_torrents if t.hash}
        all_torrent_info = await downloader.torrents_info(status_filter="completed")
        torrents_to_process = [
            t for t in all_torrent_info if t.hash.lower() in target_hashes
        ]

        logger.info(
            f"[Renamer] Found {len(torrents_to_process)} torrents for bangumi {bangumi_id}"
        )

        # --- Phase 2: NETWORK I/O (move + rename, no DB transaction held) ---
        target_save_path = RenamerService.full_save_path(bangumi)
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
                all_torrent_info = await downloader.torrents_info(status_filter="completed")
                torrents_to_process = [
                    t for t in all_torrent_info if t.hash.lower() in target_hashes
                ]

        rename_successes: list[tuple[int, int]] = []
        rename_conflicts: list[tuple[int, str]] = []

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

            if db_torrent.renamed_at is not None:
                continue

            media_files, subtitle_files = self._classify_files(torrent_info.files)

            success = False
            file_count = 0
            conflict_target: Optional[str] = None

            if len(media_files) == 1:
                success, file_count, conflict_target = await self._rename_single_file(
                    torrent_info,
                    media_files[0],
                    bangumi,
                    downloader,
                    all_torrent_info,
                )
                if conflict_target is not None:
                    rename_conflicts.append((db_torrent.id, conflict_target))
                    continue
                if (success or retrigger) and subtitle_files:
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
                if (success or retrigger) and subtitle_files:
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
                if subtitle_files:
                    await self._rename_subtitles(
                        torrent_info,
                        subtitle_files,
                        bangumi,
                        downloader,
                    )
                success = True
                file_count = 0

            if retrigger and not success:
                success = True
                file_count = 0

            if success:
                rename_successes.append((db_torrent.id, file_count))
            else:
                logger.warning(
                    f"[Renamer] Failed to rename torrent {db_torrent.id}"
                )

        # --- Phase 3: SHORT write transaction (milliseconds) ---
        renamed_results: list[dict[str, Any]] = []
        if rename_successes:
            torrents_by_id = {t.id: t for t in bangumi_torrents}
            for torrent_id, file_count in rename_successes:
                db_torrent = torrents_by_id.get(torrent_id)
                if db_torrent:
                    db_torrent.downloaded = True
                    db_torrent.renamed_at = datetime.now(timezone.utc)
                    db_torrent.renamed_file_count = file_count

                renamed_results.append(
                    {"torrent_id": torrent_id, "file_count": file_count}
                )

            await self.session.commit()

        for torrent_id, target in rename_conflicts:
            renamed_results.append(
                {"torrent_id": torrent_id, "file_count": 0, "conflict": target}
            )

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
        all_torrent_info: list,
    ) -> tuple[bool, int, Optional[str]]:
        """Returns (success, file_count, conflict_target).

        conflict_target is a non-None target path string when a rename was
        skipped due to a collision (spec §10.3).
        """
        _season = bangumi.series.season if bangumi.series is not None else 1
        _title = bangumi.series.canonical_title if bangumi.series is not None else ""
        ep = self.parser.torrent_parser(
            torrent_name=torrent_info.name,
            torrent_path=media_path,
            season=_season,
        )
        if not ep:
            logger.warning(
                f"[Renamer] Failed to parse: torrent_name={torrent_info.name}, "
                f"media_path={media_path}"
            )
            return False, 0, None

        new_path = self.generate_rename_path(
            ep, _title, self.rename_method
        )
        logger.info(
            f"[Renamer] Rename check: '{media_path}' -> '{new_path}' "
            f"(parsed season={ep.season}, target season={_season})"
        )

        if media_path == new_path:
            logger.debug(f"[Renamer] Skipped (same path): {media_path}")
            return True, 1, None

        if self._target_exists_with_different_hash(
            all_torrent_info, torrent_info.hash, new_path,
        ):
            logger.warning(
                f"[Renamer] Conflict: '{new_path}' already exists for a "
                f"different torrent — skipping (spec §10.3)"
            )
            return False, 0, new_path

        success = await downloader.torrents_rename_file(
            torrent_info.hash, media_path, new_path
        )
        if not success:
            logger.warning(f"[Renamer] rename_torrent_file failed: {media_path}")
            return False, 0, None

        return True, 1, None

    @staticmethod
    def effective_root(bangumi: Bangumi) -> Optional[str]:
        """Return path_override when set, else the linked series root_path."""
        if bangumi.path_override:
            return bangumi.path_override
        if bangumi.series is not None:
            return bangumi.series.root_path
        return None

    @staticmethod
    def full_save_path(bangumi: Bangumi) -> Optional[str]:
        """Return the full per-season save path.

        Uses path_override directly when set; otherwise appends
        ``Season {season}`` to the series root_path.
        """
        if bangumi.path_override:
            return bangumi.path_override
        if bangumi.series is None:
            return None
        from pathlib import PurePosixPath
        return str(
            PurePosixPath(bangumi.series.root_path) / f"Season {bangumi.series.season}"
        )

    @staticmethod
    def _target_exists_with_different_hash(
        all_torrent_info: list,
        torrent_hash: str,
        target_path: str,
    ) -> bool:
        """Check the cached torrents_info for a hash≠ entry that already
        owns target_path. The caller is responsible for passing the same
        list it used in Phase 1, so the probe doesn't hit the downloader
        again per file."""
        for info in all_torrent_info:
            if info.hash and info.hash.lower() == torrent_hash.lower():
                continue
            for f in getattr(info, "files", []) or []:
                if getattr(f, "name", None) == target_path:
                    return True
        return False

    async def _rename_collection(
        self,
        torrent_info: Any,
        media_files: list[str],
        bangumi: Bangumi,
        downloader: DownloaderProtocol,
    ) -> tuple[bool, int]:
        _season = bangumi.series.season if bangumi.series is not None else 1
        _title = bangumi.series.canonical_title if bangumi.series is not None else ""
        renamed_count = 0
        for media_path in media_files:
            if not self._is_media_file(media_path):
                continue

            ep = self.parser.torrent_parser(
                torrent_path=media_path,
                season=_season,
            )
            if not ep:
                logger.warning(f"[Renamer] Failed to parse: {media_path}")
                continue

            new_path = self.generate_rename_path(ep, _title, self.rename_method)
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
        _season = bangumi.series.season if bangumi.series is not None else 1
        _title = bangumi.series.canonical_title if bangumi.series is not None else ""
        subtitle_method = "subtitle_" + self.rename_method
        for subtitle_path in subtitle_files:
            sub = self.parser.torrent_parser(
                torrent_path=subtitle_path,
                season=_season,
                file_type="subtitle",
            )
            if not sub:
                logger.warning(f"[Renamer] Failed to parse subtitle: {subtitle_path}")
                continue

            new_path = self.generate_rename_path(sub, _title, subtitle_method)
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
