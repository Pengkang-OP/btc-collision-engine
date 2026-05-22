"""Configuration loader for CLI."""
import json
from pathlib import Path

from ..utils import get_configured_logger

logger = get_configured_logger("ConfigLoader")


class ConfigLoader:
    """Loads and validates configuration files."""

    def load(
        self, filepath: str | Path
    ) -> dict:
        """Load configuration from JSON file.

        Args:
            filepath: Path to config file

        Returns:
            Configuration dictionary
        """
        path = Path(filepath)
        if not path.exists():
            logger.error(
                f"Config file not found: {path}"
            )
            return {}
        with open(path) as f:
            return json.load(f)

    def merge(
        self,
        base: dict,
        override: dict,
    ) -> dict:
        """Merge configurations, override taking precedence.

        Args:
            base: Base configuration
            override: Override configuration

        Returns:
            Merged configuration
        """
        result = dict(base)
        result.update(override)
        return result
