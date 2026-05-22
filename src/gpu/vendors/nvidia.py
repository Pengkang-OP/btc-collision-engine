"""NVIDIA GPU vendor implementation."""
from .base import BaseVendor


class NvidiaVendor(BaseVendor):
    """NVIDIA-specific GPU implementation using CUDA/OpenCL."""

    def initialize(self, device) -> bool:
        from ...utils import get_configured_logger
        logger = get_configured_logger("NvidiaVendor")
        logger.info("NVIDIA GPU vendor initialized")
        return True

    def get_device_count(self) -> int:
        return 0
