"""Event adapters for monitoring system integration."""

from typing import Any

from ..utils import get_configured_logger

logger = get_configured_logger(__name__)

__all__ = [
    "AlertSystemAdapter",
    "DataLoggerAdapter",
    "EnhancedMonitoringAdapter",
    "EventAdapter",
    "setup_data_logging",
]


class DataLoggerAdapter:
    """Adapter that wraps a DataLogger and subscribes it to events."""

    def __init__(self, data_logger: Any) -> None:
        """Initialize the data logger adapter."""
        self.data_logger = data_logger


def setup_data_logging(event_bus: "Any", data_logger: "Any") -> DataLoggerAdapter:
    """Set up data logging via event bus.

    Args:
        event_bus: Event bus instance
        data_logger: DataLogger instance

    Returns:
        DataLoggerAdapter wrapping the data logger

    """
    # Import event types to avoid circular imports
    from ..collision.events import EngineErrorEvent, EngineMatchEvent, EngineProgressEvent

    # Subscribe to events using type objects
    event_bus.subscribe(EngineMatchEvent, lambda e: data_logger.log_match(e))
    event_bus.subscribe(EngineProgressEvent, lambda e: data_logger.log_progress(e))
    event_bus.subscribe(EngineErrorEvent, lambda e: data_logger.log_error(e))
    return DataLoggerAdapter(data_logger)


class EnhancedMonitoringAdapter:
    """Adapter that subscribes enhanced monitoring to event bus events."""

    def __init__(self, monitoring_system: Any) -> None:
        """Initialize the monitoring adapter."""
        self._monitoring = monitoring_system

    def subscribe_to(self, event_bus: Any) -> None:
        """Subscribe to relevant events on the event bus."""
        from ..collision.events import EngineMatchEvent, EngineProgressEvent

        event_bus.subscribe(EngineMatchEvent, self._on_match)
        event_bus.subscribe(EngineProgressEvent, self._on_progress)

    def _on_match(self, event: Any) -> None:
        self._monitoring.record_metric("matches", 1)

    def _on_progress(self, event: Any) -> None:
        keys = getattr(event, "keys_checked", 0) or getattr(event, "total_checked", 0)
        self._monitoring.record_metric("keys_checked", keys)


class AlertSystemAdapter:
    """Adapter that subscribes AlertSystem to engine EventBus events.

    Enables event-driven alerting (R3 fix) — alerts are triggered by
    EngineProgressEvent and EngineErrorEvent rather than only via
    poll-based check_metrics() in the runtime loop.
    """

    def __init__(self, alert_system: Any) -> None:
        """Initialize the alert adapter."""
        self._alert_system = alert_system

    def subscribe_to(self, event_bus: Any) -> None:
        """Subscribe to relevant events on the event bus."""
        from ..collision.events import EngineErrorEvent, EngineProgressEvent

        event_bus.subscribe(EngineProgressEvent, self._on_progress)
        event_bus.subscribe(EngineErrorEvent, self._on_error)

    def _on_progress(self, event: Any) -> None:
        """Handle progress events — check metrics for alert conditions."""
        try:
            metrics = {
                "throughput": getattr(event, "throughput", 0) or getattr(event, "speed", 0),
                "error_rate": getattr(event, "error_rate", 0),
                "memory_usage_percent": getattr(event, "memory_usage", 0),
                "gpu_temperature": getattr(event, "gpu_temp", 0),
            }
            self._alert_system.check_metrics(metrics)
        except Exception:
            logger.debug("AlertSystemAdapter: progress alert check failed (non-fatal)", exc_info=True)

    def _on_error(self, event: Any) -> None:
        """Handle error events — check error rate for alert conditions."""
        try:
            metrics = {
                "error_rate": 0.1,  # Any error event implies elevated error rate
                "throughput": 0,
                "memory_usage_percent": 0,
                "gpu_temperature": 0,
            }
            self._alert_system.check_metrics(metrics)
        except Exception:
            logger.debug("AlertSystemAdapter: error alert check failed (non-fatal)", exc_info=True)


class EventAdapter:
    """Adapts engine events for monitoring consumption."""

    def adapt_match_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Convert match event to monitoring format.

        Args:
            event: Engine match event

        Returns:
            Adapted monitoring event

        """
        return {
            "type": "match_found",
            "address": event.get("address", ""),
            "timestamp": event.get("timestamp", 0),
        }

    def adapt_error_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Convert error event to monitoring format.

        Args:
            event: Engine error event

        Returns:
            Adapted monitoring event

        """
        return {
            "type": "error",
            "error_type": event.get("error_type", ""),
            "message": event.get("error_message", ""),
            "recoverable": event.get("recoverable", False),
        }

    def adapt_progress_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Convert progress event to monitoring format.

        Args:
            event: Engine progress event

        Returns:
            Adapted monitoring event

        """
        return {
            "type": "progress",
            "keys_checked": event.get("keys_checked", 0),
            "throughput": event.get("throughput", 0),
        }
