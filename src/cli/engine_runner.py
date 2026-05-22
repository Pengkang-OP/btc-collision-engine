"""Engine runner for executing collision detection."""
import signal
import time

from ..utils import get_configured_logger

logger = get_configured_logger("EngineRunner")


class EngineRunner:
    """Runs collision detection with proper lifecycle management."""

    def __init__(self, engine):
        self._engine = engine
        self._running = False
        self._stop_requested = False

    def run(self) -> dict:
        """Run collision detection.

        Returns:
            Final statistics dictionary
        """
        self._running = True
        self._engine.start()
        logger.info("Engine started")
        while self._running and not self._stop_requested:
            time.sleep(1)
            stats = self._engine.get_stats()
            if stats.get("total_matches", 0) > 0:
                break
        self._engine.stop()
        return self._engine.get_stats()

    def stop(self) -> None:
        """Request graceful stop."""
        self._stop_requested = True
        self._running = False
