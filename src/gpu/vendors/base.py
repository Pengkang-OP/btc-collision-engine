"""Base class for GPU vendor-specific implementations."""
from abc import ABC, abstractmethod
from typing import Any


class BaseVendor(ABC):
    """Abstract base class for GPU vendor implementations."""

    @abstractmethod
    def initialize(self, device: Any) -> bool:
        """Initialize vendor-specific GPU support.

        Args:
            device: GPU device instance

        Returns:
            True if initialization succeeded
        """

    @abstractmethod
    def get_device_count(self) -> int:
        """Get available device count."""
