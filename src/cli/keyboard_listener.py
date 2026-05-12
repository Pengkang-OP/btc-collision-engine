#!/usr/bin/env python3
"""
运行时键盘交互监听器

支持平台：
- Windows: 使用 msvcrt.kbhit / msvcrt.getch（无阻塞轮询）
- Unix:    使用 select + tty.setcbreak（非回显非缓冲模式）

如果任何依赖不可用，监听器静默失败，不影响主流程。
"""

import os
import sys
import threading
import time
from collections.abc import Callable


class KeyboardListener:
    """运行时键盘交互监听器，支持单字符按键回调（不需要按 Enter）。"""

    # 类级别可用性缓存：None 表示尚未检测
    _platform_available: bool | None = None
    _platform_unavailable_reason: str = ""

    @classmethod
    def is_available(cls) -> bool:
        """
        检测当前环境是否支持键盘监听。

        检测结果会被缓存，多次调用不会重复探测。

        返回:
            True  — 当前平台 + 终端支持无阻塞单字符读取
            False — 不支持（CI / 管道 / 非 TTY 等场景）
        """
        if cls._platform_available is not None:
            return cls._platform_available

        # 非 TTY（管道/重定向）场景不可用
        if not sys.stdin.isatty():
            cls._platform_available = False
            cls._platform_unavailable_reason = "stdin 非 TTY（管道或重定向模式）"
            return False

        if os.name == "nt":
            try:
                import msvcrt  # noqa: PLC0415, F401

                cls._platform_available = True
            except ImportError:
                cls._platform_available = False
                cls._platform_unavailable_reason = "msvcrt 模块不可用"
        else:
            try:
                import select  # noqa: PLC0415, F401
                import termios  # noqa: PLC0415
                import tty  # noqa: PLC0415, F401

                fd = sys.stdin.fileno()
                getattr(termios, "tcgetattr")(fd)  # 若非 TTY 会抛出 termios.error
                cls._platform_available = True
            except Exception as exc:
                cls._platform_available = False
                cls._platform_unavailable_reason = str(exc)

        if cls._platform_available is None:
            raise RuntimeError("KeyboardListener 平台检测逻辑错误：_platform_available 未设置")
        return cls._platform_available

    @classmethod
    def unavailable_reason(cls) -> str:
        """返回不可用原因字符串（可用时返回空字符串）。"""
        cls.is_available()  # 确保已检测
        return cls._platform_unavailable_reason

    def __init__(self, on_key_callback: Callable) -> None:
        """
        参数:
            on_key_callback: 接收单个大写字符的可调用对象，例如 'P'/'R'/'Q'/'S'
        """
        self._callback = on_key_callback
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # 实例可用性与类级别检测保持一致
        self._available: bool = KeyboardListener.is_available()

    def start(self) -> None:
        """启动监听线程（daemon，不阻塞主线程退出）。"""
        self._stop.clear()
        self._thread = threading.Thread(target=self._listen, daemon=True, name="KeyboardListener")
        self._thread.start()

    def stop(self) -> None:
        """停止监听线程，最多等待 1 秒。"""
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    # ------------------------------------------------------------------ #
    # 内部实现                                                              #
    # ------------------------------------------------------------------ #

    def _listen(self):
        if os.name == "nt":
            self._listen_windows()
        else:
            self._listen_unix()

    def _listen_windows(self):
        """Windows 平台：使用 msvcrt 实现无阻塞单字符读取。"""
        try:
            import msvcrt  # noqa: PLC0415
        except ImportError:
            self._available = False
            return

        while not self._stop.is_set():
            try:
                if msvcrt.kbhit():
                    raw = msvcrt.getch()
                    # 处理功能键（第一个字节为 0x00 或 0xe0，需再读一个字节丢弃）
                    if raw in (b"\x00", b"\xe0"):
                        msvcrt.getch()  # 丢弃第二个字节
                    else:
                        key = raw.decode("utf-8", errors="ignore").upper()
                        if key:
                            self._callback(key)
            except Exception:
                pass
            time.sleep(0.05)

    def _listen_unix(self):
        """Unix/Linux/macOS 平台：使用 tty.setcbreak + select 实现单字符读取。"""
        try:
            import select  # noqa: PLC0415
            import termios  # noqa: PLC0415
            import tty  # noqa: PLC0415
        except ImportError:
            self._available = False
            return

        fd = sys.stdin.fileno()
        try:
            old_settings = getattr(termios, "tcgetattr")(fd)
        except Exception:
            self._available = False
            return

        try:
            tty.setcbreak(fd)
            while not self._stop.is_set():
                try:
                    ready, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if ready:
                        key = sys.stdin.read(1).upper()
                        if key:
                            self._callback(key)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass
