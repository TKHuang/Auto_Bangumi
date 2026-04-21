"""Tests for rename scheduled job."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from module.concurrency import rename_lock as rename_lock_module
from module.scheduler.jobs import rename as rename_module
from module.scheduler.jobs.rename import rename_job


class TestRenameJob:
    """Test rename_job function."""

    @pytest.fixture(autouse=True)
    async def reset_lock(self):
        """Reset lock before each test."""
        rename_lock_module._rename_lock = asyncio.Lock()
        yield
        rename_lock_module._rename_lock = asyncio.Lock()

    def _make_session_cm(self, mock_session: AsyncMock):
        """Build an async context-manager that yields mock_session.

        rename_job uses ``async with AsyncSessionLocal() as session``,
        so AsyncSessionLocal must be callable and return an object that
        supports the async context-manager protocol.
        """
        @asynccontextmanager
        async def _cm():
            yield mock_session

        return MagicMock(return_value=_cm())

    @pytest.mark.asyncio
    async def test_rename_job_success(self):
        """Test successful rename job execution."""
        mock_session = AsyncMock()
        mock_renamer = AsyncMock()
        mock_renamer.rename_all = AsyncMock()
        mock_downloader = AsyncMock()

        mock_session_local = self._make_session_cm(mock_session)

        with patch("module.scheduler.jobs.rename.AsyncSessionLocal", mock_session_local):
            with patch(
                "module.scheduler.jobs.rename.RenamerService"
            ) as mock_renamer_class:
                with patch(
                    "module.scheduler.jobs.rename.create_downloader"
                ) as mock_create_downloader:
                    mock_renamer_class.return_value = mock_renamer
                    mock_create_downloader.return_value = mock_downloader

                    await rename_job()

                    mock_renamer_class.assert_called_once()
                    mock_create_downloader.assert_called_once()
                    mock_renamer.rename_all.assert_called_once_with(mock_downloader)

    @pytest.mark.asyncio
    async def test_rename_job_skips_when_locked(self):
        """Test that rename job skips when lock is already held."""
        await rename_lock_module._rename_lock.acquire()

        mock_session_local = MagicMock()

        with patch("module.scheduler.jobs.rename.AsyncSessionLocal", mock_session_local):
            with patch(
                "module.scheduler.jobs.rename.RenamerService"
            ) as mock_renamer_class:
                await rename_job()

                # Lock held — nothing should have been called
                mock_session_local.assert_not_called()
                mock_renamer_class.assert_not_called()

        rename_lock_module._rename_lock.release()

    @pytest.mark.asyncio
    async def test_rename_job_handles_exception(self):
        """Test that rename job handles exceptions gracefully."""
        mock_session = AsyncMock()
        mock_renamer = AsyncMock()
        mock_renamer.rename_all = AsyncMock(
            side_effect=RuntimeError("Rename failed")
        )
        mock_downloader = AsyncMock()

        mock_session_local = self._make_session_cm(mock_session)

        with patch("module.scheduler.jobs.rename.AsyncSessionLocal", mock_session_local):
            with patch(
                "module.scheduler.jobs.rename.RenamerService"
            ) as mock_renamer_class:
                with patch(
                    "module.scheduler.jobs.rename.create_downloader"
                ) as mock_create_downloader:
                    mock_renamer_class.return_value = mock_renamer
                    mock_create_downloader.return_value = mock_downloader

                    # Should not raise — errors are caught and logged
                    await rename_job()

    @pytest.mark.asyncio
    async def test_rename_job_closes_session_on_error(self):
        """Test that session context-manager exits even when rename_all fails.

        With ``async with AsyncSessionLocal() as session`` the session is
        automatically closed when the context exits, even on exception.
        We verify that rename_all was called (and raised) without the
        job re-raising the exception.
        """
        mock_session = AsyncMock()
        mock_renamer = AsyncMock()
        mock_renamer.rename_all = AsyncMock(side_effect=ValueError("Test error"))
        mock_downloader = AsyncMock()

        mock_session_local = self._make_session_cm(mock_session)

        with patch("module.scheduler.jobs.rename.AsyncSessionLocal", mock_session_local):
            with patch(
                "module.scheduler.jobs.rename.RenamerService"
            ) as mock_renamer_class:
                with patch(
                    "module.scheduler.jobs.rename.create_downloader"
                ) as mock_create_downloader:
                    mock_renamer_class.return_value = mock_renamer
                    mock_create_downloader.return_value = mock_downloader

                    # Should not raise
                    await rename_job()

                    mock_renamer.rename_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_rename_job_uses_configured_rename_method(self):
        """Test that rename job uses configured rename method."""
        mock_session = AsyncMock()
        mock_renamer = AsyncMock()
        mock_renamer.rename_all = AsyncMock()
        mock_downloader = AsyncMock()

        mock_session_local = self._make_session_cm(mock_session)

        with patch("module.scheduler.jobs.rename.AsyncSessionLocal", mock_session_local):
            with patch(
                "module.scheduler.jobs.rename.RenamerService"
            ) as mock_renamer_class:
                with patch(
                    "module.scheduler.jobs.rename.create_downloader"
                ) as mock_create_downloader:
                    with patch("module.scheduler.jobs.rename.settings") as mock_settings:
                        mock_settings.bangumi_manage.rename_method = "pn"
                        mock_renamer_class.return_value = mock_renamer
                        mock_create_downloader.return_value = mock_downloader

                        await rename_job()

                        mock_renamer_class.assert_called_once_with(
                            mock_session, rename_method="pn"
                        )

    @pytest.mark.asyncio
    async def test_rename_job_lock_prevents_concurrent_execution(self):
        """Test that lock prevents concurrent execution."""
        call_count = 0
        execution_times = []

        async def slow_rename_all(downloader):
            nonlocal call_count
            call_count += 1
            execution_times.append(("start", call_count))
            await asyncio.sleep(0.1)
            execution_times.append(("end", call_count))

        mock_session = AsyncMock()
        mock_renamer = AsyncMock()
        mock_renamer.rename_all = slow_rename_all
        mock_downloader = AsyncMock()

        @asynccontextmanager
        async def _cm():
            yield mock_session

        mock_session_local = MagicMock(return_value=_cm())

        async def run_job():
            with patch("module.scheduler.jobs.rename.AsyncSessionLocal", mock_session_local):
                with patch(
                    "module.scheduler.jobs.rename.RenamerService"
                ) as mock_renamer_class:
                    with patch(
                        "module.scheduler.jobs.rename.create_downloader"
                    ) as mock_create_downloader:
                        mock_renamer_class.return_value = mock_renamer
                        mock_create_downloader.return_value = mock_downloader

                        await rename_job()

        await asyncio.gather(run_job(), run_job())

        # Only one execution should have happened (second was skipped by lock)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_rename_job_session_cleanup_on_get_db_error(self):
        """Test that job handles error when AsyncSessionLocal raises gracefully."""
        mock_session_local = MagicMock(side_effect=RuntimeError("DB connection failed"))

        with patch("module.scheduler.jobs.rename.AsyncSessionLocal", mock_session_local):
            # Should not raise — error is caught and logged
            await rename_job()

    @pytest.mark.asyncio
    async def test_rename_job_lock_is_released_after_execution(self):
        """Test that lock is released after job completes."""
        mock_session = AsyncMock()
        mock_renamer = AsyncMock()
        mock_renamer.rename_all = AsyncMock()
        mock_downloader = AsyncMock()

        @asynccontextmanager
        async def _cm():
            yield mock_session

        def _fresh_cm():
            return _cm()

        mock_session_local = MagicMock(side_effect=_fresh_cm)

        with patch("module.scheduler.jobs.rename.AsyncSessionLocal", mock_session_local):
            with patch(
                "module.scheduler.jobs.rename.RenamerService"
            ) as mock_renamer_class:
                with patch(
                    "module.scheduler.jobs.rename.create_downloader"
                ) as mock_create_downloader:
                    mock_renamer_class.return_value = mock_renamer
                    mock_create_downloader.return_value = mock_downloader

                    await rename_job()

                    assert not rename_lock_module._rename_lock.locked()

                    await rename_job()

                    assert mock_renamer.rename_all.call_count == 2
