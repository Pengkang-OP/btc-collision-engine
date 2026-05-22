"""日志平台适配模块

处理不同操作系统的特定问题，确保日志系统在所有平台上稳定运行，包括：
- Windows 平台适配
- Linux 平台适配
- macOS 平台适配
- 跨平台兼容性处理
"""

import ctypes
import logging
import os
import platform
import sys
from collections.abc import Callable
from typing import Any, cast


class PlatformAdapter:
    """平台适配器"""

    def __init__(self) -> None:
        """初始化平台适配器"""
        self.platform_name = platform.system()
        self.platform_version = platform.version()
        self.platform_architecture = platform.architecture()

    def get_platform_info(self) -> dict[str, Any]:
        """
        获取平台信息

        Returns:
            平台信息字典
        """
        return {
            "name": self.platform_name,
            "version": self.platform_version,
            "architecture": self.platform_architecture,
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
        }

    def get_file_path(self, relative_path: str) -> str:
        """
        获取平台特定的文件路径

        Args:
            relative_path: 相对路径

        Returns:
            平台特定的绝对路径
        """
        if self.platform_name == "Windows":
            # Windows 路径处理
            return os.path.abspath(relative_path).replace("/", "\\")
        else:
            # Unix-like 路径处理
            return os.path.abspath(relative_path)

    def get_log_directory(self) -> str:
        """
        获取平台特定的日志目录

        Returns:
            日志目录路径
        """
        if self.platform_name == "Windows":
            # Windows: 使用 AppData 目录
            appdata = os.getenv("APPDATA", os.path.expanduser("~"))
            return os.path.join(appdata, "btc-collision-engine", "logs")
        elif self.platform_name == "Darwin":
            # macOS: 使用 Library/Logs 目录
            return os.path.join(os.path.expanduser("~"), "Library", "Logs", "btc-collision-engine")
        else:
            # Linux: 使用 ~/.local/share 目录
            return os.path.join(
                os.path.expanduser("~"), ".local", "share", "btc-collision-engine", "logs"
            )

    def ensure_directory(self, directory: str) -> bool:
        """
        确保目录存在

        Args:
            directory: 目录路径

        Returns:
            是否成功
        """
        try:
            os.makedirs(directory, mode=0o750, exist_ok=True)
            return True
        except Exception as e:
            print(f"创建目录失败: {e}")
            return False

    def get_file_encoding(self) -> str:
        """
        获取平台特定的文件编码

        Returns:
            文件编码
        """
        if self.platform_name == "Windows":
            # Windows 默认使用 UTF-8
            return "utf-8"
        else:
            # Unix-like 系统默认使用 UTF-8
            return "utf-8"

    def get_console_encoding(self) -> str:
        """
        获取控制台编码

        Returns:
            控制台编码
        """
        if self.platform_name == "Windows":
            # Windows 控制台编码处理
            try:
                import ctypes

                kernel32 = ctypes.windll.kernel32
                cp = kernel32.GetConsoleOutputCP()
                return f"cp{cp}"
            except (OSError, AttributeError):
                return "utf-8"
        else:
            # Unix-like 系统默认使用 UTF-8
            return "utf-8"

    def is_admin(self) -> bool:
        """
        检查是否以管理员权限运行

        Returns:
            是否以管理员权限运行
        """
        if self.platform_name == "Windows":
            try:
                return cast(bool, ctypes.windll.shell32.IsUserAnAdmin() != 0)  # Windows ctypes API
            except (OSError, AttributeError):
                return False
        else:
            try:
                return getattr(os, "geteuid", lambda: -1)() == 0  # Unix-only，mypy无类型信息
            except (OSError, AttributeError):
                return False

    def get_process_priority(self) -> int:
        """
        获取进程优先级

        Returns:
            进程优先级
        """
        if self.platform_name == "Windows":
            # Windows 进程优先级
            try:
                import ctypes

                kernel32 = ctypes.windll.kernel32
                return cast(
                    int, kernel32.GetPriorityClass(kernel32.GetCurrentProcess())
                )  # Windows ctypes API
            except (OSError, AttributeError):
                return 0
        else:
            # Unix-like 系统进程优先级
            try:
                import psutil

                return int(psutil.Process(os.getpid()).nice())  # 可选依赖psutil
            except (OSError, AttributeError):
                return 0

    def set_process_priority(self, priority: int) -> bool:
        """
        设置进程优先级

        Args:
            priority: 优先级

        Returns:
            是否成功
        """
        if self.platform_name == "Windows":
            # Windows 进程优先级
            try:
                import ctypes

                kernel32 = ctypes.windll.kernel32
                return cast(
                    bool, kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), priority) != 0
                )  # Windows ctypes API
            except (OSError, AttributeError):
                return False
        else:
            # Unix-like 系统进程优先级
            try:
                import psutil

                psutil.Process(os.getpid()).nice(priority)
                return True
            except (OSError, AttributeError):
                return False

    def get_platform_specific_handlers(self) -> dict[str, Callable[..., Any]]:
        """
        获取平台特定的处理器

        Returns:
            平台特定的处理器字典
        """
        handlers: dict[str, Callable[..., Any]] = {}

        if self.platform_name == "Windows":
            # Windows 特定处理器
            handlers["file_handler"] = self._get_windows_file_handler
            handlers["console_handler"] = self._get_windows_console_handler
        elif self.platform_name == "Darwin":
            # macOS 特定处理器
            handlers["file_handler"] = self._get_unix_file_handler
            handlers["console_handler"] = self._get_unix_console_handler
        else:
            # Linux 特定处理器
            handlers["file_handler"] = self._get_unix_file_handler
            handlers["console_handler"] = self._get_unix_console_handler

        return handlers

    def _get_windows_file_handler(self, filename: str, level: int) -> logging.Handler:
        """
        获取 Windows 文件处理器

        Args:
            filename: 文件名
            level: 日志级别

        Returns:
            文件处理器
        """
        from .logging_config import SafeRotatingFileHandler

        return cast(
            logging.Handler,
            SafeRotatingFileHandler(
                filename, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
            ),
        )

    def _get_unix_file_handler(self, filename: str, level: int) -> logging.Handler:
        """
        获取 Unix 文件处理器

        Args:
            filename: 文件名
            level: 日志级别

        Returns:
            文件处理器
        """
        from logging.handlers import RotatingFileHandler

        return cast(
            logging.Handler,
            RotatingFileHandler(filename, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"),
        )

    def _get_windows_console_handler(self, level: int) -> logging.Handler:
        """
        获取 Windows 控制台处理器

        Args:
            level: 日志级别

        Returns:
            控制台处理器
        """
        from .logger import SafeStreamHandler

        return cast(logging.Handler, SafeStreamHandler(sys.stdout))

    def _get_unix_console_handler(self, level: int) -> logging.Handler:
        """
        获取 Unix 控制台处理器

        Args:
            level: 日志级别

        Returns:
            控制台处理器
        """
        from .logger import SafeStreamHandler

        return cast(logging.Handler, SafeStreamHandler(sys.stdout))

    def get_platform_optimizations(self) -> dict[str, Any]:
        """
        获取平台特定的优化策略

        Returns:
            优化策略
        """
        optimizations: dict[str, Any] = {
            "platform": self.platform_name,
            "optimizations": [],
        }

        if self.platform_name == "Windows":
            optimizations["optimizations"].append(
                {
                    "name": "文件锁处理",
                    "description": "使用 SafeRotatingFileHandler 避免文件锁问题",
                    "enabled": True,
                }
            )
            optimizations["optimizations"].append(
                {
                    "name": "控制台编码",
                    "description": "使用 SafeStreamHandler 处理控制台编码问题",
                    "enabled": True,
                }
            )
        elif self.platform_name == "Linux":
            optimizations["optimizations"].append(
                {"name": "文件权限", "description": "设置日志文件权限为 0o600", "enabled": True}
            )
            optimizations["optimizations"].append(
                {
                    "name": "系统日志",
                    "description": "考虑使用 syslog 进行日志聚合",
                    "enabled": False,
                }
            )
        elif self.platform_name == "Darwin":
            optimizations["optimizations"].append(
                {
                    "name": "macOS 日志",
                    "description": "考虑使用 macOS 原生日志系统",
                    "enabled": False,
                }
            )

        return optimizations


# 全局平台适配器实例
_platform_adapter: PlatformAdapter | None = None


def get_platform_adapter() -> PlatformAdapter:
    """
    获取平台适配器实例

    Returns:
        平台适配器实例
    """
    global _platform_adapter
    if _platform_adapter is None:
        _platform_adapter = PlatformAdapter()
    return _platform_adapter


def get_platform_info() -> dict[str, Any]:
    """
    获取平台信息

    Returns:
        平台信息字典
    """
    adapter = get_platform_adapter()
    return adapter.get_platform_info()


def get_log_directory() -> str:
    """
    获取平台特定的日志目录

    Returns:
        日志目录路径
    """
    adapter = get_platform_adapter()
    return adapter.get_log_directory()


def ensure_log_directory() -> bool:
    """
    确保日志目录存在

    Returns:
        是否成功
    """
    adapter = get_platform_adapter()
    log_dir = adapter.get_log_directory()
    return adapter.ensure_directory(log_dir)


def get_platform_specific_handlers() -> dict[str, Callable[..., Any]]:
    """
    获取平台特定的处理器

    Returns:
        平台特定的处理器字典
    """
    adapter = get_platform_adapter()
    return adapter.get_platform_specific_handlers()


def get_platform_optimizations() -> dict[str, Any]:
    """
    获取平台特定的优化策略

    Returns:
        优化策略
    """
    adapter = get_platform_adapter()
    return adapter.get_platform_optimizations()
