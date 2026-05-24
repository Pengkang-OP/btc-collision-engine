"""Statistics and performance monitor CLI integration."""

import logging
import time

logger = logging.getLogger(__name__)


class StatsPerformanceMonitor:
    """Monitors and reports performance statistics."""

    def __init__(self):
        self._start_time = time.time()
        self._last_report = time.time()
        self._total_keys = 0

    def record_keys(
        self,
        count: int,
    ) -> None:
        """Record key processing.

        Args:
            count: Keys processed

        """
        self._total_keys += count

    def get_report(self) -> str:
        """Get performance report.

        Returns:
            Formatted report string

        """
        elapsed = max(
            time.time() - self._start_time,
            0.001,
        )
        throughput = self._total_keys / elapsed
        return f"Keys: {self._total_keys:,} | Rate: {throughput:.0f} keys/s | Time: {elapsed:.1f}s"
