"""Integration between logging and monitoring systems."""
import logging

logger = logging.getLogger(__name__)


class LogMonitoringIntegrator:
    """Integrates log events with the monitoring system."""

    def __init__(self):
        self._alert_system = None
        logger.info(
            "Log-monitoring integrator initialized"
        )

    def integrate(
        self, log_entry: dict
    ) -> None:
        """Process a log entry through monitoring.

        Args:
            log_entry: Log entry to process
        """
        level = log_entry.get("level", "INFO")
        if level in ("ERROR", "CRITICAL"):
            if self._alert_system:
                self._alert_system.trigger(
                    log_entry.get("message", ""),
                    log_entry.get("source", ""),
                )

    def set_alert_system(self, alert_system) -> None:
        """Set alert system reference.

        Args:
            alert_system: Alert system instance
        """
        self._alert_system = alert_system
