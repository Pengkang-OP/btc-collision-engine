#!/usr/bin/env python3
"""Collision detection statistics tracking."""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from ..utils import get_configured_logger

logger = get_configured_logger("CollisionStats")


@dataclass
class StatsSnapshot:
    """Immutable snapshot of collision statistics at a point in time."""

    total_keys_checked: int = 0
    total_matches: int = 0
    total_errors: int = 0
    elapsed_seconds: float = 0.0
    throughput: float = 0.0
    matches: list[dict] = field(default_factory=list)


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
        self._total_batches = 0
        self._total_matches = 0
        self._total_errors = 0
        self.matches: list = []
        # Error counters by category
        self._gpu_errors: int = 0
        self._worker_errors: int = 0
        self._resource_errors: int = 0
        self._total_range: int = 0

    def record_key(self) -> None:
        with self._lock:
            self._total_keys += 1

    def record_keys(self, count: int) -> None:
        with self._lock:
            self._total_keys += count

    def increment(self, delta: int) -> None:
        """Increment total keys checked by delta.

        Args:
            delta: Non-negative integer to add to total_checked

        Raises:
            ValueError: If delta is negative
            TypeError: If delta is not an int
        """
        if not isinstance(delta, int):
            raise TypeError(f"delta must be an int, got {type(delta).__name__}")
        if delta < 0:
            raise ValueError("delta must be non-negative")
        with self._lock:
            self._total_keys += delta

    def set_total_batches(self, batch_num: int) -> None:
        """Set total batch count (called by GPU search modes).

        Args:
            batch_num: Current batch number to record
        """
        with self._lock:
            self._total_batches = batch_num

    @property
    def total_batches(self) -> int:
        """Get total batches processed."""
        with self._lock:
            return self._total_batches

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
                entry["private_key_hash"] = hashlib.sha256(
                    bytes(pk) if not isinstance(pk, bytes) else pk,
                ).hexdigest()[:16]
            self.matches.append(entry)

    def snapshot(self) -> StatsSnapshot:
        """Take a snapshot of current stats.

        Returns:
            StatsSnapshot object with current stats

        """
        with self._lock:
            return StatsSnapshot(
                total_keys_checked=self._total_keys,
                total_matches=self._total_matches,
                total_errors=self._total_errors,
                elapsed_seconds=max(time.time() - self._start_time, 0.001),
                throughput=(self._total_keys / max(time.time() - self._start_time, 0.001)),
                matches=list(self.matches),
            )

    def record_error(self, error_type: str = "", error_msg: str = "") -> None:
        """Record a general error with optional type/message."""
        with self._lock:
            self._total_errors += 1

    def record_gpu_error(self, is_resource_error: bool = False) -> None:
        """Record a GPU error, optionally classifying as resource error.

        Called by ExceptionHandler.handle_gpu_error() via getattr.
        """
        with self._lock:
            self._gpu_errors += 1
            if is_resource_error:
                self._resource_errors += 1

    def record_worker_error(self) -> None:
        """Record a worker engine error.

        Called by ExceptionHandler.handle_engine_error() via getattr.
        """
        with self._lock:
            self._worker_errors += 1

    def get_throughput(self) -> float:
        elapsed = max(time.time() - self._start_time, 0.001)
        return self._total_keys / elapsed

    def to_dict(self) -> dict:
        with self._lock:
            elapsed = max(
                time.time() - self._start_time,
                0.001,
            )
            return {
                "total_keys_checked": self._total_keys,
                "total_matches": self._total_matches,
                "total_errors": self._total_errors,
                "elapsed_seconds": elapsed,
                "throughput": (self._total_keys / elapsed),
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
            elif "total_range" in kwargs:
                self._total_keys = kwargs["total_range"]
            if "total_range" in kwargs:
                self._total_range = kwargs["total_range"]

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
    def total_keys(self) -> int:
        """Get total keys (alias for total_checked for engine_monitor compatibility)."""
        with self._lock:
            return self._total_keys

    @total_keys.setter
    def total_keys(self, value: int) -> None:
        """Set total keys (alias for total_checked for engine_monitor compatibility)."""
        with self._lock:
            self._total_keys = value

    @property
    def matches_found(self) -> int:
        """Get total matches found."""
        with self._lock:
            return self._total_matches

    @property
    def gpu_errors(self) -> int:
        """Get GPU error count."""
        with self._lock:
            return self._gpu_errors

    @gpu_errors.setter
    def gpu_errors(self, value: int) -> None:
        """Set GPU error count."""
        with self._lock:
            self._gpu_errors = value

    @property
    def worker_errors(self) -> int:
        """Get worker error count."""
        with self._lock:
            return self._worker_errors

    @worker_errors.setter
    def worker_errors(self, value: int) -> None:
        """Set worker error count."""
        with self._lock:
            self._worker_errors = value

    @property
    def resource_errors(self) -> int:
        """Get resource error count."""
        with self._lock:
            return self._resource_errors

    @resource_errors.setter
    def resource_errors(self, value: int) -> None:
        """Set resource error count."""
        with self._lock:
            self._resource_errors = value

    @property
    def avg_speed(self) -> float:
        """Get average speed (keys per second)."""
        return self.get_throughput()

    @property
    def speed(self) -> float:
        """Alias for avg_speed for backward compatibility."""
        return self.avg_speed

    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds since start_time."""
        return max(time.time() - self._start_time, 0.0)

    @property
    def _match_count(self) -> int:
        """Backward-compatible accessor for match count (internal)."""
        with self._lock:
            return self._total_matches

    @property
    def eta_seconds(self) -> float:
        """Estimated time to completion in seconds.

        Returns:
            -1.0 if total_range is not set or is 0 (infinite),
            0.0 if remaining work <= 0,
            otherwise remaining / throughput.
        """
        throughput = self.avg_speed
        remaining = self._total_range - self._total_keys
        if self._total_range <= 0:
            return -1.0
        if remaining <= 0:
            return 0.0
        if throughput <= 0:
            return float("inf")
        return remaining / throughput

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like access for backward compatibility with stats consumers.

        Supported keys:
            - total_checked: total keys checked
            - speed: average throughput (keys/sec)
            - matches_found: total matches detected
            - elapsed: elapsed time in seconds
        """
        mapping = {
            "total_checked": self.total_checked,
            "speed": self.avg_speed,
            "matches_found": self.matches_found,
            "elapsed": max(time.time() - self._start_time, 0.001),
        }
        return mapping.get(key, default)

    def reset(self) -> None:
        with self._lock:
            self._total_keys = 0
            self._total_matches = 0
            self._total_errors = 0
            self._start_time = time.time()

    def format_elapsed(self) -> str:
        """Format elapsed time as human-readable string.

        Returns:
            Formatted string like "1h 2m 3s" or "45.2s"

        """
        elapsed = max(time.time() - self._start_time, 0.0)
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = elapsed % 60
        if hours > 0:
            return f"{hours}h {minutes}m {seconds:.1f}s"
        elif minutes > 0:
            return f"{minutes}m {seconds:.1f}s"
        else:
            return f"{seconds:.1f}s"

    def format_speed(self) -> str:
        """Format average speed as human-readable string.

        Returns:
            Formatted string like "5,721 keys/s"

        """
        speed = self.avg_speed
        if speed >= 1_000_000:
            return f"{speed / 1_000_000:.2f}M keys/s"
        elif speed >= 1_000:
            return f"{speed:,.0f} keys/s"
        else:
            return f"{speed:.1f} keys/s"
