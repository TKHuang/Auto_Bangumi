"""Tests for rename scheduled job."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from module.scheduler.jobs import rename as rename_module
from module.scheduler.jobs.rename import rename_job


class TestRenameJob:
    """Test rename_job function."""

    @pytest.fixture(autouse=True)
    async def reset_lock(self):
        """Reset lock before each test."""
        rename_module._rename_lock = asyncio.Lock()
        yield
        rename_module._rename_lock = asyncio.Lock()

    @pytest.mark.asyncio
    async def test_rename_job_success(self):
        """Test successful rename job execution."""
        mock_session = AsyncMock()
        mock_renamer = AsyncMock()
        mock_renamer.rename_all = AsyncMock()
        mock_downloader = AsyncMock()

        with patch("module.scheduler.jobs.rename.get_db_session") as mock_get_session:
            with patch(
                "module.scheduler.jobs.rename.RenamerService"
            ) as mock_renamer_class:
                with patch(
                    "module.scheduler.jobs.rename.create_downloader"
                ) as mock_create_downloader:
                    # Setup mocks
                    async_gen = AsyncMock()
                    async_gen.__anext__ = AsyncMock(return_value=mock_session)
                    mock_get_session.return_value = async_gen
                    mock_renamer_class.return_value = mock_renamer
                    mock_create_downloader.return_value = mock_downloader

                    # Execute
                    await rename_job()

                    # Verify
                    mock_get_session.assert_called_once()
                    mock_renamer_class.assert_called_once()
                    mock_create_downloader.assert_called_once()
                    mock_renamer.rename_all.assert_called_once_with(mock_downloader)
                    mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_rename_job_skips_when_locked(self):
        """Test that rename job skips when lock is already held."""
        # Acquire lock
        await rename_module._rename_lock.acquire()

        mock_session = AsyncMock()
        mock_renamer = AsyncMock()

        with patch("module.scheduler.jobs.rename.get_db_session") as mock_get_session:
            with patch(
                "module.scheduler.jobs.rename.RenamerService"
            ) as mock_renamer_class:
                # Execute
                await rename_job()

                # Verify - should not call anything
                mock_get_session.assert_not_called()
                mock_renamer_class.assert_not_called()

        # Release lock
        rename_module._rename_lock.release()

    @pytest.mark.asyncio
    async def test_rename_job_handles_exception(self):
        """Test that rename job handles exceptions gracefully."""
        mock_session = AsyncMock()
        mock_renamer = AsyncMock()
        mock_renamer.rename_all = AsyncMock(
            side_effect=RuntimeError("Rename failed")
        )
        mock_downloader = AsyncMock()

        with patch("module.scheduler.jobs.rename.get_db_session") as mock_get_session:
            with patch(
                "module.scheduler.jobs.rename.RenamerService"
            ) as mock_renamer_class:
                with patch(
                    "module.scheduler.jobs.rename.create_downloader"
                ) as mock_create_downloader:
                    # Setup mocks
                    async_gen = AsyncMock()
                    async_gen.__anext__ = AsyncMock(return_value=mock_session)
                    mock_get_session.return_value = async_gen
                    mock_renamer_class.return_value = mock_renamer
                    mock_create_downloader.return_value = mock_downloader

                    # Execute - should not raise
                    await rename_job()

                    # Verify session was closed even on error
                    mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_rename_job_closes_session_on_error(self):
        """Test that session is closed even when rename_all fails."""
        mock_session = AsyncMock()
        mock_renamer = AsyncMock()
        mock_renamer.rename_all = AsyncMock(side_effect=ValueError("Test error"))
        mock_downloader = AsyncMock()

        with patch("module.scheduler.jobs.rename.get_db_session") as mock_get_session:
            with patch(
                "module.scheduler.jobs.rename.RenamerService"
            ) as mock_renamer_class:
                with patch(
                    "module.scheduler.jobs.rename.create_downloader"
                ) as mock_create_downloader:
                    # Setup mocks
                    async_gen = AsyncMock()
                    async_gen.__anext__ = AsyncMock(return_value=mock_session)
                    mock_get_session.return_value = async_gen
                    mock_renamer_class.return_value = mock_renamer
                    mock_create_downloader.return_value = mock_downloader

                    # Execute
                    await rename_job()

                    # Verify session was closed
                    mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_rename_job_uses_configured_rename_method(self):
        """Test that rename job uses configured rename method."""
        mock_session = AsyncMock()
        mock_renamer = AsyncMock()
        mock_renamer.rename_all = AsyncMock()
        mock_downloader = AsyncMock()

        with patch("module.scheduler.jobs.rename.get_db_session") as mock_get_session:
            with patch(
                "module.scheduler.jobs.rename.RenamerService"
            ) as mock_renamer_class:
                with patch(
                    "module.scheduler.jobs.rename.create_downloader"
                ) as mock_create_downloader:
                    with patch("module.scheduler.jobs.rename.settings") as mock_settings:
                        # Setup mocks
                        mock_settings.bangumi_manage.rename_method = "pn"
                        async_gen = AsyncMock()
                        async_gen.__anext__ = AsyncMock(return_value=mock_session)
                        mock_get_session.return_value = async_gen
                        mock_renamer_class.return_value = mock_renamer
                        mock_create_downloader.return_value = mock_downloader

                        # Execute
                        await rename_job()

                        # Verify RenamerService was called with correct rename_method
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

        async def run_job():
            with patch("module.scheduler.jobs.rename.get_db_session") as mock_get_session:
                with patch(
                    "module.scheduler.jobs.rename.RenamerService"
                ) as mock_renamer_class:
                    with patch(
                        "module.scheduler.jobs.rename.create_downloader"
                    ) as mock_create_downloader:
                        # Setup mocks
                        async_gen = AsyncMock()
                        async_gen.__anext__ = AsyncMock(return_value=mock_session)
                        mock_get_session.return_value = async_gen
                        mock_renamer_class.return_value = mock_renamer
                        mock_create_downloader.return_value = mock_downloader

                        # Execute
                        await rename_job()

        # Run two jobs concurrently
        await asyncio.gather(run_job(), run_job())

        # Verify only one execution happened (second was skipped)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_rename_job_session_cleanup_on_get_db_error(self):
        """Test that job handles error in get_db_session gracefully."""
        with patch("module.scheduler.jobs.rename.get_db_session") as mock_get_session:
            mock_get_session.side_effect = RuntimeError("DB connection failed")

            # Execute - should not raise
            await rename_job()

            # Verify get_db_session was called
            mock_get_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_rename_job_lock_is_released_after_execution(self):
        """Test that lock is released after job completes."""
        mock_session = AsyncMock()
        mock_renamer = AsyncMock()
        mock_renamer.rename_all = AsyncMock()
        mock_downloader = AsyncMock()

        with patch("module.scheduler.jobs.rename.get_db_session") as mock_get_session:
            with patch(
                "module.scheduler.jobs.rename.RenamerService"
            ) as mock_renamer_class:
                with patch(
                    "module.scheduler.jobs.rename.create_downloader"
                ) as mock_create_downloader:
                    # Setup mocks
                    async_gen = AsyncMock()
                    async_gen.__anext__ = AsyncMock(return_value=mock_session)
                    mock_get_session.return_value = async_gen
                    mock_renamer_class.return_value = mock_renamer
                    mock_create_downloader.return_value = mock_downloader

                    # Execute first job
                    await rename_job()

                    # Verify lock is released (not locked)
                    assert not rename_module._rename_lock.locked()

                    # Execute second job - should succeed (not skipped)
                    await rename_job()

                    # Verify rename_all was called twice
                    assert mock_renamer.rename_all.call_count == 2
