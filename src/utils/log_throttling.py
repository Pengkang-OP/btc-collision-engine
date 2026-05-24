"""Log throttling utility.

Provides unified error log frequency control to prevent log
flooding.
"""

import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)


class LogThrottle:
    """Throttles repeated log messages."""

    def __init__(
        self, interval: float = 5.0,
    ):
        self._interval = interval
        self._last_log: dict[str, float] = {}

    def should_log(
        self, key: str,
    ) -> bool:
        """Check if a message should be logged.

        Args:
            key: Unique key for the message

        Returns:
            True if message should be logged

        """
        now = time.time()
        last = self._last_log.get(key, 0)
        if now - last >= self._interval:
            self._last_log[key] = now
            return True
        return False

    def throttle(
        self,
        key: str,
        log_fn: Callable,
        message: str,
    ) -> None:
        """Log a throttled message.

        Args:
            key: Unique message key
            log_fn: Log function (e.g. logger.warning)
            message: Message to log

        """
        if self.should_log(key):
            log_fn(message)
