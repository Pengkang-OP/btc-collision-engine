#!/usr/bin/env python3
"""
Windows 控制台 UTF-8 编码修复工具

在 Windows 平台上，默认控制台编码通常是 GBK/CP936，
导致中文输出显示为乱码。此模块通过调用 Windows API
设置控制台编码为 UTF-8 (代码页 65001)，解决中文显示问题。

非 Windows 平台下，所有函数为空操作，保证跨平台兼容性。
"""
import ctypes
import io
import logging
import sys

logger = logging.getLogger(__name__)

__version__ = "1.0.0"
__author__ = "BTC Collision Engine Team"
__date__ = "2025-05-17"


def is_utf8_setup_needed() -> bool:
    """检查是否需要设置 UTF-8 编码。

    Returns:
        True 如果在 Windows 平台且控制台编码不是 UTF-8
    """
    if sys.platform != "win32":
        return False
    try:
        encoding = get_console_encoding()
        return encoding.lower() not in ("utf-8", "utf8", "cp65001")
    except Exception:
        return True


def get_console_encoding() -> str:
    """获取当前控制台编码。

    Returns:
        当前控制台编码字符串，如 'cp936'、'utf-8'
    """
    if sys.platform != "win32":
        try:
            return sys.stdout.encoding or "utf-8"
        except Exception:
            return "utf-8"
    try:
        cp = ctypes.windll.kernel32.GetConsoleOutputCP()
        return f"cp{cp}"
    except Exception:
        try:
            return sys.stdout.encoding or "unknown"
        except Exception:
            return "unknown"


def setup_windows_utf8() -> bool:
    """在 Windows 平台上设置控制台为 UTF-8 编码。

    通过调用 Windows API SetConsoleOutputCP(65001) 和
    SetConsoleCP(65001) 将控制台编码切换为 UTF-8。
    同时重新包装 sys.stdout 以使用 UTF-8 编码。

    Returns:
        True 如果设置成功或无需设置，False 如果设置失败
    """
    if sys.platform != "win32":
        return True

    if not is_utf8_setup_needed():
        return True

    try:
        # 设置控制台代码页为 UTF-8 (65001)
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)

        # 重新包装 stdout 以使用 UTF-8 编码
        if hasattr(sys.stdout, "buffer"):
            try:
                sys.stdout = io.TextIOWrapper(
                    sys.stdout.buffer,
                    encoding="utf-8",
                    errors="replace",
                    line_buffering=True,
                )
            except Exception as wrapper_err:
                logger.debug(f"Failed to wrap stdout: {wrapper_err}")

        if hasattr(sys.stderr, "buffer"):
            try:
                sys.stderr = io.TextIOWrapper(
                    sys.stderr.buffer,
                    encoding="utf-8",
                    errors="replace",
                    line_buffering=True,
                )
            except Exception as wrapper_err:
                logger.debug(f"Failed to wrap stderr: {wrapper_err}")

        logger.debug("Windows console code page set to UTF-8 (65001)")
        return True
    except Exception as e:
        logger.debug(f"Failed to set UTF-8 code page: {e}")
        return False
