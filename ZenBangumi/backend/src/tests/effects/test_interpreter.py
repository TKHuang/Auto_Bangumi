import pytest
from unittest.mock import AsyncMock, patch

from zen_bangumi.domain.commands.base import (
    DownloadTorrent,
    RenameFile,
    SendNotification,
)
from zen_bangumi.effects.interpreter import EffectInterpreter
from zen_bangumi.effects.result import EffectStatus


class TestEffectInterpreter:
    async def test_execute_single_command_success(self):
        interpreter = EffectInterpreter()
        command = DownloadTorrent(
            torrent_url="http://example.com/test.torrent",
            save_path="/downloads",
            bangumi_id=1,
        )
        
        with patch.object(interpreter, '_dispatch', new_callable=AsyncMock) as mock_dispatch:
            results = await interpreter.execute([command])
        
        assert len(results) == 1
        assert results[0].status == EffectStatus.SUCCESS
        assert results[0].command == command
        mock_dispatch.assert_called_once_with(command)

    async def test_idempotency_skips_duplicate_commands(self):
        interpreter = EffectInterpreter()
        command = DownloadTorrent(
            torrent_url="http://example.com/test.torrent",
            save_path="/downloads",
            bangumi_id=1,
        )
        
        with patch.object(interpreter, '_dispatch', new_callable=AsyncMock) as mock_dispatch:
            results1 = await interpreter.execute([command])
            results2 = await interpreter.execute([command])
        
        assert results1[0].status == EffectStatus.SUCCESS
        assert results2[0].status == EffectStatus.SKIPPED
        mock_dispatch.assert_called_once()

    async def test_retry_on_failure_then_success(self):
        interpreter = EffectInterpreter(max_retries=3, retry_delay=0.01)
        command = RenameFile(
            source_path="/old/path",
            target_path="/new/path",
            downloader_type="pikpak",
        )
        
        call_count = 0
        async def mock_dispatch_fail_twice(cmd):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Transient error")
        
        with patch.object(interpreter, '_dispatch', side_effect=mock_dispatch_fail_twice):
            results = await interpreter.execute([command])
        
        assert len(results) == 1
        assert results[0].status == EffectStatus.SUCCESS
        assert call_count == 3

    async def test_retry_exhausted_returns_failed(self):
        interpreter = EffectInterpreter(max_retries=3, retry_delay=0.01)
        command = RenameFile(
            source_path="/old/path",
            target_path="/new/path",
            downloader_type="pikpak",
        )
        
        async def mock_dispatch_always_fail(cmd):
            raise Exception("Permanent error")
        
        with patch.object(interpreter, '_dispatch', side_effect=mock_dispatch_always_fail):
            results = await interpreter.execute([command])
        
        assert len(results) == 1
        assert results[0].status == EffectStatus.FAILED
        assert results[0].error == "Permanent error"

    async def test_batch_execution_preserves_order(self):
        interpreter = EffectInterpreter()
        commands = [
            DownloadTorrent("http://example.com/1.torrent", "/downloads", 1),
            RenameFile("/old/1", "/new/1", "pikpak"),
            SendNotification("Test", "Message"),
        ]
        
        with patch.object(interpreter, '_dispatch', new_callable=AsyncMock):
            results = await interpreter.execute(commands)
        
        assert len(results) == 3
        assert results[0].command == commands[0]
        assert results[1].command == commands[1]
        assert results[2].command == commands[2]

    async def test_failed_command_does_not_add_to_executed_keys(self):
        interpreter = EffectInterpreter(max_retries=1, retry_delay=0.01)
        command = DownloadTorrent(
            torrent_url="http://example.com/test.torrent",
            save_path="/downloads",
            bangumi_id=1,
        )
        
        async def mock_dispatch_fail(cmd):
            raise Exception("Error")
        
        with patch.object(interpreter, '_dispatch', side_effect=mock_dispatch_fail):
            results1 = await interpreter.execute([command])
        
        assert results1[0].status == EffectStatus.FAILED
        
        with patch.object(interpreter, '_dispatch', new_callable=AsyncMock):
            results2 = await interpreter.execute([command])
        
        assert results2[0].status == EffectStatus.SUCCESS

    async def test_different_commands_same_type_different_keys(self):
        interpreter = EffectInterpreter()
        command1 = DownloadTorrent("http://example.com/1.torrent", "/downloads", 1)
        command2 = DownloadTorrent("http://example.com/2.torrent", "/downloads", 2)
        
        with patch.object(interpreter, '_dispatch', new_callable=AsyncMock):
            results = await interpreter.execute([command1, command2])
        
        assert len(results) == 2
        assert results[0].status == EffectStatus.SUCCESS
        assert results[1].status == EffectStatus.SUCCESS
        assert command1.idempotency_key != command2.idempotency_key
