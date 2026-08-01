"""Renamer service for automatic file renaming and organization."""

from __future__ import annotations

import logging
import posixpath
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.bangumi import Bangumi
from module.domain.models.torrent import RenameStatus, Torrent
from module.domain.parser.title_parser import TitleParser
from module.domain.value_objects import (
    EpisodeFile,
    SubtitleFile,
    sanitize_path_component,
)
from module.repositories.bangumi import BangumiRepository
from module.repositories.torrent import TorrentRepository
from module.services.downloader.interface import RenameOutcome

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
                    db_torrent.name,
                    bangumi,
                    downloader,
                    all_torrent_info,
                )
                if conflict_target is not None:
                    rename_conflicts.append((db_torrent.id, conflict_target))
                    continue
                if success and subtitle_files:
                    subtitle_outcome, subtitle_conflict = await self._rename_subtitles(
                        torrent_info,
                        subtitle_files,
                        bangumi,
                        downloader,
                    )
                    if subtitle_conflict is not None:
                        rename_conflicts.append((db_torrent.id, subtitle_conflict))
                        continue
                    if subtitle_outcome == RenameOutcome.ERROR:
                        continue
            elif len(media_files) > 1:
                success, file_count, conflict_target = await self._rename_collection(
                    torrent_info,
                    media_files,
                    bangumi,
                    downloader,
                )
                if conflict_target is not None:
                    rename_conflicts.append((db_torrent.id, conflict_target))
                    continue
                if success and subtitle_files:
                    subtitle_outcome, subtitle_conflict = await self._rename_subtitles(
                        torrent_info,
                        subtitle_files,
                        bangumi,
                        downloader,
                    )
                    if subtitle_conflict is not None:
                        rename_conflicts.append((db_torrent.id, subtitle_conflict))
                        continue
                    if subtitle_outcome == RenameOutcome.ERROR:
                        continue
            else:
                logger.warning(
                    f"[Renamer] Torrent {db_torrent.id} has no media files"
                )
                if subtitle_files:
                    subtitle_outcome, subtitle_conflict = await self._rename_subtitles(
                        torrent_info,
                        subtitle_files,
                        bangumi,
                        downloader,
                    )
                    if subtitle_conflict is not None:
                        rename_conflicts.append((db_torrent.id, subtitle_conflict))
                        continue
                    if subtitle_outcome == RenameOutcome.ERROR:
                        continue

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
        unrenamed_by_id = {t.id: t for t in unrenamed_torrents}
        if rename_successes:
            for torrent_id, file_count in rename_successes:
                db_torrent = unrenamed_by_id.get(torrent_id)
                if db_torrent:
                    db_torrent.downloaded = True
                    db_torrent.renamed_at = datetime.now(timezone.utc)
                    db_torrent.renamed_file_count = file_count
                    db_torrent.rename_status = RenameStatus.DONE
                    db_torrent.rename_conflict_target = None

                renamed_results.append(
                    {"torrent_id": torrent_id, "file_count": file_count}
                )

        for torrent_id, target in rename_conflicts:
            db_torrent = unrenamed_by_id.get(torrent_id)
            if db_torrent:
                db_torrent.rename_status = RenameStatus.CONFLICT
                db_torrent.rename_conflict_target = target
            renamed_results.append(
                {"torrent_id": torrent_id, "file_count": 0, "conflict": target}
            )

        if rename_successes or rename_conflicts:
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

        bangumi_torrents = await self.torrent_repo.get_visible_by_bangumi(bangumi_id)
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
                    db_torrent.name,
                    bangumi,
                    downloader,
                    all_torrent_info,
                )
                if conflict_target is not None:
                    rename_conflicts.append((db_torrent.id, conflict_target))
                    continue
                if (success or retrigger) and subtitle_files:
                    subtitle_outcome, subtitle_conflict = await self._rename_subtitles(
                        torrent_info,
                        subtitle_files,
                        bangumi,
                        downloader,
                    )
                    if subtitle_conflict is not None:
                        rename_conflicts.append((db_torrent.id, subtitle_conflict))
                        continue
                    if subtitle_outcome == RenameOutcome.ERROR:
                        continue
            elif len(media_files) > 1:
                success, file_count, conflict_target = await self._rename_collection(
                    torrent_info,
                    media_files,
                    bangumi,
                    downloader,
                )
                if conflict_target is not None:
                    rename_conflicts.append((db_torrent.id, conflict_target))
                    continue
                if (success or retrigger) and subtitle_files:
                    subtitle_outcome, subtitle_conflict = await self._rename_subtitles(
                        torrent_info,
                        subtitle_files,
                        bangumi,
                        downloader,
                    )
                    if subtitle_conflict is not None:
                        rename_conflicts.append((db_torrent.id, subtitle_conflict))
                        continue
                    if subtitle_outcome == RenameOutcome.ERROR:
                        continue
            else:
                logger.warning(
                    f"[Renamer] Torrent {db_torrent.id} has no media files"
                )
                if subtitle_files:
                    subtitle_outcome, subtitle_conflict = await self._rename_subtitles(
                        torrent_info,
                        subtitle_files,
                        bangumi,
                        downloader,
                    )
                    if subtitle_conflict is not None:
                        rename_conflicts.append((db_torrent.id, subtitle_conflict))
                        continue
                    if subtitle_outcome == RenameOutcome.ERROR:
                        continue

            if success:
                rename_successes.append((db_torrent.id, file_count))
            else:
                logger.warning(
                    f"[Renamer] Failed to rename torrent {db_torrent.id}"
                )

        # --- Phase 3: SHORT write transaction (milliseconds) ---
        renamed_results: list[dict[str, Any]] = []
        torrents_by_id = {t.id: t for t in bangumi_torrents}
        if rename_successes:
            for torrent_id, file_count in rename_successes:
                db_torrent = torrents_by_id.get(torrent_id)
                if db_torrent:
                    db_torrent.downloaded = True
                    db_torrent.renamed_at = datetime.now(timezone.utc)
                    db_torrent.renamed_file_count = file_count
                    db_torrent.rename_status = RenameStatus.DONE
                    db_torrent.rename_conflict_target = None

                renamed_results.append(
                    {"torrent_id": torrent_id, "file_count": file_count}
                )

        for torrent_id, target in rename_conflicts:
            db_torrent = torrents_by_id.get(torrent_id)
            if db_torrent:
                db_torrent.rename_status = RenameStatus.CONFLICT
                db_torrent.rename_conflict_target = target
            renamed_results.append(
                {"torrent_id": torrent_id, "file_count": 0, "conflict": target}
            )

        if rename_successes or rename_conflicts:
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
        source_torrent_name: str,
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
        if ep and not ep.is_movie and ep.episode is None and source_torrent_name:
            fallback_ep = self.parser.torrent_parser(
                torrent_name=source_torrent_name,
                torrent_path=media_path,
                season=_season,
            )
            if fallback_ep and fallback_ep.episode is not None:
                ep = fallback_ep
        if not ep:
            logger.warning(
                f"[Renamer] Failed to parse: torrent_name={torrent_info.name}, "
                f"media_path={media_path}"
            )
            return False, 0, None

        ep = self._apply_offset(ep, bangumi.offset or 0)
        if ep is None:
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

        outcome = await downloader.torrents_rename_file(
            torrent_info.hash, media_path, new_path
        )
        if outcome == RenameOutcome.OK:
            return True, 1, None
        if outcome == RenameOutcome.CONFLICT:
            logger.warning(
                "[Renamer] Downloader-reported name conflict for '%s' -> '%s'",
                media_path,
                new_path,
            )
            return False, 0, new_path
        logger.warning(f"[Renamer] rename_torrent_file failed: {media_path}")
        return False, 0, None

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
    def _apply_offset(
        ep: EpisodeFile | SubtitleFile, offset: int
    ) -> EpisodeFile | SubtitleFile | None:
        """Shift the parsed episode number by ``bangumi.offset``.

        Returns the same instance with episode mutated, or ``None`` when the
        offset would push the episode to a non-positive value (which would
        produce ``SxxE-1`` style filenames that no library scraper handles).

        Movies / specials (``is_movie=True`` or ``episode is None``) are
        passed through untouched because offsets only apply to numbered
        episodes.
        """
        if not offset:
            return ep
        if ep.is_movie or ep.episode is None:
            return ep
        new_ep = ep.episode + offset
        if new_ep <= 0:
            logger.warning(
                "[Renamer] Skipping rename — offset %+d would produce "
                "non-positive episode %s for '%s'",
                offset, new_ep, ep.media_path,
            )
            return None
        ep.episode = new_ep
        return ep

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
    ) -> tuple[bool, int, Optional[str]]:
        """Returns ``(success, file_count, conflict_target)``.

        For multi-file torrents we still report the *first* file that
        encounters a name conflict. Other files in the same torrent that
        happened to rename successfully before the conflict have already
        been renamed at the downloader — that's acceptable because every
        file inside one torrent is independently scrapable; the user will
        see both renamed entries and one stuck-on-conflict entry.
        """
        _season = bangumi.series.season if bangumi.series is not None else 1
        _title = bangumi.series.canonical_title if bangumi.series is not None else ""
        _offset = bangumi.offset or 0
        rename_plan: list[tuple[str, str]] = []
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

            ep = self._apply_offset(ep, _offset)
            if ep is None:
                continue

            new_path = self.generate_rename_path(ep, _title, self.rename_method)
            if media_path == new_path:
                continue

            rename_plan.append((media_path, new_path))

        targets: dict[str, list[int]] = {}
        for index, (_, target_path) in enumerate(rename_plan):
            targets.setdefault(target_path, []).append(index)

        for target_path, indexes in targets.items():
            if len(indexes) < 2:
                continue

            disambiguated: list[tuple[int, str]] = []
            for index in indexes:
                media_path, _ = rename_plan[index]
                edition_label = self._source_edition_label(media_path)
                if edition_label is None:
                    logger.warning(
                        "[Renamer] Collection target '%s' is ambiguous and '%s' "
                        "has no distinct source label",
                        target_path,
                        media_path,
                    )
                    return False, 0, target_path

                torrent_ep = self.parser.torrent_parser(
                    torrent_name=torrent_info.name,
                    torrent_path=media_path,
                    season=_season,
                )
                if not torrent_ep:
                    return False, 0, target_path
                torrent_ep = self._apply_offset(torrent_ep, _offset)
                if torrent_ep is None:
                    return False, 0, target_path
                episode_target = self.generate_rename_path(
                    torrent_ep, _title, self.rename_method
                )
                stem, suffix = posixpath.splitext(episode_target)
                disambiguated.append(
                    (index, f"{stem} - {edition_label}{suffix}")
                )

            distinct_targets = {target for _, target in disambiguated}
            if len(distinct_targets) != len(disambiguated):
                logger.warning(
                    "[Renamer] Collection target '%s' has duplicate source labels",
                    target_path,
                )
                return False, 0, target_path
            for index, disambiguated_target in disambiguated:
                media_path, _ = rename_plan[index]
                rename_plan[index] = (media_path, disambiguated_target)

        final_targets = [target for _, target in rename_plan]
        if len(set(final_targets)) != len(final_targets):
            conflict_target = next(
                target
                for target in final_targets
                if final_targets.count(target) > 1
            )
            return False, 0, conflict_target

        renamed_count = 0
        for media_path, new_path in rename_plan:
            outcome = await downloader.torrents_rename_file(
                torrent_info.hash, media_path, new_path
            )
            if outcome == RenameOutcome.OK:
                renamed_count += 1
            elif outcome == RenameOutcome.CONFLICT:
                logger.warning(
                    "[Renamer] Collection rename conflict on '%s' (target '%s') — "
                    "marking torrent for user resolution",
                    media_path,
                    new_path,
                )
                return False, 0, new_path
            else:
                logger.warning(f"[Renamer] {media_path} rename failed")
                return False, 0, None

        return renamed_count > 0, renamed_count, None

    @staticmethod
    def _source_edition_label(media_path: str) -> str | None:
        """Return a source-provided terminal ``【edition】`` label.

        This is only consulted after normal collection naming has produced a
        collision, so ordinary torrents retain their existing filenames.
        """
        stem, _ = posixpath.splitext(posixpath.basename(media_path))
        match = re.search(r"【([^【】]+)】$", stem)
        if not match:
            return None
        label = sanitize_path_component(match.group(1))
        return None if label == "_" else label

    async def _rename_subtitles(
        self,
        torrent_info: Any,
        subtitle_files: list[str],
        bangumi: Bangumi,
        downloader: DownloaderProtocol,
    ) -> tuple[RenameOutcome, Optional[str]]:
        _season = bangumi.series.season if bangumi.series is not None else 1
        _title = bangumi.series.canonical_title if bangumi.series is not None else ""
        _offset = bangumi.offset or 0
        subtitle_method = "subtitle_" + self.rename_method
        overall = RenameOutcome.OK
        for subtitle_path in subtitle_files:
            sub = self.parser.torrent_parser(
                torrent_path=subtitle_path,
                season=_season,
                file_type="subtitle",
            )
            if not sub:
                logger.warning(f"[Renamer] Failed to parse subtitle: {subtitle_path}")
                overall = RenameOutcome.ERROR
                continue

            sub = self._apply_offset(sub, _offset)
            if sub is None:
                overall = RenameOutcome.ERROR
                continue

            new_path = self.generate_rename_path(sub, _title, subtitle_method)
            if subtitle_path == new_path:
                continue

            outcome = await downloader.torrents_rename_file(
                torrent_info.hash, subtitle_path, new_path
            )
            if outcome == RenameOutcome.CONFLICT:
                logger.warning(
                    "[Renamer] Subtitle rename conflict for %s -> %s",
                    subtitle_path,
                    new_path,
                )
                return RenameOutcome.CONFLICT, new_path
            if outcome != RenameOutcome.OK:
                logger.warning(
                    "[Renamer] Subtitle rename %s for %s",
                    outcome.value,
                    subtitle_path,
                )
                overall = RenameOutcome.ERROR
        return overall, None

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
