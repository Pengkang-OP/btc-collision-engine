#!/usr/bin/env python3
"""Target address monitor for tracking resolution status."""

from ...utils import get_configured_logger

logger = get_configured_logger("TargetMonitor")


class TargetMonitor:
    """Monitors target address resolution and validation status."""

    def __init__(self):
        self._resolved: int = 0
        self._failed: int = 0
        self._total: int = 0

    def record_resolved(self) -> None:
        self._resolved += 1

    def record_failed(self) -> None:
        self._failed += 1

    @property
    def resolved_count(self) -> int:
        return self._resolved

    @property
    def failed_count(self) -> int:
        return self._failed

    def reset(self) -> None:
        self._resolved = 0
        self._failed = 0
