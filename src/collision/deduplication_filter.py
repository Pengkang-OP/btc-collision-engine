#!/usr/bin/env python3
"""
Deduplication filter for collision detection results.
"""

from ..utils import get_configured_logger

logger = get_configured_logger("DedupFilter")


class DeduplicationFilter:
    """Filters duplicate private keys and addresses in results."""

    def __init__(self):
        self._seen_keys: set[bytes] = set()
        self._seen_addresses: set[str] = set()

    def is_duplicate(
        self, private_key: bytes, address: str
    ) -> bool:
        """Check if key or address is a duplicate.

        Args:
            private_key: Private key bytes
            address: Bitcoin address

        Returns:
            True if duplicate
        """
        if private_key in self._seen_keys:
            return True
        if address.lower() in self._seen_addresses:
            return True
        self._seen_keys.add(private_key)
        self._seen_addresses.add(address.lower())
        return False

    def clear(self) -> None:
        """Clear all seen keys and addresses."""
        self._seen_keys.clear()
        self._seen_addresses.clear()
