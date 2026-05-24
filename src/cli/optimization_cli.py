"""Auto-tuning and batch-size optimization for CLI.

Provides runtime auto-tuning of batch sizes and worker counts
based on system resource detection. Used by the performance tuning
group in arg_parser.py.
"""

import logging
import os

logger = logging.getLogger(__name__)


class OptimizationCLI:
    """Optimization-related CLI configuration and auto-tuning.

    Integrated into arg_parser.py's performance tuning group.
    When --auto-tune is specified, this class adjusts batch sizes
    and worker counts based on available system resources.
    """

    @staticmethod
    def add_arguments(parser) -> None:
        """Add auto-tuning arguments to parser.

        Args:
            parser: Argument parser

        """
        parser.add_argument(
            "--auto-tune",
            action="store_true",
            default=False,
            help="启用运行时自动调优：根据系统资源自动调整 batch_size 和 workers",
        )
        parser.add_argument(
            "--batch-size",
            metavar="N",
            type=int,
            default=100000,
            help="CPU 模式下每批处理的私钥数 (默认: 100000)",
        )

    @staticmethod
    def auto_tune(args) -> dict:
        """Auto-tune batch size and workers based on system resources.

        Args:
            args: Parsed CLI arguments

        Returns:
            Dict with tuned 'workers' and 'batch_size' recommendations

        """
        cpu_count = os.cpu_count() or 4
        recommendations = {}

        # Worker count: default to half of logical cores
        current_workers = getattr(args, "workers", None)
        if current_workers is None:
            recommendations["workers"] = max(2, cpu_count // 2)

        # Batch size tuning based on CPU cores
        base_batch = getattr(args, "batch_size", 100000)
        # Scale batch size with core count (more cores = bigger batches)
        tuned_batch = base_batch * max(1, cpu_count // 4)
        recommendations["batch_size"] = tuned_batch

        logger.info(
            "Auto-tune: workers=%s, batch_size=%s (CPU cores: %s)",
            recommendations.get("workers", current_workers),
            recommendations["batch_size"],
            cpu_count,
        )
        return recommendations
