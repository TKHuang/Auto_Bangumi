"""Tests for reconciliation scheduled job."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from module.domain.models.torrent import TorrentState
from module.scheduler.jobs import reconciliation as reconciliation_module
from module.scheduler.jobs.reconciliation import reconciliation_job


def _make_db_torrent(
    torrent_id: int,
    state: TorrentState,
    torrent_hash: str = "hash",
    name: str = "torrent",
    pikpak_cloud_path: str | None = None,
):
    return SimpleNamespace(
        id=torrent_id,
        state=state,
        hash=torrent_hash,
        name=name,
        pikpak_cloud_path=pikpak_cloud_path,
    )


def _make_downloader_torrent(
    torrent_hash: str,
    state: str,
    save_path: str | None = None,
):
    return SimpleNamespace(hash=torrent_hash, state=state, save_path=save_path)


class TestReconciliationJob:
    """Test reconciliation_job function."""

    @pytest.fixture(autouse=True)
    async def reset_lock(self):
        """Reset lock before each test."""
        reconciliation_module._reconciliation_lock = asyncio.Lock()
        yield
        reconciliation_module._reconciliation_lock = asyncio.Lock()

    @pytest.mark.asyncio
    async def test_reconciliation_job_skips_when_locked(self):
        """Test that reconciliation job skips when lock is already held."""
        await reconciliation_module._reconciliation_lock.acquire()

        with patch(
            "module.scheduler.jobs.reconciliation.get_db_session"
        ) as mock_get_session:
            await reconciliation_job()
            mock_get_session.assert_not_called()

        reconciliation_module._reconciliation_lock.release()

    @pytest.mark.asyncio
    async def test_reconciliation_job_no_torrents(self):
        """Test job exits early when no torrents are found."""
        mock_session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.get_by_state.side_effect = [[], [], []]
        mock_downloader = AsyncMock()

        async_gen = AsyncMock()
        async_gen.__anext__ = AsyncMock(return_value=mock_session)

        with patch(
            "module.scheduler.jobs.reconciliation.get_db_session"
        ) as mock_get_session:
            with patch(
                "module.scheduler.jobs.reconciliation.create_downloader"
            ) as mock_create_downloader:
                with patch(
                    "module.scheduler.jobs.reconciliation.TorrentRepository"
                ) as mock_repo_class:
                    mock_get_session.return_value = async_gen
                    mock_create_downloader.return_value = mock_downloader
                    mock_repo_class.return_value = mock_repo

                    await reconciliation_job()

                    mock_downloader.torrents_info.assert_not_called()
                    mock_repo.update_state.assert_not_called()
                    mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconciliation_job_marks_missing(self):
        """Test job marks torrents missing when downloader lacks them."""
        mock_session = AsyncMock()
        db_torrent = _make_db_torrent(1, TorrentState.DOWNLOADING, "abc")

        mock_repo = AsyncMock()
        mock_repo.get_by_state.side_effect = [[db_torrent], [], []]
        mock_repo.update_state = AsyncMock()

        mock_downloader = AsyncMock()
        mock_downloader.torrents_info = AsyncMock(return_value=[])

        async_gen = AsyncMock()
        async_gen.__anext__ = AsyncMock(return_value=mock_session)

        with patch(
            "module.scheduler.jobs.reconciliation.get_db_session"
        ) as mock_get_session:
            with patch(
                "module.scheduler.jobs.reconciliation.create_downloader"
            ) as mock_create_downloader:
                with patch(
                    "module.scheduler.jobs.reconciliation.TorrentRepository"
                ) as mock_repo_class:
                    mock_get_session.return_value = async_gen
                    mock_create_downloader.return_value = mock_downloader
                    mock_repo_class.return_value = mock_repo

                    await reconciliation_job()

                    mock_repo.update_state.assert_called_once_with(
                        db_torrent.id, TorrentState.MISSING
                    )
                    mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconciliation_job_updates_state_drift(self):
        """Test job updates state when downloader and DB drift."""
        mock_session = AsyncMock()
        db_torrent = _make_db_torrent(2, TorrentState.COMPLETED, "def")
        downloader_torrent = _make_downloader_torrent("def", "downloading")

        mock_repo = AsyncMock()
        mock_repo.get_by_state.side_effect = [[db_torrent], [], []]
        mock_repo.update_state = AsyncMock()

        mock_downloader = AsyncMock()
        mock_downloader.torrents_info = AsyncMock(return_value=[downloader_torrent])

        async_gen = AsyncMock()
        async_gen.__anext__ = AsyncMock(return_value=mock_session)

        with patch(
            "module.scheduler.jobs.reconciliation.get_db_session"
        ) as mock_get_session:
            with patch(
                "module.scheduler.jobs.reconciliation.create_downloader"
            ) as mock_create_downloader:
                with patch(
                    "module.scheduler.jobs.reconciliation.TorrentRepository"
                ) as mock_repo_class:
                    mock_get_session.return_value = async_gen
                    mock_create_downloader.return_value = mock_downloader
                    mock_repo_class.return_value = mock_repo

                    await reconciliation_job()

                    mock_repo.update_state.assert_called_once_with(
                        db_torrent.id, TorrentState.DOWNLOADING
                    )

    @pytest.mark.asyncio
    async def test_reconciliation_job_marks_stale_on_path_drift(self):
        """Test job marks torrents stale on path drift."""
        mock_session = AsyncMock()
        db_torrent = _make_db_torrent(
            3,
            TorrentState.COMPLETED,
            "ghi",
            pikpak_cloud_path="/old/path",
        )
        downloader_torrent = _make_downloader_torrent(
            "ghi", "completed", save_path="/new/path"
        )

        mock_repo = AsyncMock()
        mock_repo.get_by_state.side_effect = [[db_torrent], [], []]
        mock_repo.update_state = AsyncMock()

        mock_downloader = AsyncMock()
        mock_downloader.torrents_info = AsyncMock(return_value=[downloader_torrent])

        async_gen = AsyncMock()
        async_gen.__anext__ = AsyncMock(return_value=mock_session)

        with patch(
            "module.scheduler.jobs.reconciliation.get_db_session"
        ) as mock_get_session:
            with patch(
                "module.scheduler.jobs.reconciliation.create_downloader"
            ) as mock_create_downloader:
                with patch(
                    "module.scheduler.jobs.reconciliation.TorrentRepository"
                ) as mock_repo_class:
                    mock_get_session.return_value = async_gen
                    mock_create_downloader.return_value = mock_downloader
                    mock_repo_class.return_value = mock_repo

                    await reconciliation_job()

                    mock_repo.update_state.assert_called_once_with(
                        db_torrent.id, TorrentState.STALE
                    )

    @pytest.mark.asyncio
    async def test_reconciliation_job_handles_exception(self):
        """Test that job handles exceptions gracefully."""
        mock_session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.get_by_state.side_effect = RuntimeError("DB failure")

        mock_downloader = AsyncMock()

        async_gen = AsyncMock()
        async_gen.__anext__ = AsyncMock(return_value=mock_session)

        with patch(
            "module.scheduler.jobs.reconciliation.get_db_session"
        ) as mock_get_session:
            with patch(
                "module.scheduler.jobs.reconciliation.create_downloader"
            ) as mock_create_downloader:
                with patch(
                    "module.scheduler.jobs.reconciliation.TorrentRepository"
                ) as mock_repo_class:
                    mock_get_session.return_value = async_gen
                    mock_create_downloader.return_value = mock_downloader
                    mock_repo_class.return_value = mock_repo

                    await reconciliation_job()

                    mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconciliation_job_uses_settings_for_downloader(self):
        """Test that downloader is created with settings."""
        mock_session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.get_by_state.side_effect = [[], [], []]

        async_gen = AsyncMock()
        async_gen.__anext__ = AsyncMock(return_value=mock_session)

        with patch(
            "module.scheduler.jobs.reconciliation.get_db_session"
        ) as mock_get_session:
            with patch(
                "module.scheduler.jobs.reconciliation.create_downloader"
            ) as mock_create_downloader:
                with patch(
                    "module.scheduler.jobs.reconciliation.TorrentRepository"
                ) as mock_repo_class:
                    with patch(
                        "module.scheduler.jobs.reconciliation.settings"
                    ) as mock_settings:
                        mock_get_session.return_value = async_gen
                        mock_repo_class.return_value = mock_repo

                        await reconciliation_job()

                        mock_create_downloader.assert_called_once_with(mock_settings)
