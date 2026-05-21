"""内存池管理器共享工具

提供 CPU 内存池 (src.core.memory_pool) 和 GPU 内存池 (src.gpu.memory_pool)
的共享接口和工具，消除双生子架构中的重复代码。

v4.2.4: 从 GlobalPoolManager / GlobalGPUMemoryManager 提取共享模式
"""

import threading
from typing import Any, Protocol, runtime_checkable

from .logging_config import get_configured_logger

_logger = get_configured_logger("PoolHelpers")


# ──────────────────────────── StatsProvider Protocol ────────────────────────────


@runtime_checkable
class StatsProvider(Protocol):
    """统一统计信息提供者接口

    所有内存池对象 (ObjectPool, GPUMemoryPool, ECPointPool, ByteArrayPool,
    GPUBufferAllocator) 及其管理器均实现此接口，确保 get_stats() 返回
    一致的字典结构。
    """

    def get_stats(self) -> dict[str, Any]:
        """返回池统计信息字典"""
        ...

    def get_all_stats(self) -> dict[str, Any]:
        """返回聚合统计信息（管理器级别）"""
        ...


# ──────────────────────────── 自动清理线程管理 ────────────────────────────


class _CleanupThreadState:
    """自动清理线程的状态封装 (避免子类重复声明)"""

    __slots__ = ("_cleanup_thread", "_cleanup_stop_event")

    def __init__(self) -> None:
        self._cleanup_thread: threading.Thread | None = None
        self._cleanup_stop_event = threading.Event()


def start_cleanup_thread(
    state: _CleanupThreadState,
    loop_func: Any,
    interval: float,
    thread_name: str,
    **loop_kwargs: Any,
) -> None:
    """启动自动清理 daemon 线程（幂等）

    参数:
        state: 线程状态封装
        loop_func: 清理循环函数，签名 (interval, **kwargs) -> None
        interval: 清理间隔(秒)
        thread_name: 线程名称
        **loop_kwargs: 传递给 loop_func 的额外参数
    """
    if state._cleanup_thread is not None and state._cleanup_thread.is_alive():
        _logger.debug(f"{thread_name} 已在运行，跳过重复启动")
        return

    state._cleanup_stop_event.clear()
    state._cleanup_thread = threading.Thread(
        target=loop_func,
        args=(interval,),
        kwargs=loop_kwargs,
        daemon=True,
        name=thread_name,
    )
    state._cleanup_thread.start()
    _logger.info(f"{thread_name} 自动清理已启动 (间隔={interval:.0f}s)")


def stop_cleanup_thread(
    state: _CleanupThreadState,
    thread_name: str,
    timeout: float = 5.0,
) -> None:
    """停止自动清理线程（幂等）

    参数:
        state: 线程状态封装
        thread_name: 线程名称（用于日志）
        timeout: 等待线程结束的超时时间(秒)
    """
    if state._cleanup_thread is None or not state._cleanup_thread.is_alive():
        return

    state._cleanup_stop_event.set()
    state._cleanup_thread.join(timeout=timeout)
    if state._cleanup_thread.is_alive():
        _logger.warning(f"{thread_name} 未能在{timeout}s超时内停止")
    else:
        state._cleanup_thread = None
        _logger.info(f"{thread_name} 已停止")


def run_cleanup_loop_safely(
    state: _CleanupThreadState,
    interval: float,
    thread_name: str,
    cleanup_action: Any,
    *,
    on_memory_error: str | None = "break",
) -> None:
    """运行清理循环的安全包装

    参数:
        state: 线程状态封装
        interval: 清理间隔(秒)
        thread_name: 线程名称
        cleanup_action: 每次迭代执行的清理动作，签名 () -> None
        on_memory_error: "break" 停止线程, "continue" 继续运行, None 忽略
    """
    _logger.info(f"{thread_name} 自动清理已启动 (间隔={interval:.0f}s)")
    while not state._cleanup_stop_event.wait(interval):
        try:
            cleanup_action()
        except MemoryError:
            _logger.error(f"{thread_name}: 内存耗尽", exc_info=True)
            if on_memory_error == "break":
                break
        except Exception:
            _logger.error(f"{thread_name} 自动清理异常, 继续运行", exc_info=True)
    _logger.info(f"{thread_name} 自动清理已停止")
