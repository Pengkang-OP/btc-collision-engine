"""Callback timeout protection utility.

Provides decorators and context managers to prevent user callback
functions from blocking the main flow due to timeout.

Features:
- Dual platform: Windows uses thread timeout, Unix uses SIGALRM
- Exception isolation: timeouts and exceptions don't interrupt main
- Unified logging: WARNING level log on timeout

使用示例:
    >>> from src.utils.timeout import with_timeout, TimeoutContext
    >>>
    >>> @with_timeout(5)
    ... def my_callback():
    ...     pass
    >>>
    >>> with TimeoutContext(5):
    ...     my_callback()
"""

import ctypes
import os
import signal
import threading
import time
from collections.abc import Callable
from functools import wraps
from types import TracebackType
from typing import Any

from .logging_config import get_configured_logger

logger = get_configured_logger("TimeoutProtection")


class _TimeoutError(Exception):
    """超时异常，用于信号处理器抛出."""


# ============================================================================
# 线程终止 API（Windows 专用，用于强制中断超时线程）
# ============================================================================


def _terminate_thread(thread_handle: int, exit_code: int = 0) -> bool:
    """Windows: 通过 kernel32.TerminateThread 终止线程（仅作最后手段）.

    注意: TerminateThread 可能导致资源泄漏，
    仅在守护线程超时且无法自行退出时使用。
    """
    if os.name != "nt":
        return False
    try:
        kernel32 = ctypes.windll.kernel32
        result = kernel32.TerminateThread(
            ctypes.c_void_p(thread_handle),
            ctypes.c_ulong(exit_code),
        )
        return bool(result)
    except (OSError, ValueError, AttributeError):
        return False


# ============================================================================
# 线程超时执行器（跨平台通用）
# ============================================================================


def _execute_with_thread_timeout(
    func: Callable[..., Any],
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    timeout: float = 5.0,
    callback_name: str = "",
) -> bool:
    """在独立线程中执行函数，带超时控制.

    启动守护线程执行目标函数，主线程等待最多 timeout 秒。
    超时后返回 False，不中断主流程。

    Args:
        func: 要执行的函数
        args: 位置参数
        kwargs: 关键字参数
        timeout: 超时时间（秒）
        callback_name: 回调名称（用于日志）

    Returns:
        True 表示执行成功，False 表示超时或异常

    """
    if kwargs is None:
        kwargs = {}

    exception: list[BaseException | None] = [None]
    completed: list[bool] = [False]

    def target() -> None:
        try:
            func(*args, **kwargs)
        except Exception as e:
            exception[0] = e
        finally:
            completed[0] = True

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        thread_info = f"name={thread.name}, ident={thread.ident}, native_id={thread.native_id}"
        logger.warning(
            "回调执行超时 (%s秒) - 回调: %s - 线程: %s",
            timeout,
            callback_name,
            thread_info,
        )
        return False

    if exception[0]:
        logger.warning(
            f"回调执行异常 - 回调: {callback_name} - "
            f"异常: {type(exception[0]).__name__}: {exception[0]}",
        )
        return False

    return True


# ============================================================================
# SIGALRM 超时执行器（Unix 专用）
# ============================================================================


def _execute_with_sigalrm_timeout(
    func: Callable[..., Any],
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    timeout: float = 5.0,
    callback_name: str = "",
) -> bool:
    """使用 SIGALRM 信号执行函数，带超时控制.

    仅适用于 Unix 系统。设置 alarm 信号处理器，在超时时抛出 _TimeoutError。

    Args:
        func: 要执行的函数
        args: 位置参数
        kwargs: 关键字参数
        timeout: 超时时间（秒）
        callback_name: 回调名称（用于日志）

    Returns:
        True 表示执行成功，False 表示超时或异常

    """
    if kwargs is None:
        kwargs = {}

    def _timeout_handler(_signum: int, _frame: object) -> None:
        raise _TimeoutError(f"回调执行超时 ({timeout}秒) - 回调: {callback_name}")

    retry_count = 0
    max_retries = 3

    while retry_count < max_retries:
        try:
            # 使用 getattr 避免 Windows 上 signal.SIGALRM/setitimer 不存在的类型错误
            sigalrm = getattr(signal, "SIGALRM", None)
            setitimer = getattr(signal, "setitimer", None)
            if sigalrm is None or setitimer is None:
                logger.warning("SIGALRM 超时不可用，回退到线程超时")
                return _execute_with_thread_timeout(
                    func,
                    args,
                    kwargs,
                    timeout,
                    callback_name,
                )

            old_handler = signal.signal(sigalrm, _timeout_handler)
            setitimer(signal.ITIMER_REAL, timeout)  # type: ignore[attr-defined]  # Unix-only
            try:
                func(*args, **kwargs)
                return True
            except _TimeoutError:
                logger.warning(
                    f"回调执行超时 ({timeout}秒) - 回调: {callback_name} - "
                    f"线程: {threading.current_thread().name}",
                )
                return False
            except Exception as e:
                logger.warning(
                    "回调执行异常 - 回调: %s - 异常: %s: %s",
                    callback_name,
                    type(e).__name__,
                    e,
                )
                return False
            finally:
                setitimer(signal.ITIMER_REAL, 0.0)  # type: ignore[attr-defined]  # Unix-only
                signal.signal(# Unix-only
                    signal.SIGALRM,  # type: ignore[attr-defined]  # Unix-only
                    old_handler,
                )
        except (ValueError, OSError, AttributeError) as e:
            retry_count += 1
            if retry_count >= max_retries:
                logger.warning(
                    "SIGALRM 超时执行重试耗尽 (%s次) - 回调: %s - 错误: %s",
                    max_retries,
                    callback_name,
                    e,
                )
                return False
            time.sleep(0.1)

    return False


