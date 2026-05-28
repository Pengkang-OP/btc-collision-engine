"""错误处理工具：with_sync_fallback 装饰器和辅助函数。.

消除 async_executor 中大量重复的 try/except → sync_fallback 样板代码。

v5.2.3: 从 async_executor.py 提取为独立模块（代码质量优化 #M2）。
v5.2.4: 新增 _SyncFallbackHost(Protocol) 接口，消除 4 处 # type: ignore[attr-defined/return-value]。
"""

import functools
from collections.abc import Callable
from contextlib import suppress
from typing import Any, Protocol, TypeVar, cast

from src.utils import get_configured_logger

logger = get_configured_logger("AsyncGPUExecutor.ErrorUtils")

__all__ = ["with_sync_fallback", "safe_release_buffer"]


F = TypeVar("F", bound=Callable[..., Any])


class _SyncFallbackHost(Protocol):
    """Sync fallback 装饰器宿主需要满足的接口协议。.

    声明 with_sync_fallback 装饰器通过 self 访问的所有属性/方法，
    使 mypy 能正确推断类型，无需 type: ignore。
    """

    sync_fallbacks: int

    def _track_sync_fallback(self) -> None: ...

    def _run_batch_sync(
        self,
        seed: Any,
        num_keys: Any,
        program: Any,
        targets_buf: Any,
        num_targets: Any,
    ) -> Any: ...


# 避免循环导入：在运行时延迟导入 _SyncFallbackError


def _get_sync_fallback_error_type() -> type:
    """延迟获取 _SyncFallbackError 类型，避免循环导入。."""
    from ..executor_types import _SyncFallbackError  # type: ignore[import-unlocked]

    return _SyncFallbackError


def with_sync_fallback(
    *,
    message: str = "操作失败",
    error_types: tuple[type[Exception], ...] = (RuntimeError, MemoryError),
) -> Callable[[F], F]:
    """装饰器：拦截 GPU/OpenCL 错误，自动回退到同步模式。.

    被装饰方法必须为 AsyncGPUExecutor 或其子类的实例方法。
    当抛出 **不是 **_SyncFallbackError 的指定异常时，自动：
    1. 记录警告日志
    2. 递增 sync_fallbacks 并调用 _track_sync_fallback
    3. 执行 _run_batch_sync 并返回同步结果

    Args:
        message: 日志消息前缀
        error_types: 要捕获的异常类型元组（默认 RuntimeError, MemoryError）

    """
    SyncFallback = _get_sync_fallback_error_type()  # noqa: N806

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(self: _SyncFallbackHost, *args: Any, **kwargs: Any) -> Any:
            try:
                return func(self, *args, **kwargs)
            except SyncFallback:
                raise  # 已经完成同步回退的结果，直接穿透
            except error_types as e:
                logger.warning(f"{message}: {type(e).__name__}: {e}")
                self.sync_fallbacks += 1
                self._track_sync_fallback()
                # 自动提取标准参数
                seed = _arg_or_kw(args, kwargs, 0, "seed")
                num_keys = _arg_or_kw(args, kwargs, 1, "num_keys")
                program = _arg_or_kw(args, kwargs, 2, "program")
                targets_buf = _arg_or_kw(args, kwargs, 3, "targets_buf")
                num_targets = _arg_or_kw(args, kwargs, 4, "num_targets")
                return self._run_batch_sync(
                    seed,
                    num_keys,
                    program,
                    targets_buf,
                    num_targets,
                )

        return cast(F, wrapper)

    return decorator


def _arg_or_kw(args: tuple[Any, ...], kwargs: dict, idx: int, name: str) -> Any:
    """安全提取位置参数或关键字参数。."""
    if len(args) > idx:
        return args[idx]
    return kwargs.get(name)


def safe_release_buffer(buf_dict: dict, key: str) -> None:
    """安全释放缓冲区字典中的单个 OpenCL buffer（防止孤儿泄漏）。."""
    buf = buf_dict.get(key)
    if buf is not None:
        with suppress(Exception):
            buf.release()
