"""Log collector for aggregating log entries."""

import logging
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)


class LogCollector:
    """Collects and aggregates log entries."""

    def __init__(self, max_queue_size: int = 1000):
        self._lock = threading.Lock()
        self._max_queue_size = max_queue_size
        self._entries: list[dict] = []
        self._handlers: list[Callable] = []

    def add_entry(self, entry: dict) -> None:
        """Add a log entry.

        Args:
            entry: Log entry dictionary

        """
        with self._lock:
            self._entries.append(entry)
            # Trim if over max queue size
            if len(self._entries) > self._max_queue_size:
                self._entries = self._entries[-self._max_queue_size:]
        for handler in self._handlers:
            try:
                handler(entry)
            except Exception as e:
                logger.error("Log handler error: %s", e)

    def collect_from_queue(self, event_type, data: dict) -> None:
        """Collect an event from a queue (backward compat API).

        Args:
            event_type: LogEventType enum value
            data: Event data dict

        """
        entry = {
            "type": getattr(event_type, "name", str(event_type)),
            "data": data,
        }
        self.add_entry(entry)

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
