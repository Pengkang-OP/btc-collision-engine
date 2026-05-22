#!/usr/bin/env python3
"""
Base collision engine providing core collision detection framework.

Supports random and sequential search modes with configurable
targets, workers, and event hooks.
"""

import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Callable

from ..utils import get_configured_logger

logger = get_configured_logger("BaseEngine")


class BaseCollisionEngine(ABC):
    """Abstract base class for collision detection engines.

    Provides common state management, worker coordination, and
    match recording functionality.
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._lock = threading.Lock()
        self._running = False
        self._initialized = False
        self._start_time: float | None = None
        self._total_keys_checked = 0
        self._match_callback: (
            Callable | None
        ) = None

    @abstractmethod
    def start(self) -> None:
        """Start the collision engine."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the collision engine."""

    @abstractmethod
    def get_stats(self) -> dict:
        """Get collision detection statistics."""

    def is_running(self) -> bool:
        """Check if engine is running."""
        return self._running
