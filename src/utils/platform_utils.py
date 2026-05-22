"""Platform-specific utility functions."""

import os
import sys


class PlatformUtils:
    """Platform utility functions."""
    
    @staticmethod
    def is_windows() -> bool:
        """Check if running on Windows."""
        return os.name == "nt"
    
    @staticmethod
    def is_linux() -> bool:
        """Check if running on Linux."""
        return sys.platform == "linux"
    
    @staticmethod
    def is_darwin() -> bool:
        """Check if running on macOS."""
        return sys.platform == "darwin"


def get_os_name() -> str:
    """Get normalized OS name.

    Returns:
        'windows', 'linux', or 'darwin'
    """
    if os.name == "nt":
        return "windows"
    return sys.platform.lower()


def get_memory_limit() -> int:
    """Get available memory limit for the process.

    On Linux, returns available memory in bytes.
    On other platforms, returns a conservative estimate.

    Returns:
        Memory limit in bytes
    """
    try:
        import psutil

        return psutil.virtual_memory().available
    except ImportError:
        return 4 * 1024**3  # 4GB default


def has_gpu_support() -> bool:
    """Check if GPU support libraries are available.

    Returns:
        True if OpenCL or CUDA support is detected
    """
    try:
        import opencl  # noqa: F401
        return True
    except ImportError:
        pass
    try:
        import pyopencl  # noqa: F401
        return True
    except ImportError:
        pass
    return False
