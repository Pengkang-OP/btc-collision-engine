"""Log query engine for searching log entries."""

import re
from typing import Any


class LogQuery:
    """Query filter for log entries."""

    @staticmethod
    def filter_by_level(
        entries: list[dict[str, Any]],
        min_level: str,
    ) -> list[dict[str, Any]]:
        """Filter entries by minimum log level.

        Args:
            entries: Log entries
            min_level: Minimum level (DEBUG, INFO, WARNING, ERROR)

        Returns:
            Filtered entries

        """
        levels = {
            "DEBUG": 10,
            "INFO": 20,
            "WARNING": 30,
            "ERROR": 40,
        }
        min_val = levels.get(min_level.upper(), 0)
        return [
            e
            for e in entries
            if levels.get(
                e.get("level", "INFO").upper(),
                20,
            )
            >= min_val
        ]

    @staticmethod
    def search_text(
        entries: list[dict[str, Any]],
        text: str,
    ) -> list[dict[str, Any]]:
        """Search entries containing text.

        Args:
            entries: Log entries
            text: Search text

        Returns:
            Matching entries

        """
        pattern = re.compile(
            re.escape(text),
            re.IGNORECASE,
        )
        return [e for e in entries if pattern.search(e.get("message", ""))]
