"""GPU engine performance monitor."""
import logging
import time

logger = logging.getLogger(__name__)


class GPUEngineMonitor:
    """Monitors GPU engine performance metrics."""

    def __init__(self):
        self._start_time = time.time()
        self._total_keys = 0
        logger.info("GPU engine monitor initialized")

    def record_keys(
        self, count: int
    ) -> None:
        """Record keys processed.

        Args:
            count: Number of keys
        """
        self._total_keys += count

    def get_throughput(self) -> float:
        """Get current throughput.

        Returns:
            Keys per second
        """
        elapsed = max(
            time.time() - self._start_time, 0.001
        )
        return self._total_keys / elapsed
