"""AMD GPU vendor implementation."""
from .base import BaseVendor


class AMDVendor(BaseVendor):
    """AMD-specific GPU implementation using OpenCL."""

    def initialize(self, device) -> bool:
        from ...utils import get_configured_logger
        logger = get_configured_logger("AMDVendor")
        logger.info("AMD GPU vendor initialized")
        return True

    def get_device_count(self) -> int:
        return 0
