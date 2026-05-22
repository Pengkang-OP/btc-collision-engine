"""GPU lock contention monitoring utilities."""

import threading
import time

from ..utils import get_configured_logger

logger = get_configured_logger("LockMonitor")


class LockMonitor:
    """Monitors lock contention for debugging thread safety issues."""

    def __init__(self):
        self._lock = threading.Lock()
        self._wait_times: list[float] = []

    def acquire(self, lock: threading.Lock) -> None:
        """Acquire a lock with timing.

        Args:
            lock: Lock to acquire
        """
        start = time.perf_counter()
        lock.acquire()
        elapsed = time.perf_counter() - start
        if elapsed > 0.1:
            with self._lock:
                self._wait_times.append(elapsed)
                logger.warning(
                    f"Lock contention: {elapsed:.3f}s"
                )

    def get_stats(self) -> dict:
        """Get contention statistics.

        Returns:
            Statistics dictionary
        """
        with self._lock:
            if not self._wait_times:
                return {"total_contentions": 0}
            return {
                "total_contentions": len(
                    self._wait_times
                ),
                "max_wait": max(self._wait_times),
                "avg_wait": (
                    sum(self._wait_times)
                    / len(self._wait_times)
                ),
            }
