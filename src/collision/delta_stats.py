"""Delta statistics tracking for collision detection progress."""

import threading
import time


class DeltaStats:
    """Tracks incremental statistics for collision detection.

    Periodically records throughput and key counts for progress
    monitoring and reporting.
    """

    def __init__(
        self,
        window_seconds: int = 60,
    ):
        """Initialize delta stats tracker.

        Args:
            window_seconds: Statistics window in seconds

        """
        self._window = window_seconds
        self._lock = threading.Lock()
        self._start_time = time.time()
        self._last_check = time.time()
        self._last_keys = 0
        self._delta_history: list[float] = []

    def update(
        self,
        total_keys: int,
    ) -> dict:
        """Update stats and compute delta.

        Args:
            total_keys: Current total keys checked

        Returns:
            Delta statistics dictionary

        """
        with self._lock:
            now = time.time()
            elapsed = now - self._last_check
            if elapsed <= 0:
                return {}
            delta_keys = total_keys - self._last_keys
            throughput = delta_keys / elapsed
            self._delta_history.append(throughput)
            if len(self._delta_history) > self._window:
                self._delta_history.pop(0)
            self._last_check = now
            self._last_keys = total_keys
            avg_throughput = (
                sum(self._delta_history) / len(self._delta_history) if self._delta_history else 0
            )
            return {
                "delta_keys": delta_keys,
                "throughput": throughput,
                "avg_throughput": avg_throughput,
                "elapsed": elapsed,
            }

    def reset(self) -> None:
        """Reset all statistics."""
        with self._lock:
            self._start_time = time.time()
            self._last_check = time.time()
            self._last_keys = 0
            self._delta_history.clear()
