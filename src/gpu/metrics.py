"""GPU performance metrics tracking."""
import logging

logger = logging.getLogger(__name__)


def get_metrics_collector():
    """Get the global metrics collector instance."""
    return GPUMetrics()


class GPUMetrics:
    """Tracks GPU performance metrics."""

    def __init__(self):
        self._throughput: list[float] = []
        self._utilization: list[float] = []

    def record_throughput(self, value: float) -> None:
        self._throughput.append(value)
        if len(self._throughput) > 1000:
            self._throughput = self._throughput[-500:]

    def record_utilization(self, value: float) -> None:
        self._utilization.append(value)
        if len(self._utilization) > 1000:
            self._utilization = self._utilization[-500:]

    def average_throughput(self) -> float:
        if not self._throughput:
            return 0.0
        return sum(self._throughput) / len(self._throughput)

    def to_dict(self) -> dict:
        return {"avg_throughput": self.average_throughput(), "samples": len(self._throughput)}
