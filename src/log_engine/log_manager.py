"""Log manager for centralized log configuration."""

import logging

from ..utils import get_configured_logger

logger = get_configured_logger(__name__)


class LogManager:
    """Manages log configuration and lifecycle."""

    def __init__(self):
        self._loggers: dict[str, logging.Logger] = {}

    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a named logger.

        Args:
            name: Logger name

        Returns:
            Logger instance

        """
        if name not in self._loggers:
            self._loggers[name] = logging.getLogger(
                name,
            )
        return self._loggers[name]

    def set_level(
        self,
        name: str,
        level: int,
    ) -> None:
        """Set log level for a logger.

        Args:
            name: Logger name
            level: Logging level

        """
        log = self.get_logger(name)
        log.setLevel(level)

    def cleanup(self) -> None:
        """Remove all managed loggers."""
        self._loggers.clear()
