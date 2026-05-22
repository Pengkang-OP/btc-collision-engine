#!/usr/bin/env python3
"""
Collision detection statistics tracking.
"""

import threading
import time

from ..utils import get_configured_logger

logger = get_configured_logger("CollisionStats")


class CollisionStats:
    """Tracks and aggregates collision detection statistics."""

    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = time.time()
        self._total_keys = 0
        self._total_matches = 0
        self._total_errors = 0

    def record_key(self) -> None:
        with self._lock:
            self._total_keys += 1

    def record_keys(self, count: int) -> None:
        with self._lock:
            self._total_keys += count

    def record_match(self) -> None:
        with self._lock:
            self._total_matches += 1

    def record_error(self) -> None:
        with self._lock:
            self._total_errors += 1

    def get_throughput(self) -> float:
        elapsed = max(time.time() - self._start_time, 0.001)
        return self._total_keys / elapsed

    def to_dict(self) -> dict:
        with self._lock:
            elapsed = max(
                time.time() - self._start_time, 0.001
            )
            return {
                "total_keys_checked": self._total_keys,
                "total_matches": self._total_matches,
                "total_errors": self._total_errors,
                "elapsed_seconds": elapsed,
                "throughput": (
                    self._total_keys / elapsed
                ),
            }

    def reset(self) -> None:
        with self._lock:
            self._total_keys = 0
            self._total_matches = 0
            self._total_errors = 0
            self._start_time = time.time()
