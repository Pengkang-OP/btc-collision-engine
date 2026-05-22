#!/usr/bin/env python3
"""
Continuous address matcher.

Provides continuous matching of generated addresses against target
address sets with efficient set operations.
"""

from ..utils import get_configured_logger

logger = get_configured_logger("ContinuousMatcher")


class ContinuousMatcher:
    """Continuous address matcher for collision detection.

    Efficiently checks generated addresses against a target set and
    accumulates matches for batch processing.
    """

    def __init__(self, targets: set[str] | None = None):
        """
        Initialize matcher.

        Args:
            targets: Initial set of target addresses
        """
        self._targets: set[str] = set()
        self._matches: list[dict] = []
        if targets:
            self._targets = {
                a.lower() for a in targets
            }

    def check(self, address: str) -> bool:
        """Check if address matches any target.

        Args:
            address: Bitcoin address to check

        Returns:
            True if match found
        """
        return address.lower() in self._targets

    def record_match(
        self,
        private_key: bytes,
        address: str,
        wif: str,
    ) -> None:
        """Record a found match.

        Args:
            private_key: Matched private key
            address: Matched address
            wif: WIF-encoded key
        """
        self._matches.append(
            {
                "private_key": private_key,
                "address": address,
                "wif": wif,
            }
        )

    @property
    def match_count(self) -> int:
        """Get number of matches found."""
        return len(self._matches)

    def clear_matches(self) -> None:
        """Clear accumulated matches."""
        self._matches.clear()
