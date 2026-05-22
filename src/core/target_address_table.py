"""Target address table for collision detection."""

from ..utils import get_configured_logger

logger = get_configured_logger("TargetAddressTable")


class TargetAddressTable:
    """
    Target address table for efficient collision detection.

    Provides O(1) lookup for target addresses, supporting bloom
    filters for reduced memory usage and multiple address format
    matching.
    """

    def __init__(self, targets: set[str] | None = None):
        """
        Initialize target address table.

        Args:
            targets: Initial set of target addresses
        """
        self._addresses: set[str] = set()
        if targets:
            self._addresses.update(
                a.lower() for a in targets
            )
        logger.info(
            f"Target address table initialized: "
            f"{len(self._addresses)} addresses"
        )

    def add_target(self, address: str) -> None:
        """Add a target address.

        Args:
            address: Bitcoin address to add
        """
        self._addresses.add(address.lower())

    def add_targets(
        self, addresses: list[str]
    ) -> None:
        """Add multiple target addresses.

        Args:
            addresses: List of Bitcoin addresses
        """
        self._addresses.update(
            a.lower() for a in addresses
        )

    def is_match(self, address: str) -> bool:
        """Check if address matches any target.

        Args:
            address: Bitcoin address to check

        Returns:
            True if address matches a target
        """
        return address.lower() in self._addresses

    def remove_target(self, address: str) -> None:
        """Remove a target address.

        Args:
            address: Bitcoin address to remove
        """
        self._addresses.discard(address.lower())

    def clear(self) -> None:
        """Clear all target addresses."""
        self._addresses.clear()

    @property
    def count(self) -> int:
        """Get number of target addresses."""
        return len(self._addresses)

    @property
    def addresses(self) -> set[str]:
        """Get a copy of target addresses."""
        return self._addresses.copy()
