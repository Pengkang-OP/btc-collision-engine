#!/usr/bin/env python3
"""
Device manager adapter for GPU device management.
"""

from ...utils import get_configured_logger

logger = get_configured_logger("DeviceManagerAdapter")


class DeviceManagerAdapter:
    """Adapts the device manager for GPU collision operations."""

    def __init__(self, config: dict):
        self._config = config
        logger.info("Device manager adapter initialized")
