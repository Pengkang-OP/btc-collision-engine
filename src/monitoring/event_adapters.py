"""Event adapters for monitoring system integration."""
import logging

logger = logging.getLogger(__name__)


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
