"""Base search mode for GPU collision detection."""
from abc import ABC, abstractmethod
from typing import Any


class BaseSearchMode(ABC):
    """Abstract base class for GPU search modes."""

    @abstractmethod
    def search(
        self,
        device,
        targets: set[str],
        batch_size: int,
    ) -> list[dict[str, Any]]:
        """Execute search on GPU device.

        Args:
            device: GPU device instance
            targets: Target address set
            batch_size: Keys per batch

        Returns:
            List of match records
        """

    @abstractmethod
    def name(self) -> str:
        """Get search mode name."""
