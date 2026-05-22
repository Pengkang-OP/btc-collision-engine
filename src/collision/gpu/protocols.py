#!/usr/bin/env python3
"""
Protocol interfaces for GPU collision components.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class GPUDeviceProtocol(Protocol):
    """Protocol for GPU device abstraction."""
    name: str
    vendor: str
    compute_units: int
    global_memory: int


@runtime_checkable
class GPUKernelProtocol(Protocol):
    """Protocol for GPU kernel abstraction."""
    def compile(self, source: str) -> None: ...
    def execute(self, *args) -> None: ...
