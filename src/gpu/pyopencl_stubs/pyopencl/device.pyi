"""Minimal type stubs for pyopencl.device module."""

from typing import Any

class Device:
    """OpenCL device."""

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
    platform: Any  # Platform
    max_clock_frequency: int
    max_mem_alloc_size: int
    image_support: bool
    max_read_image_args: int
    max_write_image_args: int
    image2d_max_width: int
    image2d_max_height: int
    image3d_max_width: int
    image3d_max_height: int
    image3d_max_depth: int
