"""Optimization CLI commands and options."""
import logging

logger = logging.getLogger(__name__)


class OptimizationCLI:
    """Optimization-related CLI commands."""

    @staticmethod
    def add_arguments(parser) -> None:
        """Add optimization arguments to parser.

        Args:
            parser: Argument parser
        """
        parser.add_argument(
            "--optimize",
            action="store_true",
            help="Enable auto-optimization",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100000,
            help="Keys per batch",
        )
