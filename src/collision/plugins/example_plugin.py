#!/usr/bin/env python3
"""
Example collision strategy plugin.
"""

from ..utils import get_configured_logger
from .base_plugin import BaseCollisionPlugin

logger = get_configured_logger("ExamplePlugin")


class ExamplePlugin(BaseCollisionPlugin):
    """Example collision strategy plugin for demonstration."""

    @property
    def name(self) -> str:
        return "example"

    def initialize(self, engine) -> None:
        """Initialize the plugin."""
        self.engine = engine
        logger.info("Example plugin initialized")
