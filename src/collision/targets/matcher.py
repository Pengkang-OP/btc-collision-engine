#!/usr/bin/env python3
"""Address matcher for collision detection against target set."""

from ...utils import get_configured_logger

logger = get_configured_logger("Matcher")


class AddressMatcher:
    """Matches generated addresses against target address set."""

    def __init__(
        self, targets: set[str] | None = None
    ):
        self._targets: set[str] = set()
        if targets:
            self._targets = {
                t.lower() for t in targets
            }

    def match(
        self, address: str
    ) -> bool:
        """Check if address matches any target.

        Args:
            address: Bitcoin address to check

        Returns:
            True if match found
        """
        return address.lower() in self._targets

    @property
    def target_count(self) -> int:
        return len(self._targets)
