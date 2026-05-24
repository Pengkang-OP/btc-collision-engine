"""Performance monitoring configuration."""

from dataclasses import dataclass


@dataclass
class PerformanceConfig:
    """Performance monitoring and tracking configuration."""

    enabled: bool = True
    sample_interval: float = 1.0
    history_size: int = 3600
    alert_threshold: float = 0.8
