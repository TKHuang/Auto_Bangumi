"""Reconciliation scheduled job.

Periodically syncs DB torrent states with downloader reality every 15 minutes.
Detects state drift, missing torrents, and path inconsistencies.
Uses asyncio.Lock to prevent concurrent reconciliation operations.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from ...conf import settings
from ...database import get_db_session
from ...domain.models.torrent import TorrentState
from ...repositories.torrent import TorrentRepository
from ...services.downloader import create_downloader

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Global lock to prevent concurrent reconciliation operations
_reconciliation_lock = asyncio.Lock()


async def reconciliation_job() -> None:
    """Reconcile DB torrent states with downloader reality.

    Registered with scheduler at 15 minute interval (900s).
    For each torrent in DOWNLOADING, COMPLETED, or STALE state:
    - Query downloader for current task status
    - Compare with DB state
    - Update states if drift detected
    - Mark as MISSING if task not found in downloader
    - Handle PikPak path inconsistencies

    Uses asyncio.Lock to prevent concurrent reconciliation.
    Errors are logged but don't crash the scheduler.
    Idempotent: Safe to run repeatedly without side effects.
    """
    if _reconciliation_lock.locked():
        logger.debug("Reconciliation job already running, skipping this cycle")
        return

    async with _reconciliation_lock:
        try:
            async_session_gen = get_db_session()
            session: AsyncSession = await async_session_gen.__anext__()

            try:
                downloader = create_downloader(settings, session=session)
                repo = TorrentRepository(session)

                states_to_check = [
                    TorrentState.DOWNLOADING,
                    TorrentState.COMPLETED,
                    TorrentState.STALE,
                ]

                torrents_to_check = []
                for state in states_to_check:
                    torrents = await repo.get_by_state(state)
                    torrents_to_check.extend(torrents)

                if not torrents_to_check:
                    logger.debug("No torrents to reconcile")
                    return

                logger.info(f"Reconciling {len(torrents_to_check)} torrents")

                downloader_torrents = await downloader.torrents_info()
                downloader_by_hash = {t.hash: t for t in downloader_torrents}

                updated_count = 0
                missing_count = 0

                for db_torrent in torrents_to_check:
                    if not db_torrent.hash:
                        logger.warning(
                            f"Torrent {db_torrent.id} has no hash, skipping"
                        )
                        continue

                    downloader_torrent = downloader_by_hash.get(db_torrent.hash)

                    if downloader_torrent is None:
                        if db_torrent.state != TorrentState.MISSING:
                            logger.warning(
                                f"Torrent {db_torrent.id} ({db_torrent.name}) not found in downloader, marking as MISSING"
                            )
                            await repo.update_state(
                                db_torrent.id, TorrentState.MISSING
                            )
                            missing_count += 1
                        continue

                    downloader_state = _normalize_downloader_state(
                        downloader_torrent.state
                    )

                    if downloader_state and downloader_state != db_torrent.state:
                        logger.info(
                            f"State drift detected for torrent {db_torrent.id}: DB={db_torrent.state.value}, Downloader={downloader_state.value}"
                        )
                        await repo.update_state(db_torrent.id, downloader_state)
                        updated_count += 1

                    if (
                        db_torrent.pikpak_cloud_path
                        and downloader_torrent.save_path
                        and db_torrent.pikpak_cloud_path
                        != downloader_torrent.save_path
                    ):
                        logger.warning(
                            f"Path drift detected for torrent {db_torrent.id}: DB={db_torrent.pikpak_cloud_path}, Downloader={downloader_torrent.save_path}"
                        )
                        if db_torrent.state != TorrentState.STALE:
                            await repo.update_state(
                                db_torrent.id, TorrentState.STALE
                            )
                            updated_count += 1

                logger.info(
                    f"Reconciliation completed: {updated_count} updated, {missing_count} missing"
                )

            finally:
                await session.close()

        except Exception as e:
            logger.exception(f"Error in reconciliation job: {e}")
            # Don't re-raise - let scheduler continue


def _normalize_downloader_state(downloader_state: str) -> TorrentState | None:
    state_lower = downloader_state.lower()

    state_mapping = {
        "downloading": TorrentState.DOWNLOADING,
        "uploading": TorrentState.COMPLETED,
        "stalledUP": TorrentState.COMPLETED,
        "stalledDL": TorrentState.DOWNLOADING,
        "completed": TorrentState.COMPLETED,
        "pausedUP": TorrentState.COMPLETED,
        "pausedDL": TorrentState.DOWNLOADING,
        "queuedUP": TorrentState.COMPLETED,
        "queuedDL": TorrentState.QUEUED,
        "checkingUP": TorrentState.COMPLETED,
        "checkingDL": TorrentState.DOWNLOADING,
        "error": TorrentState.ERROR,
        "missingFiles": TorrentState.MISSING,
        "queued": TorrentState.QUEUED,
        "pending": TorrentState.PENDING,
    }

    if state_lower in state_mapping:
        return state_mapping[state_lower]

    if "download" in state_lower:
        return TorrentState.DOWNLOADING
    if "upload" in state_lower or "seed" in state_lower:
        return TorrentState.COMPLETED
    if "complet" in state_lower:
        return TorrentState.COMPLETED
    if "error" in state_lower:
        return TorrentState.ERROR
    if "queue" in state_lower:
        return TorrentState.QUEUED

    logger.warning(f"Unknown downloader state: {downloader_state}")
    return None
