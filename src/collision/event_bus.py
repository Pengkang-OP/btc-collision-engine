#!/usr/bin/env python3
"""Event bus for decoupled communication between components."""

import logging
import threading
from collections.abc import Callable
from contextlib import suppress
from typing import Any

logger = logging.getLogger(__name__)

# Global event bus instance
_event_bus: "EventBus | None" = None
_event_bus_lock = threading.Lock()

# Mapping from EngineEvent subclass to EventType enum (for backward compat)
_EVENT_CLASS_TO_TYPE: dict[type, Any] = {}


def _build_event_class_map() -> None:
    """Build the event-class-to-EventType mapping once."""
    if _EVENT_CLASS_TO_TYPE:
        return
    from .events import (  # noqa: PLC0415
        EngineCompleteEvent,
        EngineErrorEvent,
        EngineMatchEvent,
        EngineProgressEvent,
        EngineStartEvent,
        EngineStateEvent,
        EngineStopEvent,
        EventType,
    )
    _EVENT_CLASS_TO_TYPE.update({
        EngineStartEvent: EventType.ENGINE_START,
        EngineStopEvent: EventType.ENGINE_STOP,
        EngineCompleteEvent: EventType.ENGINE_COMPLETE,
        EngineMatchEvent: EventType.ENGINE_MATCH,
        EngineErrorEvent: EventType.ENGINE_ERROR,
        EngineProgressEvent: EventType.ENGINE_PROGRESS,
        EngineStateEvent: EventType.ENGINE_STATE,
    })


class EventBus:
    """Simple event bus for publish-subscribe communication.

    Allows decoupled communication between engine components via
    typed events with handler registration and asynchronous dispatch.

    Supports both string/enum-keyed subscriptions (legacy) and
    type-keyed subscriptions (current).
    """

    def __init__(self, async_mode: bool = False):  # noqa: FBT001
        self._lock = threading.Lock()
        self._subscribers: dict[
            Any,
            list[Callable],
        ] = {}
        self._async_mode = async_mode
        self.published_count: int = 0
        self.error_count: int = 0

    def subscribe(
        self,
        event_type: Any,
        handler: Callable,
    ) -> None:
        """Subscribe a handler to an event type.

        Args:
            event_type: Event class, enum value, or string key
            handler: Callable(event) -> None

        """
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)
            name = getattr(event_type, "__name__", str(event_type))
            logger.debug(f"Subscribed {handler.__name__} to {name}")

    def unsubscribe(
        self,
        event_type: Any,
        handler: Callable,
    ) -> None:
        """Unsubscribe a handler.

        Args:
            event_type: Event class, enum value, or string key
            handler: Previously registered handler

        """
        with self._lock:
            if event_type in self._subscribers:
                with suppress(ValueError):
                    self._subscribers[event_type].remove(handler)

    def publish(self, event: Any) -> None:
        """Publish an event to all subscribers.

        Args:
            event: Event instance (or None, which is silently ignored)

        """
        if event is None:
            return

        # Skip events with explicit event_type=None
        evt_type = getattr(event, "event_type", ...)
        if evt_type is None:
            return

        # Collect handlers: type-based + enum/string-keyed
        handlers: list[Callable] = []
        with self._lock:
            # Type-based lookup
            handlers.extend(list(self._subscribers.get(type(event), [])))
            # Enum/string-keyed lookup via event_type attribute or class mapping
            if evt_type is ...:  # no event_type attribute at all → try class map
                _build_event_class_map()
                evt_type = _EVENT_CLASS_TO_TYPE.get(type(event))
            if evt_type is not None:
                handlers.extend(list(self._subscribers.get(evt_type, [])))

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                self.error_count += 1
                logger.error(
                    f"Event handler {handler.__name__} failed: {e}",
                )
        self.published_count += 1

    def clear(self) -> None:
        """Remove all subscribers."""
        with self._lock:
            self._subscribers.clear()

    def stop(self) -> None:
        """Stop the event bus (no-op for backward compatibility)."""
        pass

    def __enter__(self) -> "EventBus":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit – calls stop()."""
        self.stop()


def get_event_bus() -> EventBus:
    """Get the global event bus instance.

    Returns:
        The global EventBus instance

    """
    global _event_bus
    if _event_bus is None:
        with _event_bus_lock:
            if _event_bus is None:
                _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset the global event bus instance (for testing)."""
    global _event_bus
    with _event_bus_lock:
        _event_bus = None
