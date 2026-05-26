"""Wizard message queue for inter-component communication."""

import queue
from typing import Any

from ..utils import get_configured_logger

logger = get_configured_logger(__name__)


class WizardMessageQueue:
    """Message queue for wizard component communication."""

    def __init__(self):
        self._queue: queue.Queue[Any] = queue.Queue()

    def send(self, message: Any) -> None:
        """Send a message.

        Args:
            message: Message payload

        """
        self._queue.put(message)

    def receive(self, timeout: float = 0.1) -> Any:
        """Receive a message with timeout.

        Args:
            timeout: Wait timeout in seconds

        Returns:
            Message or None if timeout

        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            logger.debug("Message queue receive timed out after %.1fs", timeout)
            return None


# Global message queue instance
_global_message_queue: WizardMessageQueue | None = None


def get_message_queue() -> WizardMessageQueue:
    """Get the global message queue instance.

    Returns:
        Global WizardMessageQueue instance

    """
    global _global_message_queue
    if _global_message_queue is None:
        _global_message_queue = WizardMessageQueue()
    return _global_message_queue
