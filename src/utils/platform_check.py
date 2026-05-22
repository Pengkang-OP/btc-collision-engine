"""Platform detection utilities for OS-specific features."""

import os
import platform
import sys


def is_linux() -> bool:
    """Check if running on Linux."""
    return sys.platform.startswith("linux")


def is_macos() -> bool:
    """Check if running on macOS."""
    return sys.platform == "darwin"


def is_windows() -> bool:
    """Check if running on Windows."""
    return os.name == "nt"


def get_platform_name() -> str:
    """Get human-readable platform name.

    Returns:
        Platform string (e.g. 'Linux', 'macOS', 'Windows')
    """
    return platform.system()


def has_admin_privileges() -> bool:
    """Check if process has admin/root privileges.

    Returns:
        True if running as administrator/root
    """
    if is_windows():
        import ctypes

        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    else:
        return os.geteuid() == 0
