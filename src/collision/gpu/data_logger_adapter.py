#!/usr/bin/env python3
"""
Data logger adapter for GPU collision metrics recording.
"""

from ...utils import get_configured_logger

logger = get_configured_logger("DataLoggerAdapter")


class DataLoggerAdapter:
    """Adapts the data logging system for GPU collision metrics."""

    def __init__(self, config: dict):
        self._config = config
        logger.info("Data logger adapter initialized")
