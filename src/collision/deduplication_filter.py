#!/usr/bin/env python3
"""Deduplication filter for collision detection results.

Thread-safe filter that prevents re-processing of already-seen
private keys and addresses.
"""

import threading

from ..utils import get_configured_logger

logger = get_configured_logger("DedupFilter")


class DeduplicationFilter:
    """Filters duplicate private keys and addresses in results.

    Thread-safe via internal lock.
    """

    def __init__(
        self,
        max_size: int = 1_000_000,
        enabled: bool = True,
    ) -> None:
        """Initialize deduplication filter.

        Args:
            max_size: Maximum number of entries to track
            enabled: Whether the filter is enabled

        """
        self.max_size = max_size
        self.enabled = enabled
        self._lock = threading.Lock()
        self._seen_keys: set[bytes] = set()
        self._seen_addresses: set[str] = set()
        self._stats = {
            "checks_total": 0,
            "duplicates_found": 0,
        }

    @property
    def _current_size(self) -> int:
        """Number of entries currently tracked."""
        return len(self._seen_keys)

    def check_and_add(self, key: bytes, address: str | None = None) -> bool:
        """Check if key is duplicate and add if not.

        Args:
            key: Private key bytes
            address: Optional Bitcoin address

        Returns:
            True if not duplicate (added), False if duplicate

        """
        if not self.enabled:
            return True

        with self._lock:
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

            # If over max_size, warn and accept new items without clearing
            # (clearing all would silently lose dedup state)
            if self.max_size > 0 and len(self._seen_keys) > self.max_size:
                logger.warning(
                    "DeduplicationFilter exceeded max_size=%d (%d keys), "
                    "new items will be accepted without dedup. "
                    "Consider increasing max_size.",
                    self.max_size,
                    len(self._seen_keys),
                )
                # Reset stats counter but keep sets for best-effort dedup
                self._stats["max_exceeded"] = self._stats.get("max_exceeded", 0) + 1

        return True

    def is_duplicate(
        self,
        private_key: bytes,
        address: str,
    ) -> bool:
        """Check if key or address is a duplicate.

        Args:
            private_key: Private key bytes
            address: Bitcoin address

        Returns:
            True if duplicate

        """
        if not self.enabled:
            return False

        with self._lock:
            return private_key in self._seen_keys or address.lower() in self._seen_addresses

    def get_stats(self) -> dict:
        """Get filter statistics.

        Returns:
            Dictionary with filter statistics

        """
        with self._lock:
            return {
                **self._stats,
                "unique_keys": len(self._seen_keys),
                "unique_addresses": len(self._seen_addresses),
                "enabled": self.enabled,
                "max_size": self.max_size,
            }

    def reset(self) -> None:
        """Reset filter (clear all tracking data)."""
        with self._lock:
            self._seen_keys.clear()
            self._seen_addresses.clear()
            self._stats = {
                "checks_total": 0,
                "duplicates_found": 0,
            }

    def clear(self) -> None:
        """Clear all seen keys and addresses (alias for reset)."""
        self.reset()
