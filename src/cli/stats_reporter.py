"""Statistics reporting utilities for CLI."""
import json

from ..utils import get_configured_logger

logger = get_configured_logger("StatsReporter")


class StatsReporter:
    """Formats and outputs collision engine statistics."""

    @staticmethod
    def format_summary(stats: dict) -> str:
        """Format a human-readable summary.

        Args:
            stats: Statistics dictionary

        Returns:
            Formatted summary string
        """
        lines = [
            "=== Collision Detection Summary ===",
            f"Keys checked: {stats.get('total_keys_checked', 0):,}",
            f"Matches found: {stats.get('total_matches', 0)}",
            f"Elapsed time: {stats.get('elapsed_seconds', 0):.1f}s",
            f"Throughput: {stats.get('throughput', 0):.0f} keys/s",
        ]
        return "\n".join(lines)

    @staticmethod
    def format_json(stats: dict) -> str:
        """Format as JSON.

        Args:
            stats: Statistics dictionary

        Returns:
            JSON string
        """
        return json.dumps(stats, indent=2, default=str)
