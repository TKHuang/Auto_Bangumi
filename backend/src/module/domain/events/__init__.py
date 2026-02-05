"""Domain events - event-driven architecture."""

from module.domain.events.bus import EventBus, event_bus

__all__ = ["EventBus", "event_bus"]
