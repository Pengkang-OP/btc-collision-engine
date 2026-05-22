"""Distributed statistics aggregator.

Supports statistics aggregation for large-scale multi-GPU
scenarios."""
import threading


class DistributedStatsAggregator:
    """Aggregates GPU worker statistics."""

    def __init__(self):
        self._lock = threading.Lock()
        self._stats: dict[str, dict] = {}

    def update(
        self, worker_id: str, stats: dict
    ) -> None:
        with self._lock:
            self._stats[worker_id] = stats

    def aggregate(self) -> dict:
        with self._lock:
            total_keys = sum(
                s.get("total_keys", 0)
                for s in self._stats.values()
            )
            total_matches = sum(
                s.get("total_matches", 0)
                for s in self._stats.values()
            )
            return {
                "workers": len(self._stats),
                "total_keys": total_keys,
                "total_matches": total_matches,
            }
