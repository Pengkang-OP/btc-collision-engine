#!/usr/bin/env python3
"""
Dependency injection container.

Provides centralized management of component instances and
dependencies for the collision engine.
"""

from ..utils import get_configured_logger

logger = get_configured_logger("DependencyContainer")


class DependencyContainer:
    """
    Dependency injection container.

    Manages singleton instances of core components, providing lazy
    initialization and centralized lifecycle management.
    """

    def __init__(self):
        self._instances = {}
        self._logger = get_configured_logger(
            "DependencyContainer"
        )

    def register(self, key: str, instance) -> None:
        """Register a component instance.

        Args:
            key: Component identifier
            instance: Component instance
        """
        self._instances[key] = instance
        self._logger.debug(
            f"Registered component: {key}"
        )

    def get(self, key: str):
        """Get a component instance.

        Args:
            key: Component identifier

        Returns:
            Component instance or None
        """
        return self._instances.get(key)

    def has(self, key: str) -> bool:
        """Check if component is registered.

        Args:
            key: Component identifier

        Returns:
            True if registered
        """
        return key in self._instances

    def remove(self, key: str) -> None:
        """Remove a component instance.

        Args:
            key: Component identifier
        """
        self._instances.pop(key, None)
        self._logger.debug(
            f"Removed component: {key}"
        )

    def clear(self) -> None:
        """Clear all registered components."""
        self._instances.clear()
        self._logger.debug("All components cleared")
