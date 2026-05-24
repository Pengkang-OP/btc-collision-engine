"""Log collector for aggregating log entries."""

import logging
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)


class LogCollector:
    """Collects and aggregates log entries."""

    def __init__(self):
        self._lock = threading.Lock()
        self._entries: list[dict] = []
        self._handlers: list[Callable] = []

    def add_entry(self, entry: dict) -> None:
        """Add a log entry.

        Args:
            entry: Log entry dictionary

        """
        with self._lock:
            self._entries.append(entry)
        for handler in self._handlers:
            try:
                handler(entry)
            except Exception as e:
                logger.error("Log handler error: %s", e)

    def get_entries(
        self,
        limit: int = 100,
    ) -> list[dict]:
        """Get recent log entries.

        Args:
            limit: Max entries to return

        Returns:
            List of log entries

        """
        with self._lock:
            return self._entries[-limit:]

    def clear(self) -> None:
        """Clear collected entries."""
        with self._lock:
            self._entries.clear()
