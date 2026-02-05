"""
In-process async event bus for domain events.

Provides subscribe/publish pattern with error isolation.
All handlers are async and run concurrently via asyncio.gather.
Errors in one handler don't block others.
"""

import asyncio
from typing import Any, Callable, Awaitable


class EventBus:
    """In-process async event bus with error isolation."""

    def __init__(self):
        self._handlers: dict[str, list[Callable[[Any], Awaitable[None]]]] = {}

    def subscribe(self, event_name: str, handler: Callable[[Any], Awaitable[None]]) -> None:
        """
        Register async handler for event.

        Args:
            event_name: Event name (e.g., 'torrent.completed')
            handler: Async callable that receives event data
        """
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(handler)

    async def publish(self, event_name: str, data: Any) -> None:
        """
        Fire all handlers for event.

        Handlers run concurrently. Errors in one handler don't block others.

        Args:
            event_name: Event name
            data: Event data passed to handlers
        """
        handlers = self._handlers.get(event_name, [])
        if not handlers:
            return

        tasks = [handler(data) for handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)


event_bus = EventBus()
