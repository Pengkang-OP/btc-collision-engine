"""Minimal type stubs for pyopencl (OpenCL wrapper).

This stub file provides type annotations for pyopencl, which doesn't have
official type stubs. Only the most commonly used APIs are stubbed.
"""

from collections.abc import Sequence
from typing import Any

# ── Platform & Device ──────────────────────────────────────────────────

class Platform:
    name: str
    vendor: str
    version: str
    profile: str
    extensions: str
    def get_devices(self, device_type: int = ...) -> list[Device]: ...
    def get_info(self, param: Any) -> Any: ...

class Device:
    name: str
    vendor: str
    version: str
    driver_version: str
    global_mem_size: int
    local_mem_size: int
    max_compute_units: int
    max_work_group_size: int
    max_work_item_sizes: list[int]
    available: bool
    compiler_available: bool
    platform: Platform
    def get_info(self, param: Any) -> Any: ...

# ── Context ─────────────────────────────────────────────────────────────

class Context:
    def __init__(self, devices: Sequence[Device]) -> None: ...
    devices: list[Device]
    properties: int | None

# ── Command Queue ──────────────────────────────────────────────────────

class CommandQueue:
    def __init__(
        self,
        context: Context,
        device: Device | None = ...,
        properties: int = ...,
    ) -> None: ...
    context: Context
    device: Device
    properties: int
    def finish(self) -> None: ...
    def flush(self) -> None: ...

# ── Memory Flags ─────────────────────────────────────────────────────

class _MemFlags:
    READ_WRITE: int
    WRITE_ONLY: int
    READ_ONLY: int
    USE_HOST_PTR: int
    ALLOC_HOST_PTR: int
    COPY_HOST_PTR: int

mem_flags: _MemFlags

# ── Command Queue Properties ───────────────────────────────────────

class _CommandQueueProperties:
    PROFILING_ENABLE: int
    OUT_OF_ORDER_EXEC_MODE_ENABLE: int

command_queue_properties: _CommandQueueProperties

# ── Buffer ───────────────────────────────────────────────────────────

class Buffer:
    def __init__(
        self,
        context: Context,
        flags: int,
        size: int = ...,
        hostbuf: Any = ...,
    ) -> None: ...
    context: Context
    size: int
    flags: int
    def release(self) -> None: ...
    def retain(self) -> None: ...

# ── Program & Kernel ───────────────────────────────────────────────

class Program:
    def __init__(self, context: Context, src: str | Sequence[str]) -> None: ...
    def build(self, options: str | None = ..., devices: Sequence[Device] | None = ...) -> Program: ...
    def __getattr__(self, name: str) -> Kernel: ...
    def get_build_info(self, device: Device, param: int) -> Any: ...

class Kernel:
    def __init__(self, program: Program, name: str) -> None: ...
    def set_arg(self, idx: int, arg: Any) -> None: ...
    def __call__(
        self,
        queue: CommandQueue,
        global_size: int | Sequence[int],
        local_size: int | Sequence[int] | None = ...,
        *args: Any,
        **kwargs: Any,
    ) -> Any: ...
    def get_work_group_info(self, device: Device, param: int) -> Any: ...

# ── Enqueue Functions ──────────────────────────────────────────────

def enqueue_copy(
    queue: CommandQueue,
    dest: Buffer | Any,
    src: Buffer | Any,
    **kwargs: Any,
) -> Any: ...

def enqueue_fill_buffer(
    queue: CommandQueue,
    buf: Buffer,
    pattern: Any,
    offset: int,
    size: int,
    wait_for: Sequence[Any] | None = ...,
) -> Any: ...

def enqueue_nd_range_kernel(
    queue: CommandQueue,
    kernel: Kernel,
    global_work_size: Sequence[int],
    local_work_size: Sequence[int] | None = ...,
    global_work_offset: Sequence[int] | None = ...,
    wait_for: Sequence[Any] | None = ...,
    g_times_l: bool = ...,
) -> Any: ...

def enqueue_migrate_mem_objects(
    queue: CommandQueue,
    mem_objects: Sequence[Buffer],
    flags: int = ...,
    wait_for: Sequence[Any] | None = ...,
) -> Any: ...

# ── Image (minimal) ────────────────────────────────────────────────

class Image:
    def __init__(
        self,
        context: Context,
        flags: int,
        format: Any,
        shape: Sequence[int],
        pitches: Sequence[int] | None = ...,
        hostbuf: Any = ...,
    ) -> None: ...

# ── Information Queries ────────────────────────────────────────────

def get_platforms() -> list[Platform]: ...
def get_devices(device_type: int = ...) -> list[Device]: ...

# ── Constants ─────────────────────────────────────────────────────────

# Device type constants
device_type: Any
device_type_CPU: int  # noqa: N816
device_type_GPU: int  # noqa: N816
device_type_ACCELERATOR: int  # noqa: N816
device_type_DEFAULT: int  # noqa: N816
device_type_ALL: int  # noqa: N816

# Device info constants
device_info: Any

# Platform info constants
platform_info: Any

# Build status
program_build_status: Any
program_build_status_SUCCESS: int  # noqa: N816
program_build_status_ERROR: int  # noqa: N816

# Build options
program_build_options: Any

# Memory object types
mem_object_type: Any

# Kernel info
kernel_work_group: Any

# Event status
complete: int
running: int
submitted: int
queued: int

# Command execution status
command_execution_status: Any

# Profiling info
profiling_command_queued: int
profiling_command_submit: int
profiling_command_start: int
profiling_command_end: int

# ── Local Memory ───────────────────────────────────────────────────

class LocalMemory:
    def __init__(self, size: int) -> None: ...
    size: int

# ── Error ──────────────────────────────────────────────────────────

class Error(Exception):
    """Base pyopencl error."""
    ...
