"""Log storage for persisting log entries."""

import json
from pathlib import Path
from typing import Any


class LogStorage:
    """Persistent log storage."""

    def __init__(
        self,
        storage_dir: str | Path = "logs",
    ):
        """Initialize the log storage."""
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def save(
        self,
        entries: list[dict[str, Any]],
    ) -> None:
        """Save log entries to file.

        Args:
            entries: Log entries to persist

        """
        import time

        filepath = self._storage_dir / f"log_{int(time.time())}.json"
        with Path(filepath).open("w") as f:
            json.dump(entries, f, indent=2)

    def load_all(self) -> list[dict[str, Any]]:
        """Load all stored log entries.

        Returns:
            Aggregated log entries

        """
        entries = []
        for p in sorted(
            self._storage_dir.glob("log_*.json"),
        ):
            with Path(p).open() as f:
                entries.extend(json.load(f))
        return entries

    def get_recent(self, count: int = 100) -> list[dict[str, Any]]:
        """Get the most recent log entries.

        Args:
            count: Maximum number of entries to return

        Returns:
            List of recent log entries (newest first)

        """
        all_entries = self.load_all()
        return all_entries[-count:][::-1]

    def get_by_type(self, event_type: str) -> list[dict[str, Any]]:
        """Get log entries filtered by event type.

        Args:
            event_type: Event type to filter by

        Returns:
            Matching log entries

        """
        all_entries = self.load_all()
        return [e for e in all_entries if e.get("type") == event_type]

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search log entries by keyword.

        Args:
            query: Search keyword

        Returns:
            Matching log entries

        """
        all_entries = self.load_all()
        results = []
        for entry in all_entries:
            entry_str = json.dumps(entry, ensure_ascii=False)
            if query.lower() in entry_str.lower():
                results.append(entry)
        return results

    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics.

        Returns:
            Dictionary with total_count and other stats

        """
        all_entries = self.load_all()
        return {
            "total_count": len(all_entries),
            "file_count": len(list(self._storage_dir.glob("log_*.json"))),
        }
