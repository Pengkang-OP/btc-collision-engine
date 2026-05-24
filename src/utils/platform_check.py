"""Platform detection utilities for OS-specific features."""

import logging
import os
import platform
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class PlatformChecker:
    """Cross-platform compatibility checker."""

    def __init__(self):
        self._results: list[tuple[bool, str]] = []

    def _add(self, passed: bool, message: str):
        self._results.append((passed, message))

    def run_all_checks(self) -> tuple[bool, list[tuple[bool, str]]]:
        """Run all platform compatibility checks.

        Returns:
            (all_passed, list of (passed, message) tuples)
        """
        self._results = []

        # OS detection
        self._add(True, f"操作系统: {platform.system()} {platform.release()}")

        # Python version
        py_ver = sys.version_info
        py_ok = py_ver >= (3, 9)
        label = "OK" if py_ok else "需要 >=3.9"
        self._add(py_ok, f"Python 版本: {py_ver.major}.{py_ver.minor}.{py_ver.micro} {label}")

        # Path separators
        self._add(True, f"路径分隔符: '{os.sep}'")

        # File encoding
        self._add(True, f"文件系统编码: {sys.getfilesystemencoding()}")

        # Disk space (project directory)
        try:
            usage = shutil.disk_usage(Path.cwd())
            free_gb = usage.free / (1024**3)
            space_ok = free_gb >= 1.0
            label = "OK" if space_ok else "不足(建议>=1GB)"
            self._add(space_ok, f"磁盘可用空间: {free_gb:.1f}GB {label}")
        except OSError:
            self._add(False, "磁盘空间: 无法检测")

        # CPU cores
        cpu_count = os.cpu_count() or 0
        self._add(cpu_count > 0, f"CPU 核心数: {cpu_count}")

        all_passed = all(passed for passed, _ in self._results)
        return all_passed, self._results

    def print_report(self):
        """Print platform check report."""
        print(f"\n{'=' * 60}")  # noqa: T201
        print("  跨平台兼容性检查")  # noqa: T201
        print(f"{'=' * 60}")  # noqa: T201
        for passed, msg in self._results:
            status = "[OK]" if passed else "[WARN]"
            print(f"  {status}  {msg}")  # noqa: T201
        all_passed = all(p for p, _ in self._results)
        print(f"{'=' * 60}")  # noqa: T201
        print(f"  结果: {'全部通过' if all_passed else '存在警告'}")  # noqa: T201
        print(f"{'=' * 60}\n")  # noqa: T201

    def generate_report(self) -> dict:
        """Generate a structured report dict."""
        vi = sys.version_info
        return {
            "platform": platform.system(),
            "release": platform.release(),
            "python_version": f"{vi.major}.{vi.minor}.{vi.micro}",
            "cpu_cores": os.cpu_count(),
            "checks": [{"passed": p, "message": m} for p, m in self._results],
        }


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
    return os.geteuid() == 0
