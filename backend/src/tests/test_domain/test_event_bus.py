"""
TDD tests for in-process async event bus.

Tests cover:
- Subscribe and publish for async handlers
- Multiple handlers for same event all fire
- Error in one handler doesn't prevent others
- Publishing to event with no subscribers is no-op
"""

import asyncio
import pytest
from module.domain.events import event_bus


@pytest.mark.asyncio
class TestEventBusSubscribePublish:
    """Test basic subscribe and publish functionality."""

    async def test_subscribe_and_publish_single_handler(self):
        """Test that a single handler receives published event."""
        results = []

        async def handler(data):
            results.append(data)

        event_bus.subscribe("test.event", handler)
        await event_bus.publish("test.event", {"value": 42})

        assert len(results) == 1
        assert results[0] == {"value": 42}

    async def test_multiple_handlers_same_event(self):
        """Test that multiple handlers for same event all fire."""
        results = []

        async def handler1(data):
            results.append(("handler1", data))

        async def handler2(data):
            results.append(("handler2", data))

        event_bus.subscribe("test.multi", handler1)
        event_bus.subscribe("test.multi", handler2)
        await event_bus.publish("test.multi", {"id": 1})

        assert len(results) == 2
        assert ("handler1", {"id": 1}) in results
        assert ("handler2", {"id": 1}) in results

    async def test_publish_no_subscribers_is_noop(self):
        """Test that publishing to event with no subscribers is no-op."""
        # Should not raise any exception
        await event_bus.publish("nonexistent.event", {"data": "test"})

    async def test_handler_receives_correct_data(self):
        """Test that handler receives exact data published."""
        received = []

        async def handler(data):
            received.append(data)

        event_bus.subscribe("test.data", handler)
        test_data = {"torrent_id": 123, "state": "completed"}
        await event_bus.publish("test.data", test_data)

        assert received[0] == test_data


@pytest.mark.asyncio
class TestEventBusErrorIsolation:
    """Test error isolation between handlers."""

    async def test_error_in_one_handler_doesnt_block_others(self):
        """Test that error in one handler doesn't prevent others from running."""
        results = []

        async def failing_handler(data):
            raise ValueError("Handler error")

        async def working_handler(data):
            results.append(data)

        event_bus.subscribe("test.error", failing_handler)
        event_bus.subscribe("test.error", working_handler)

        # Should not raise exception
        await event_bus.publish("test.error", {"test": "data"})

        # Working handler should still execute
        assert len(results) == 1
        assert results[0] == {"test": "data"}

    async def test_multiple_failing_handlers_dont_block_working(self):
        """Test that multiple failing handlers don't block working ones."""
        results = []

        async def failing_handler1(data):
            raise RuntimeError("Error 1")

        async def failing_handler2(data):
            raise RuntimeError("Error 2")

        async def working_handler(data):
            results.append(data)

        event_bus.subscribe("test.multi_error", failing_handler1)
        event_bus.subscribe("test.multi_error", failing_handler2)
        event_bus.subscribe("test.multi_error", working_handler)

        # Should not raise exception
        await event_bus.publish("test.multi_error", {"value": 99})

        # Working handler should execute
        assert len(results) == 1
        assert results[0] == {"value": 99}

    async def test_all_handlers_execute_despite_errors(self):
        """Test that all handlers execute even if some fail."""
        execution_order = []

        async def handler1(data):
            execution_order.append(1)
            raise ValueError("Error in handler1")

        async def handler2(data):
            execution_order.append(2)

        async def handler3(data):
            execution_order.append(3)
            raise RuntimeError("Error in handler3")

        event_bus.subscribe("test.all_execute", handler1)
        event_bus.subscribe("test.all_execute", handler2)
        event_bus.subscribe("test.all_execute", handler3)

        await event_bus.publish("test.all_execute", {})

        # All handlers should have executed
        assert len(execution_order) == 3
        assert 1 in execution_order
        assert 2 in execution_order
        assert 3 in execution_order


