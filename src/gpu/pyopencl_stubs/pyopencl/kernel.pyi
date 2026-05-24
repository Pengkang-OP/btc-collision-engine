"""Minimal type stubs for pyopencl.kernel module."""

from collections.abc import Sequence
from typing import Any

from . import CommandQueue

class Kernel:
    """OpenCL kernel object."""

    def __init__(self, program: Any, name: str) -> None: ...
    program: Any
    name: str
    num_args: int
    def set_arg(self, idx: int, arg: Any) -> None: ...
    def __call__(
        self,
        queue: CommandQueue,
        global_size: int | Sequence[int],
        local_size: int | Sequence[int] | None = ...,
        *,
        wait_for: Sequence[Any] | None = ...,
        g_times_l: bool = ...,
    ) -> Any: ...
