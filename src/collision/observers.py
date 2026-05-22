#!/usr/bin/env python3
"""
Observers for collision detection event monitoring.
"""

from abc import ABC, abstractmethod


class CollisionObserver(ABC):
    """Observer interface for collision events."""

    @abstractmethod
    def on_match_found(
        self, private_key: bytes, address: str, wif: str
    ) -> None:
        """Called when a match is found."""

    @abstractmethod
    def on_progress(
        self, keys_checked: int, elapsed: float
    ) -> None:
        """Called on progress update."""

    @abstractmethod
    def on_error(
        self, error: Exception, recoverable: bool
    ) -> None:
        """Called on error."""


class LoggingObserver(CollisionObserver):
    """Observer that logs collision events."""

    import logging
    logger = logging.getLogger(__name__)

    def on_match_found(
        self, private_key: bytes, address: str, wif: str
    ) -> None:
        self.logger.info(
            f"Match found! address={address}"
        )

    def on_progress(
        self, keys_checked: int, elapsed: float
    ) -> None:
        self.logger.debug(
            f"Progress: {keys_checked} keys "
            f"in {elapsed:.1f}s"
        )

    def on_error(
        self, error: Exception, recoverable: bool
    ) -> None:
        level = (
            self.logger.warning
            if recoverable
            else self.logger.error
        )
        level(f"Collision error: {error}")
