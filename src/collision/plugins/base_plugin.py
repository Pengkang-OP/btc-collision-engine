#!/usr/bin/env python3
"""
Base class for collision strategy plugins.

Defines the plugin interface for extending collision detection
strategies.
"""

from abc import ABC, abstractmethod


class BaseCollisionPlugin(ABC):
    """Abstract base class for collision strategy plugins.

    All plugins must implement :meth:`name` and :meth:`initialize`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name (unique identifier)."""

    @abstractmethod
    def initialize(self, engine) -> None:
        """Initialize plugin with engine reference.

        Args:
            engine: Collision engine instance
        """

    def cleanup(self) -> None:
        """Cleanup resources before plugin removal."""
