"""Configuration loader for CLI."""

import json
from pathlib import Path
from typing import Any

from ..config.config_manager import ConfigManager
from ..utils import get_configured_logger

logger = get_configured_logger("ConfigLoader")


def load_config_with_validation(config_file: str | None = None) -> dict[str, Any] | None:
    """Load and validate configuration from JSON file.

    Uses ConfigManager for proper validation, comment stripping, and merging.

    Args:
        config_file: Path to config JSON file. If None, uses default.

    Returns:
        Validated config dict, or None if loading/validation fails.

    """
    mgr = ConfigManager(config_file=config_file)
    # ConfigManager.__init__ already calls load_config() if file exists
    # Access .config property to trigger lazy initialization with defaults
    config = mgr.config
    if config_file and not Path(config_file).exists():
        logger.warning("Config file not found: %s, using defaults", config_file)
    return config


class ConfigLoader:
    """Legacy config loader — prefer load_config_with_validation() using ConfigManager.

    Kept for backward compatibility with external scripts.
    """

    def load(
        self,
        filepath: str | Path,
    ) -> dict[str, Any]:
        """Load configuration from JSON file.

        Args:
            filepath: Path to config file

        Returns:
            Configuration dictionary

        """
        path = Path(filepath)
        if not path.exists():
            logger.error("Config file not found: %s", path)
            return {}
        with Path(path).open() as f:
            return json.load(f)  # type: ignore[no-any-return]

    def merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Merge configurations, override taking precedence."""
        result = dict(base)
        result.update(override)
        return result
