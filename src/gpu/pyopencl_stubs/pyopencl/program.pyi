"""Minimal type stubs for pyopencl.program module."""

from collections.abc import Sequence
from typing import Any

from . import Context, Device, Kernel

class Program:
    """OpenCL program object."""

    def __init__(self, context: Context, src: str) -> None: ...
    context: Context
    def build(
        self,
        options: str | None = ...,
        devices: Sequence[Device] | None = ...,
    ) -> None: ...
    def __getattr__(self, name: str) -> Kernel: ...
    def get_build_info(self, device: Device, param: int) -> Any: ...
