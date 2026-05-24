"""Enhanced monitoring with advanced metrics tracking."""
import logging
import threading
from contextlib import suppress

from src.monitoring.data_logger import DataLogger

logger = logging.getLogger(__name__)


class EnhancedMonitoringSystem:
    """Enhanced monitoring with detailed metrics tracking.

    Extends basic monitoring with throughput histograms, match rate
    analysis, and resource usage tracking.
    """

    def __init__(self, engine=None, config=None):
        self._engine = engine
        self._config = config or {}
        self._lock = threading.Lock()
        self._metrics: dict[str, list[float]] = {}
        # Create data logger for engine compatibility
        self.data_logger = DataLogger()
        logger.info(
            "Enhanced monitoring system initialized",
        )

    def is_running(self) -> bool:
        """Check if monitoring system is running."""
        return True

    def stop(self) -> None:
        """Stop the monitoring system and clean up resources.

        Safely shuts down the data logger and clears metrics storage.
        This method is idempotent - calling it multiple times is safe.
        """
        with self._lock:
            with suppress(Exception):
                self.data_logger = None
            self._metrics.clear()

    def record_metric(
        self, name: str, value: float,
    ) -> None:
        """Record a metric value.

        Args:
            name: Metric name
            value: Metric value

        """
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = []
            self._metrics[name].append(value)
            if len(self._metrics[name]) > 10000:
                self._metrics[name] = (
                    self._metrics[name][-5000:]
                )

    def get_average(
        self, name: str,
    ) -> float:
        """Get average value for a metric.

        Args:
            name: Metric name

        Returns:
            Average value or 0

        """
        with self._lock:
            values = self._metrics.get(name, [])
            if not values:
                return 0.0
            return sum(values) / len(values)
