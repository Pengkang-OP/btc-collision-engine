"""Base collision engine providing core collision detection framework.

Supports random and sequential search modes with configurable
targets, workers, and event hooks.
"""

__all__ = [
    "BaseCollisionEngine",
]

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from ..utils import get_configured_logger

logger = get_configured_logger("BaseEngine")


class BaseCollisionEngine(ABC):
    """Abstract base class for collision detection engines.

    Provides common state management, worker coordination, and
    match recording functionality.

    Subclasses must implement: start(), stop(), get_stats()
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the base collision engine."""
        self.config = config or {}
        self._lock = threading.Lock()
        self._running = False
        self._start_time: float | None = None
        self._total_keys_checked = 0
        self._match_callback: Callable[..., Any] | None = None

    @abstractmethod
    def start(self, **kwargs: Any) -> None:
        """Start the collision engine.

        Subclasses may accept additional keyword arguments
        (e.g. mode, resume, max_keys).
        """

    @abstractmethod
    def stop(self) -> None:
        """Stop the collision engine."""

    @abstractmethod
    def get_stats(self) -> Any:
        """Get collision detection statistics.

        Returns:
            Engine-specific statistics object (e.g. CollisionStats).

        """

    def is_running(self) -> bool:
        """Check if engine is running."""
        return self._running
