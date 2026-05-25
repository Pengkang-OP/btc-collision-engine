"""Wizard event definitions."""

import contextlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue
from typing import Any, Callable

logger = logging.getLogger(__name__)


class WizardEventType(Enum):
    """Wizard event types."""

    WIZARD_START = "wizard_start"
    WIZARD_COMPLETE = "wizard_complete"
    WIZARD_CANCELLED = "wizard_cancelled"
    WIZARD_ERROR = "wizard_error"
    TARGET_SELECTED = "target_selected"
    MODE_SELECTED = "mode_selected"
    CONFIG_BUILT = "config_built"
    GPU_SELECTED = "gpu_selected"
    OPTION_SELECTED = "option_selected"
    VALIDATION_ERROR = "validation_error"
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"


@dataclass
class WizardEvent:
    """Base wizard event."""

    type: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = "wizard"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source,
        }


class EventDispatcher:
    """Event dispatcher for wizard events."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable]] = {}
        self._event_queue: Queue = Queue()

    def register(self, event_type: str, listener: Callable) -> None:
        """Register a listener for an event type."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(listener)

    def unregister(self, event_type: str, listener: Callable) -> None:
        """Unregister a listener for an event type."""
        if event_type in self._listeners:
            with contextlib.suppress(ValueError):
                self._listeners[event_type].remove(listener)

    def dispatch(self, event: WizardEvent) -> None:
        """Dispatch an event to all registered listeners."""
        self._event_queue.put(event)
        if event.type in self._listeners:
            for listener in self._listeners[event.type]:
                try:
                    listener(event)
                except Exception as e:
                    logger.error("Event dispatch error: %s", e)

    def clear(self) -> None:
        """Clear all listeners."""
        self._listeners.clear()
        while not self._event_queue.empty():
            self._event_queue.get_nowait()
