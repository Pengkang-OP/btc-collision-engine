"""Monitoring storage configuration."""

import pathlib
from dataclasses import dataclass


class DataStorageConfig:
    """Data storage configuration for monitoring system."""

    def __init__(
        self,
        enabled: bool = True,
        max_size_mb: int = 100,
        retention_days: int = 7,
        output_dir: str = "data_logs",
    ):
        self.enabled = enabled
        self.max_size_mb = max_size_mb
        self.retention_days = retention_days
        self.output_dir = output_dir

    @staticmethod
    def ensure_storage_dir(storage_dir: str | None = None) -> str:
        """Ensure the storage directory exists.

        Args:
            storage_dir: Optional custom storage directory

        Returns:
            Path to the storage directory

        """
        dir_path = storage_dir or "data_logs"
        pathlib.Path(dir_path).mkdir(exist_ok=True, parents=True)
        return dir_path


@dataclass
class StorageConfig:
    """Configuration for monitoring data storage."""

    enabled: bool = True
    max_size_mb: int = 100
    retention_days: int = 7
    output_dir: str = "data_logs"
