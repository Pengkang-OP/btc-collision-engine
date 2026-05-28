r"""非阻塞键盘输入检测，支持跨平台 'q' 键优雅退出。.

用法::

    from src.cli.keyboard_listener import check_key

    while running:
        key = check_key()
        if key and key.lower() == 'q':
            print("\n[INFO] 用户按下 'q'，正在停止...")
            stop()
"""

import sys

from ..utils import get_configured_logger

logger = get_configured_logger("KeyboardListener")

# 平台特定的非阻塞键盘检测
_is_windows = sys.platform == "win32"

if _is_windows:

    def check_key() -> str | None:
        """Windows: 使用 msvcrt.kbhit 非阻塞检测按键。."""
        try:
            import msvcrt

            if msvcrt.kbhit():  # type: ignore[attr-defined]
                ch = msvcrt.getch()  # type: ignore[attr-defined]
                try:
                    return ch.decode("utf-8", errors="replace")
                except (UnicodeDecodeError, AttributeError):
                    return ch.decode("ascii", errors="replace") if isinstance(ch, bytes) else str(ch)
        except (ImportError, OSError) as e:
            logger.debug("Windows check_key failed: %s", e)
        return None

else:

    def check_key() -> str | None:
        """Unix: 使用 select 非阻塞检测 stdin。."""
        try:
            import select

            if select.select([sys.stdin], [], [], 0)[0]:
                return sys.stdin.read(1)
        except (OSError, ValueError) as e:
            logger.debug("Unix check_key failed: %s", e)
        return None


# 兼容旧接口
class KeyboardListener:
    """键盘监听器（兼容旧接口，推荐直接使用 check_key()）。."""

    def __init__(self) -> None:
        """初始化键盘监听器。."""
        self._running = False

    def start(self) -> None:
        """标记为运行中。."""
        self._running = True

    def stop(self) -> None:
        """停止监听。."""
        self._running = False

    def is_running(self) -> bool:
        """返回运行状态。."""
        return self._running

    @staticmethod
    def check() -> str | None:
        """检测按键，返回字符或 None。."""
        return check_key()
