#!/usr/bin/env python3
"""
Plugin manager for collision strategy plugins.

Handles plugin discovery, loading, lifecycle management, and
event routing.
"""

from ..utils import get_configured_logger

logger = get_configured_logger("PluginManager")


class PluginManager:
    """Manages collision strategy plugins."""

    def __init__(self):
        self._plugins = {}

    def register(self, plugin) -> None:
        """Register and initialize a plugin.

        Args:
            plugin: Plugin instance
        """
        self._plugins[plugin.name] = plugin
        logger.info(
            f"Plugin registered: {plugin.name}"
        )

    def get(self, name: str):
        """Get plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None
        """
        return self._plugins.get(name)

    def initialize_all(self, engine) -> None:
        """Initialize all registered plugins.

        Args:
            engine: Collision engine instance
        """
        for name, plugin in self._plugins.items():
            try:
                plugin.initialize(engine)
            except Exception as e:
                logger.error(
                    f"Failed to initialize plugin "
                    f"'{name}': {e}"
                )

    def cleanup_all(self) -> None:
        """Cleanup all plugins."""
        for name, plugin in self._plugins.items():
            try:
                plugin.cleanup()
            except Exception as e:
                logger.error(
                    f"Failed to cleanup plugin "
                    f"'{name}': {e}"
                )
