"""Wizard message queue for inter-component communication."""
import queue
from typing import Any


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
            return None
