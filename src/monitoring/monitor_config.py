"""Monitoring system configuration models."""
from dataclasses import dataclass, field


@dataclass
class MonitorConfig:
    """Configuration for monitoring system."""

    enabled: bool = True
    metrics_enabled: bool = True
    alerts_enabled: bool = True
    log_enabled: bool = True
    sample_interval: float = 1.0
    collection_interval: int = 5  # Alias for monitoring collection interval
    enable_monitoring_data: bool = True
    history_size: int = 3600
    alert_threshold: float = 0.8
    alert_cooldown: int = 300
    notification_channels: list[str] = field(
        default_factory=lambda: ["console", "log"],
    )
