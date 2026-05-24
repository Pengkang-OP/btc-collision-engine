"""Event adapters for monitoring system integration."""

import logging

logger = logging.getLogger(__name__)


class DataLoggerAdapter:
    """Adapter that wraps a DataLogger and subscribes it to events."""

    def __init__(self, data_logger):
        self.data_logger = data_logger


def setup_data_logging(event_bus, data_logger):
    """Set up data logging via event bus.

    Args:
        event_bus: Event bus instance
        data_logger: DataLogger instance

    Returns:
        DataLoggerAdapter wrapping the data logger

    """
    # Import event types to avoid circular imports
    from src.collision.events import EngineErrorEvent, EngineMatchEvent, EngineProgressEvent

    # Subscribe to events using type objects
    event_bus.subscribe(EngineMatchEvent, lambda e: data_logger.log_match(e))
    event_bus.subscribe(EngineProgressEvent, lambda e: data_logger.log_progress(e))
    event_bus.subscribe(EngineErrorEvent, lambda e: data_logger.log_error(e))
    return DataLoggerAdapter(data_logger)


class EnhancedMonitoringAdapter:
    """Adapter that subscribes enhanced monitoring to event bus events."""

    def __init__(self, monitoring_system):
        self._monitoring = monitoring_system

    def subscribe_to(self, event_bus):
        """Subscribe to relevant events on the event bus."""
        from src.collision.events import EngineMatchEvent, EngineProgressEvent

        event_bus.subscribe(EngineMatchEvent, self._on_match)
        event_bus.subscribe(EngineProgressEvent, self._on_progress)

    def _on_match(self, event):
        self._monitoring.record_metric("matches", 1)

    def _on_progress(self, event):
        keys = getattr(event, "keys_checked", 0) or getattr(event, "total_checked", 0)
        self._monitoring.record_metric("keys_checked", keys)


class EventAdapter:
    """Adapts engine events for monitoring consumption."""

    def adapt_match_event(self, event: dict) -> dict:
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

    def adapt_error_event(self, event: dict) -> dict:
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

    def adapt_progress_event(self, event: dict) -> dict:
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