@pytest.mark.asyncio
class TestEventBusAsync:
    """Test async handler execution."""

    async def test_async_handler_with_await(self):
        """Test that async handlers with await work correctly."""
        results = []

        async def async_handler(data):
            await asyncio.sleep(0.01)  # Simulate async work
            results.append(data)

        event_bus.subscribe("test.async", async_handler)
        await event_bus.publish("test.async", {"async": True})

        assert len(results) == 1
        assert results[0] == {"async": True}

    async def test_multiple_async_handlers_concurrent(self):
        """Test that multiple async handlers run concurrently."""
        execution_times = []

        async def handler1(data):
            execution_times.append(("start", 1))
            await asyncio.sleep(0.02)
            execution_times.append(("end", 1))

        async def handler2(data):
            execution_times.append(("start", 2))
            await asyncio.sleep(0.02)
            execution_times.append(("end", 2))

        event_bus.subscribe("test.concurrent", handler1)
        event_bus.subscribe("test.concurrent", handler2)

        await event_bus.publish("test.concurrent", {})

        # Both handlers should have started before either finished
        # (if they ran sequentially, handler1 would finish before handler2 starts)
        assert execution_times[0][0] == "start"
        assert execution_times[1][0] == "start"


@pytest.mark.asyncio
class TestEventBusCleanup:
    """Test event bus cleanup between tests."""

    async def test_handlers_cleared_between_tests(self):
        """Test that handlers are cleared for clean state."""
        # This test verifies that previous test handlers don't interfere
        results = []

        async def handler(data):
            results.append(data)

        event_bus.subscribe("test.cleanup", handler)
        await event_bus.publish("test.cleanup", {"test": 1})

        assert len(results) == 1


@pytest.mark.asyncio
class TestEventBusDomainEvents:
    """Test domain event names and data structures."""

    async def test_torrent_state_changed_event(self):
        """Test torrent.state_changed event structure."""
        results = []

        async def handler(data):
            results.append(data)

        event_bus.subscribe("torrent.state_changed", handler)
        event_data = {"torrent_id": 1, "old_state": "pending", "new_state": "queued"}
        await event_bus.publish("torrent.state_changed", event_data)

        assert results[0] == event_data

    async def test_torrent_completed_event(self):
        """Test torrent.completed event structure."""
        results = []

        async def handler(data):
            results.append(data)

        event_bus.subscribe("torrent.completed", handler)
        event_data = {"torrent_id": 42}
        await event_bus.publish("torrent.completed", event_data)

        assert results[0] == event_data

    async def test_torrent_renamed_event(self):
        """Test torrent.renamed event structure."""
        results = []

        async def handler(data):
            results.append(data)

        event_bus.subscribe("torrent.renamed", handler)
        event_data = {"torrent_id": 5, "file_count": 3}
        await event_bus.publish("torrent.renamed", event_data)

        assert results[0] == event_data

    async def test_torrent_error_event(self):
        """Test torrent.error event structure."""
        results = []

        async def handler(data):
            results.append(data)

        event_bus.subscribe("torrent.error", handler)
        event_data = {"torrent_id": 10, "error_message": "Download failed"}
        await event_bus.publish("torrent.error", event_data)

        assert results[0] == event_data

    async def test_rss_refreshed_event(self):
        """Test rss.refreshed event structure."""
        results = []

        async def handler(data):
            results.append(data)

        event_bus.subscribe("rss.refreshed", handler)
        event_data = {"rss_id": 7, "torrent_count": 15}
        await event_bus.publish("rss.refreshed", event_data)

        assert results[0] == event_data

    async def test_bangumi_created_event(self):
        """Test bangumi.created event structure."""
        results = []

        async def handler(data):
            results.append(data)

        event_bus.subscribe("bangumi.created", handler)
        event_data = {"bangumi_id": 100}
        await event_bus.publish("bangumi.created", event_data)

        assert results[0] == event_data

    async def test_bangumi_deleted_event(self):
        """Test bangumi.deleted event structure."""
        results = []

        async def handler(data):
            results.append(data)

        event_bus.subscribe("bangumi.deleted", handler)
        event_data = {"bangumi_id": 200}
        await event_bus.publish("bangumi.deleted", event_data)

        assert results[0] == event_data


@pytest.fixture(autouse=True)
async def cleanup_event_bus():
    """Clear event bus handlers before each test."""
    event_bus._handlers.clear()
    yield
    event_bus._handlers.clear()
