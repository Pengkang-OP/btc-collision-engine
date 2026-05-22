"""Notification channels for alerting."""
import logging

logger = logging.getLogger(__name__)


class NotificationChannel:
    """Base notification channel."""

    def send(self, title: str, message: str) -> None:
        """Send notification.

        Args:
            title: Notification title
            message: Notification body
        """
        logger.info(f"[{title}] {message}")


class ConsoleChannel(NotificationChannel):
    """Console output notification channel."""

    def send(self, title: str, message: str) -> None:
        print(f"[{title}] {message}")


class LogChannel(NotificationChannel):
    """Log file notification channel."""

    def send(self, title: str, message: str) -> None:
        logger.warning(f"[{title}] {message}")
