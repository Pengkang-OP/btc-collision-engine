#!/usr/bin/env python3
"""
GPU kernel adapter for OpenCL kernel management.
"""

from ...utils import get_configured_logger

logger = get_configured_logger("KernelAdapter")


class KernelAdapter:
    """Manages OpenCL kernel compilation and execution."""

    def __init__(self, context, device):
        self._context = context
        self._device = device
        self._program = None
        self._kernels = {}
