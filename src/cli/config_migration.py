"""Configuration migration utilities for version upgrades."""
import json
from pathlib import Path

from ..utils import get_configured_logger

logger = get_configured_logger("ConfigMigration")


class ConfigMigrator:
    """Migrates configuration between versions."""

    CURRENT_VERSION = 2

    def migrate(
        self, config: dict
    ) -> dict:
        """Migrate config to latest version.

        Args:
            config: Configuration to migrate

        Returns:
            Migrated configuration
        """
        version = config.get(
            "version", 1
        )
        if version < self.CURRENT_VERSION:
            logger.info(
                f"Migrating config from v{version} "
                f"to v{self.CURRENT_VERSION}"
            )
            if version < 2:
                config = self._v1_to_v2(config)
        return config

    @staticmethod
    def _v1_to_v2(config: dict) -> dict:
        """Migrate from v1 to v2 format.

        Args:
            config: v1 configuration

        Returns:
            v2 configuration
        """
        if "batch_size" not in config:
            config["batch_size"] = 100000
        config["version"] = 2
        return config
