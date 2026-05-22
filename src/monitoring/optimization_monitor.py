"""Optimization performance monitor."""
import logging

logger = logging.getLogger(__name__)


class OptimizationMonitor:
    """Monitors optimization effectiveness."""

    def __init__(self):
        self._improvements: list[float] = []

    def record_improvement(
        self, factor: float
    ) -> None:
        """Record a performance improvement factor.

        Args:
            factor: Speedup factor vs baseline
        """
        self._improvements.append(factor)

    def average_improvement(self) -> float:
        """Get average improvement factor.

        Returns:
            Average speedup factor
        """
        if not self._improvements:
            return 1.0
        return (
            sum(self._improvements)
            / len(self._improvements)
        )
