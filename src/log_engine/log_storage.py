"""Log storage for persisting log entries."""
import json
from pathlib import Path


class LogStorage:
    """Persistent log storage."""

    def __init__(
        self, storage_dir: str | Path = "logs"
    ):
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(
            parents=True, exist_ok=True
        )

    def save(
        self, entries: list[dict]
    ) -> None:
        """Save log entries to file.

        Args:
            entries: Log entries to persist
        """
        import time

        filepath = (
            self._storage_dir
            / f"log_{int(time.time())}.json"
        )
        with open(filepath, "w") as f:
            json.dump(entries, f, indent=2)

    def load_all(self) -> list[dict]:
        """Load all stored log entries.

        Returns:
            Aggregated log entries
        """
        entries = []
        for p in sorted(
            self._storage_dir.glob("log_*.json")
        ):
            with open(p) as f:
                entries.extend(json.load(f))
        return entries
