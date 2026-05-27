"""Monitoring and alerting package for BTC Collision Engine.

Provides GPU performance monitoring (gpu_performance_monitor), system-level
monitoring (monitoring_system), data logging (data_logger), alert dispatch
(alert_system), and integration between logging and monitoring subsystems.
Supports configurable thresholds, metric storage, and real-time dashboards.
"""

from src import __version__ as __version__  # noqa: F401

__all__ = [
    "alert_system",
    "data_logger",
    "enhanced_monitoring",
    "event_adapters",
    "gpu_performance_monitor",
    "log_monitoring_integrator",
    "monitor_config",
    "monitoring_system",
    "storage_config",
]
