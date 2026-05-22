"""Monitoring storage configuration."""

from dataclasses import dataclass


@dataclass
class StorageConfig:
    """Configuration for monitoring data storage."""
    enabled: bool = True
    max_size_mb: int = 100
    retention_days: int = 7
    output_dir: str = "data_logs"
