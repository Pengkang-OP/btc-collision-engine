#!/usr/bin/env python3
"""
Event bus for decoupled communication between components.
"""

import logging
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class EventBus:
    """
    Simple event bus for publish-subscribe communication.

    Allows decoupled communication between engine components via
    typed events with handler registration and asynchronous dispatch.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: dict[
            type, list[Callable]
        ] = {}

    def subscribe(
        self,
        event_type: type,
        handler: Callable,
    ) -> None:
        """Subscribe a handler to an event type.

        Args:
            event_type: Event class to subscribe to
            handler: Callable(event) -> None
        """
        with self._lock:
            if (
                event_type
                not in self._subscribers
            ):
                self._subscribers[
                    event_type
                ] = []
            self._subscribers[
                event_type
            ].append(handler)
            logger.debug(
                f"Subscribed {handler.__name__} "
                f"to {event_type.__name__}"
            )

    def unsubscribe(
        self,
        event_type: type,
        handler: Callable,
    ) -> None:
        """Unsubscribe a handler.

        Args:
            event_type: Event class
            handler: Previously registered handler
        """
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[
                    event_type
                ].remove(handler)

    def publish(self, event: Any) -> None:
        """Publish an event to all subscribers.

        Args:
            event: Event instance
        """
        handlers = []
        with self._lock:
            handlers = list(
                self._subscribers.get(
                    type(event), []
                )
            )
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    f"Event handler "
                    f"{handler.__name__} "
                    f"failed: {e}"
                )

    def clear(self) -> None:
        """Remove all subscribers."""
        with self._lock:
            self._subscribers.clear()
