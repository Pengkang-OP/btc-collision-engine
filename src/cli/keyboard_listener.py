"""Keyboard listener for graceful shutdown and control."""
import sys
import threading

from ..utils import get_configured_logger

logger = get_configured_logger("KeyboardListener")


class KeyboardListener:
    """Listens for keyboard input to control engine operation."""

    def __init__(self):
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start listening for 'q' key to stop."""
        thread = threading.Thread(
            target=self._listen,
            daemon=True,
        )
        thread.start()

    def _listen(self) -> None:
        """Listen loop."""
        while not self._stop_event.is_set():
            try:
                if sys.stdin.read(1).lower() == "q":
                    logger.info(
                        "Stop requested via keyboard",
                    )
                    break
            except (OSError, EOFError):
                break

    def stop(self) -> None:
        """Stop listening."""
        self._stop_event.set()
