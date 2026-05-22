"""Search mode coordinator for GPU operations."""
import logging

logger = logging.getLogger(__name__)


class SearchModeCoordinator:
    """Coordinates between different GPU search modes."""

    def __init__(self):
        self._current_mode = "random"
        self._performance_scores: dict[
            str, float
        ] = {}
        logger.info(
            "Search mode coordinator initialized"
        )

    def set_mode(self, mode: str) -> None:
        """Set active search mode.

        Args:
            mode: Search mode name
        """
        self._current_mode = mode
        logger.info(f"Search mode set to: {mode}")

    def record_performance(
        self, mode: str, score: float
    ) -> None:
        """Record performance score for a mode.

        Args:
            mode: Search mode name
            score: Performance score
        """
        self._performance_scores[mode] = score

    def best_mode(self) -> str:
        """Get best performing mode.

        Returns:
            Best mode name or current
        """
        if not self._performance_scores:
            return self._current_mode
        return max(
            self._performance_scores,
            key=self._performance_scores.get,
        )
