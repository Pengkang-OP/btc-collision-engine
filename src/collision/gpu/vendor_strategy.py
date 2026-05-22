#!/usr/bin/env python3
"""
Vendor-specific GPU strategy implementations.
"""

from ...utils import get_configured_logger

logger = get_configured_logger("VendorStrategy")


class BaseVendorStrategy:
    """Base class for GPU vendor-specific strategies."""

    def __init__(self, device):
        self._device = device

    def optimize_kernel(self, source: str) -> str:
        """Apply vendor-specific kernel optimizations."""
        return source


class NvidiaVendorStrategy(BaseVendorStrategy):
    """NVIDIA-specific GPU strategy."""

    def optimize_kernel(self, source: str) -> str:
        source = super().optimize_kernel(source)
        source = f"#define NVIDIA_GPU\n{source}"
        logger.debug(
            "Applied NVIDIA kernel optimizations"
        )
        return source


class AmdVendorStrategy(BaseVendorStrategy):
    """AMD-specific GPU strategy."""

    def optimize_kernel(self, source: str) -> str:
        source = super().optimize_kernel(source)
        source = f"#define AMD_GPU\n{source}"
        logger.debug(
            "Applied AMD kernel optimizations"
        )
        return source
