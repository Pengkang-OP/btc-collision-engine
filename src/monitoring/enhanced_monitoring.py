"""Enhanced monitoring with advanced metrics tracking."""
import logging
import threading
import time

logger = logging.getLogger(__name__)


class EnhancedMonitoringSystem:
    """Enhanced monitoring with detailed metrics tracking.

    Extends basic monitoring with throughput histograms, match rate
    analysis, and resource usage tracking.
    """

    def __init__(self, config: dict | None = None):
        self._config = config or {}
        self._lock = threading.Lock()
        self._metrics: dict[str, list[float]] = {}
        logger.info(
            "Enhanced monitoring system initialized"
        )

    def record_metric(
        self, name: str, value: float
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
        self, name: str
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
