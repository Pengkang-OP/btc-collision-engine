#!/usr/bin/env python3
"""Deduplication filter for collision detection results."""

from ..utils import get_configured_logger

logger = get_configured_logger("DedupFilter")


class DeduplicationFilter:
    """Filters duplicate private keys and addresses in results."""

    def __init__(
        self,
        max_size: int = 1_000_000,
        enabled: bool = True,
    ) -> None:
        """
        Initialize deduplication filter.

        Args:
            max_size: Maximum number of entries to track
            enabled: Whether the filter is enabled
        """
        self.max_size = max_size
        self.enabled = enabled
        self._seen_keys: set[bytes] = set()
        self._seen_addresses: set[str] = set()
        self._stats = {
            "checks_total": 0,
            "duplicates_found": 0,
        }

    def check_and_add(self, key: bytes, address: str | None = None) -> bool:
        """
        Check if key is duplicate and add if not.

        Args:
            key: Private key bytes
            address: Optional Bitcoin address

        Returns:
            True if not duplicate (added), False if duplicate
        """
        if not self.enabled:
            return True

        self._stats["checks_total"] += 1

        if key in self._seen_keys:
            self._stats["duplicates_found"] += 1
            return False

        if address and address.lower() in self._seen_addresses:
            self._stats["duplicates_found"] += 1
            return False

        # Add to tracking
        self._seen_keys.add(key)
        if address:
            self._seen_addresses.add(address.lower())

        # Trim if exceeds max_size
        if self.max_size > 0 and len(self._seen_keys) > self.max_size:
            self._seen_keys.clear()
            self._seen_addresses.clear()
            logger.debug(
                "DeduplicationFilter cleared at size %d",
                self.max_size,
            )

        return True

    def is_duplicate(
        self,
        private_key: bytes,
        address: str,
    ) -> bool:
        """
        Check if key or address is a duplicate.

        Args:
            private_key: Private key bytes
            address: Bitcoin address

        Returns:
            True if duplicate
        """
        if not self.enabled:
            return False

        return (
            private_key in self._seen_keys
            or address.lower() in self._seen_addresses
        )

    def get_stats(self) -> dict:
        """
        Get filter statistics.

        Returns:
            Dictionary with filter statistics
        """
        return {
            **self._stats,
            "unique_keys": len(self._seen_keys),
            "unique_addresses": len(self._seen_addresses),
            "enabled": self.enabled,
            "max_size": self.max_size,
        }

    def reset(self) -> None:
        """Reset filter (clear all tracking data)."""
        self._seen_keys.clear()
        self._seen_addresses.clear()
        self._stats = {
            "checks_total": 0,
            "duplicates_found": 0,
        }

    def clear(self) -> None:
        """Clear all seen keys and addresses (alias for reset)."""
        self.reset()
