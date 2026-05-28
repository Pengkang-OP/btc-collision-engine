"""Integration between logging and monitoring systems."""

from typing import Any

from ..utils import get_configured_logger

__all__ = ["LogMonitoringIntegrator", "get_log_monitoring_integrator"]


logger = get_configured_logger(__name__)


class LogMonitoringIntegrator:
    """Integrates log events with the monitoring system."""

    def __init__(self) -> None:
        """Initialize the log-monitoring integrator."""
        self._alert_system = None
        logger.info(
            "Log-monitoring integrator initialized",
        )

    def integrate(
        self,
        log_entry: dict,
    ) -> None:
        """Process a log entry through monitoring.

        Args:
            log_entry: Log entry to process

        """
        level = log_entry.get("level", "INFO")
        if level in ("ERROR", "CRITICAL") and self._alert_system:
            self._alert_system.trigger(
                log_entry.get("message", ""),
                log_entry.get("source", ""),
            )

    def integrate_with_monitoring_system(self, monitoring_system: Any) -> None:
        """Integrate with a monitoring system (connect alert system, hooks, etc.).

        Args:
            monitoring_system: The monitoring system instance to integrate with.

        """
        if hasattr(monitoring_system, "alert_system"):
            self.set_alert_system(monitoring_system.alert_system)

    def set_alert_system(self, alert_system: Any) -> None:
        """Set alert system reference.

        Args:
            alert_system: Alert system instance

        """
        self._alert_system = alert_system


# Global integrator instance (lazy-initialized singleton)
_integrator: LogMonitoringIntegrator | None = None


def get_log_monitoring_integrator() -> LogMonitoringIntegrator:
    """Get or create the global log-monitoring integrator instance.

    Returns:
        Global LogMonitoringIntegrator singleton.

    """
    global _integrator
    if _integrator is None:
        _integrator = LogMonitoringIntegrator()
    return _integrator
