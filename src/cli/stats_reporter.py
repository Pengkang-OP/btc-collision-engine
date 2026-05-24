"""Statistics reporting utilities for CLI."""
import json
import time
from typing import Any

from ..utils import get_configured_logger

logger = get_configured_logger("StatsReporter")


def _print_final_summary(engine: Any, engine_type: str, args: Any) -> None:
    """Print final collision statistics summary after engine stops.

    Args:
        engine: The collision engine instance
        engine_type: Engine type label (e.g. 'GPU', 'CPU')
        args: Parsed CLI arguments
    """
    print()
    print("=" * 64)
    print(f"  BTC Collision Engine - 运行结束 ({engine_type})")
    print("=" * 64)

    try:
        stats = engine.get_stats()
        if stats:
            print(f"  总检查私钥:    {stats.get('total_checked', 0):,}")
            print(f"  平均速度:      {stats.get('avg_speed', stats.get('speed', 0)):,.0f} keys/s")
            print(f"  命中次数:      {stats.get('matches_found', 0)}")
            elapsed = stats.get('elapsed', 0)
            if elapsed > 0:
                print(f"  运行时长:      {elapsed:.1f}s")
        else:
            print("  (无法获取统计信息)")
    except Exception as e:
        logger.debug("Failed to get final stats: %s", e)
        print("  (统计信息获取失败)")

    print("=" * 64)
    print()


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