# ============================================================================
# 统一超时执行入口
# ============================================================================


def invoke_with_timeout(
    func: Callable[..., Any],
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    timeout: float = 5.0,
    callback_name: str = "",
) -> bool:
    """带超时控制的函数调用（跨平台统一入口）.

    自动选择最优超时策略:
    - Windows: 线程超时（threading.Thread + join timeout）
    - Unix: SIGALRM 信号超时（支持嵌套调用）

    Args:
        func: 要执行的函数
        args: 位置参数
        kwargs: 关键字参数
        timeout: 超时时间（秒），默认 5 秒
        callback_name: 回调名称（用于日志，推荐传入）

    Returns:
        True 表示执行成功，False 表示超时或异常

    """
    if timeout <= 0:
        return False

    if os.name == "nt":
        return _execute_with_thread_timeout(
            func,
            args,
            kwargs,
            timeout,
            callback_name,
        )
    # SIGALRM 仅主线程可用；非主线程回退到线程超时
    if (
        hasattr(signal, "SIGALRM")
        and hasattr(signal, "setitimer")
        and threading.current_thread() is threading.main_thread()
    ):
        return _execute_with_sigalrm_timeout(
            func,
            args,
            kwargs,
            timeout,
            callback_name,
        )
    return _execute_with_thread_timeout(
        func,
        args,
        kwargs,
        timeout,
        callback_name,
    )


# ============================================================================
# 公共 API
# ============================================================================


def with_timeout(seconds: float) -> Any:
    """超时装饰器工厂.

    在独立线程中执行被装饰函数，超时则记录 WARNING 日志并静默返回。

    注意: 此装饰器会改变函数调用方式，被装饰函数的返回值将被忽略。
    适用于无返回值的回调函数（如 on_progress, on_match）。

    Args:
        seconds: 超时时间（秒）

    Returns:
        装饰器函数

    使用示例:
        >>> @with_timeout(5)
        ... def my_handler(stats):
        ...     time.sleep(10)  # 超过5秒
        ...     print(stats)
        >>>
        >>> my_handler(some_stats)  # 超时后记录 WARNING，不阻塞

    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> None:
            callback_name = getattr(func, "__qualname__", func.__name__)
            _ = invoke_with_timeout(
                func,
                args,
                kwargs,
                timeout=seconds,
                callback_name=callback_name,
            )

        return wrapper

    return decorator


class TimeoutContext:
    """超时上下文管理器.

    在上下文内执行的代码块受到超时保护。
    超时时不抛出异常，而是静默退出上下文。

    支持跨平台:
    - Windows: 线程超时
    - Unix: SIGALRM 信号超时

    使用示例:
        >>> with TimeoutContext(5, name="handle_match"):
        ...     user_callback(private_key, address, wif)
        ... # 超时后静默退出，不会阻塞
    """

    def __init__(self, seconds: float, name: str = "") -> None:
        """Initialize timeout context.

        Args:
            seconds: 超时时间（秒）
            name: 上下文名称（用于日志）

        """
        self._seconds: float = seconds
        self._name: str = name or "unnamed"
        self._start_time: float = 0.0

    def __enter__(self) -> "TimeoutContext":
        """Enter timeout context."""
        self._start_time = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Exit timeout context."""
        elapsed_ms = (time.perf_counter() - self._start_time) * 1000

        if exc_type is not None:
            logger.warning(
                f"上下文执行异常 [{self._name}] {exc_type.__name__}: "
                f"{exc_val} (耗时 {elapsed_ms:.1f}ms)",
            )
            return True

        if elapsed_ms > self._seconds * 1000:
            logger.warning(
                f"上下文执行可能超时 [{self._name}] "
                f"(耗时 {elapsed_ms:.1f}ms, 阈值 {self._seconds * 1000:.0f}ms)",
            )

        return True

    @property
    def elapsed_ms(self) -> float:
        """获取上下文已耗时（毫秒）."""
        return (time.perf_counter() - self._start_time) * 1000
