"""Minimal type stubs for pyopencl.buffer module."""

from typing import Any

from . import Context

class Buffer:
    """OpenCL buffer object."""

    def __init__(
        self,
        context: Context,
        flags: int,
        size: int,
        hostbuf: Any = ...,
    ) -> None: ...
    context: Context
    size: int
    flags: int
    def release(self) -> None: ...
    def retain(self) -> None: ...
