#!/usr/bin/env python3
"""
Collision detection statistics tracking.
"""

import hashlib
import threading
import time

from ..utils import get_configured_logger

logger = get_configured_logger("CollisionStats")

# 常量定义 - 消除魔法数字 (CODE-3修复)
DEFAULT_PROGRESS_INTERVAL_COUNT = 1000  # 每N次检测触发一次进度回调
DEFAULT_DATA_LOG_SAVE_FREQUENCY = 3  # 每N次记录保存一次数据日志
DEFAULT_ERROR_LOG_INTERVAL_SEC = 5.0  # 错误日志记录间隔（秒）
DEFAULT_CPU_CACHE_INTERVAL_SEC = 1.0  # CPU使用率缓存更新间隔（秒）


class CollisionStats:
    """Tracks and aggregates collision detection statistics."""

    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = time.time()
        self._total_keys = 0
        self._total_matches = 0
        self._total_errors = 0
        self.matches: list = []

    def record_key(self) -> None:
        with self._lock:
            self._total_keys += 1

    def record_keys(self, count: int) -> None:
        with self._lock:
            self._total_keys += count

    def record_match(self) -> None:
        with self._lock:
            self._total_matches += 1

    def add_match(self, pk=None, address=None, *args, **kwargs) -> None:
        """Record a match and add to matches list."""
        self.record_match()
        if pk is not None or address is not None:
            entry = {}
            if address is not None:
                entry["address"] = address
            if pk is not None:
                entry["private_key_hash"] = hashlib.sha256(bytes(pk) if not isinstance(pk, bytes) else pk).hexdigest()[:16]
            self.matches.append(entry)

    def snapshot(self) -> dict:
        """Take a snapshot of current stats.

        Returns:
            Dictionary with current stats
        """
        with self._lock:
            return {
                "total_keys_checked": self._total_keys,
                "total_matches": self._total_matches,
                "total_errors": self._total_errors,
                "elapsed_seconds": max(time.time() - self._start_time, 0.001),
                "throughput": (
                    self._total_keys / max(time.time() - self._start_time, 0.001)
                ),
            }

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

    @property
    def start_time(self) -> float:
        """Get start time."""
        return self._start_time

    @start_time.setter
    def start_time(self, value: float) -> None:
        """Set start time."""
        with self._lock:
            self._start_time = value

    def update(self, total_checked: int = 0, **kwargs) -> None:
        """Update total keys checked.

        Args:
            total_checked: Total number of keys checked
            **kwargs: Additional arguments (total_range, etc.)
        """
        with self._lock:
            if total_checked:
                self._total_keys = total_checked
            elif 'total_range' in kwargs:
                self._total_keys = kwargs['total_range']

    @property
    def total_checked(self) -> int:
        """Get total keys checked."""
        with self._lock:
            return self._total_keys

    @total_checked.setter
    def total_checked(self, value: int) -> None:
        """Set total keys checked."""
        with self._lock:
            self._total_keys = value

    @property
    def matches_found(self) -> int:
        """Get total matches found."""
        with self._lock:
            return self._total_matches

    def reset(self) -> None:
        with self._lock:
            self._total_keys = 0
            self._total_matches = 0
            self._total_errors = 0
            self._start_time = time.time()
