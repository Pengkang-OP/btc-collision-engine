"""Error recovery strategy framework.

Provides unified retry, degrade, and skip strategies for:
- Temporary I/O errors (disk full, file lock, network timeout)
- GPU device temporary unavailability (resource, timeout, device
  loss)
- Temporary memory insufficiency (can degrade gracefully)
- 配置加载失败（回退到默认值）

核心组件:
- @retry_on_error: 带指数退避的函数重试装饰器
- FallbackStrategy: 定义降级方案的分层策略
- ErrorRecoveryManager: 统一管理恢复策略的状态机

设计原则 (DEF-2):
1. 非侵入式: 通过装饰器即可为现有函数添加恢复能力
2. 可组合: 策略可嵌套、可叠加
3. 可观测: 所有恢复过程记录到日志
4. 线程安全: 管理器使用锁保护共享状态
"""

import functools
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

from .logging_config import get_configured_logger

logger = get_configured_logger("ErrorRecovery")

F = TypeVar("F", bound=Callable[..., Any])

RANDOM_SEEDED = False


def _ensure_random_seed() -> None:
    global RANDOM_SEEDED
    if not RANDOM_SEEDED:
        random.seed()
        RANDOM_SEEDED = True


class RecoverableErrorCategory(Enum):
    """可恢复错误类别."""

    TEMPORARY_IO = "temporary_io"
    GPU_RESOURCE = "gpu_resource"
    GPU_TIMEOUT = "gpu_timeout"
    GPU_DEVICE_LOST = "gpu_device_lost"
    MEMORY_TEMPORARY = "memory_temporary"
    NETWORK_TIMEOUT = "network_timeout"
    CONFIG_LOAD = "config_load"


class RecoveryAction(Enum):
    """恢复动作."""

    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    DEGRADE = "degrade"
    ABORT = "abort"


# 可恢复错误类型映射
# W2修复: 移除 RuntimeError 全局映射（过于宽泛），仅依赖关键字匹配
RECOVERABLE_ERROR_MAP: dict[type[Exception], RecoverableErrorCategory] = {
    TimeoutError: RecoverableErrorCategory.NETWORK_TIMEOUT,
    ConnectionError: RecoverableErrorCategory.NETWORK_TIMEOUT,
    OSError: RecoverableErrorCategory.TEMPORARY_IO,
    PermissionError: RecoverableErrorCategory.TEMPORARY_IO,
    MemoryError: RecoverableErrorCategory.MEMORY_TEMPORARY,
}


# 错误消息关键字 → 类别映射
ERROR_KEYWORD_CATEGORY: list[tuple[list[str], RecoverableErrorCategory]] = [
    (
        [
            "out of resources",
            "cl_out_of_resources",
            "cl_mem_object_allocation_failure",
            "allocation failed",
            "insufficient",
            "resource exhausted",
        ],
        RecoverableErrorCategory.GPU_RESOURCE,
    ),
    (
        ["timeout", "timed out", "cl_kernel_timeout"],
        RecoverableErrorCategory.GPU_TIMEOUT,
    ),
    (
        ["device lost", "device removed", "cl_invalid_device", "gpu hang"],
        RecoverableErrorCategory.GPU_DEVICE_LOST,
    ),
    (
        ["disk full", "no space left", "enospc"],
        RecoverableErrorCategory.TEMPORARY_IO,
    ),
    (
        ["out of memory", "oom", "memory allocation"],
        RecoverableErrorCategory.MEMORY_TEMPORARY,
    ),
    (
        ["connection refused", "connection reset", "network unreachable"],
        RecoverableErrorCategory.NETWORK_TIMEOUT,
    ),
]


def _sanitize_error_message(message: str) -> str:
    """对错误消息进行脱敏处理.

    移除可能泄漏的敏感信息（私钥、WIF、完整地址等），
    同时截断过长消息以避免日志膨胀。

    Args:
        message: 原始错误消息

    Returns:
        脱敏后的错误消息

    """
    import re

    _max_message_length = 500

    if len(message) > _max_message_length:
        message = message[:_max_message_length] + "...[truncated]"

    # 匹配 base58 WIF 私钥 (以 5/H/K/L 开头, 51-52 字符)
    _wif_pattern = r"\b[5HKL][1-9A-HJ-NP-Za-km-z]{50,51}\b"
    message = re.sub(_wif_pattern, "[MASKED_WIF]", message)

    # 匹配 64 字符十六进制私钥
    # 注意: SHA-256 哈希值也是 64 字符 hex，掩码标签需区分以利回溯
    message = re.sub(r"\b[0-9a-fA-F]{64}\b", "[MASKED_64CHAR_HEX]", message)

    return message


def classify_recoverable_error(
    error: Exception,
) -> RecoverableErrorCategory | None:
    """分类可恢复的错误.

    先按错误消息关键字匹配（细粒度），再按异常类型匹配（粗粒度兜底）。

    Args:
        error: 被捕获的异常

    Returns:
        RecoverableErrorCategory 或 None（不可恢复）

    """
    if isinstance(error, (SystemExit, KeyboardInterrupt)):
        return None

    error_msg = str(error).lower()
    for keywords, category in ERROR_KEYWORD_CATEGORY:
        if any(kw in error_msg for kw in keywords):
            return category

    # 使用 isinstance() 而非 type() 精确匹配，以支持子类异常
    # 例如: ConnectionRefusedError → ConnectionError, FileNotFoundError → OSError
    for exc_type, category in RECOVERABLE_ERROR_MAP.items():
        if isinstance(error, exc_type):
            return category

    return None


def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    recoverable_only: bool = True,
    on_retry: Callable[[Exception, int, float], None] | None = None,
) -> Callable[[F], F]:
    """带指数退避和抖动的函数重试装饰器.

    Args:
        max_retries: 最大重试次数（不含首次调用）
        delay: 初始延迟（秒）
        backoff: 退避因子（每次重试将延迟乘以该因子）
        max_delay: 最大延迟上限（秒）
        jitter: 是否添加随机抖动（±25%），避免惊群效应
        recoverable_only: True=仅重试可恢复错误，False=重试所有错误
        on_retry: 重试时的回调函数，签名为(error, attempt, next_delay)

    Returns:
        装饰后的函数

    使用示例:
        @retry_on_error(max_retries=3, delay=1.0, backoff=2.0)
        def fragile_io_operation(filepath):
            ...

    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            _ensure_random_seed()
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if isinstance(e, (SystemExit, KeyboardInterrupt)):
                        raise

                    if recoverable_only:
                        category = classify_recoverable_error(e)
                        if category is None:
                            raise

                    if attempt >= max_retries:
                        break

                    sleep_time = min(delay * (backoff**attempt), max_delay)
                    if jitter:
                        jitter_factor = 0.75 + random.SystemRandom().random() * 0.5  # nosec B311
                        sleep_time *= jitter_factor

                    logger.warning(
                        f"{func.__name__} 第{attempt + 1}次重试 "
                        f"(错误: {type(e).__name__}: "
                        f"{_sanitize_error_message(str(e))}, "
                        f"延迟: {sleep_time:.2f}s)",
                    )

                    if on_retry:
                        try:
                            on_retry(e, attempt + 1, sleep_time)
                        except Exception as cb_err:
                            logger.debug("重试回调异常: %s", cb_err)

                    time.sleep(sleep_time)

            if last_exception is None:
                raise RuntimeError(
                    "error_recovery: last_exception is None after retry loop",
                )
            raise last_exception

        return wrapper

    return decorator


@dataclass
class RetryRecord:
    """重试记录."""

    error_type: str
    error_message: str
    attempt: int
    timestamp: float = field(default_factory=time.time)
    success: bool = False


@dataclass
class RecoveryStats:
    """恢复统计."""

    total_errors: int = 0
    total_retries: int = 0
    successful_retries: int = 0
    failed_retries: int = 0
    fallbacks_triggered: int = 0
    skips_triggered: int = 0
    degrades_triggered: int = 0

    @property
    def retry_success_rate(self) -> float:
        """Get retry success rate as percentage."""
        if self.total_retries == 0:
            return 100.0
        return self.successful_retries / self.total_retries * 100


class FallbackStrategy:
    """降级策略定义.

    提供分层降级方案，当前方案失败后自动切换到下一层。

    使用示例:
        strategy = FallbackStrategy("gpu_batch")
        strategy.add_fallback("reduce_batch", lambda: set_batch_size(1000))
        strategy.add_fallback("switch_device", lambda: switch_to_device(1))
        strategy.add_fallback("cpu_fallback", lambda: enable_cpu_mode())
    """

    def __init__(self, name: str) -> None:
        """Initialize fallback strategy.

        Args:
            name: Strategy name

        """
        self.name = name
        self._fallbacks: list[tuple[str, Callable[[], Any]]] = []

    def add_fallback(self, label: str, action: Callable[[], Any]) -> "FallbackStrategy":
        """Add a fallback action.

        Args:
            label: Action label
            action: Callable action

        Returns:
            Self for chaining

        """
        self._fallbacks.append((label, action))
        return self

    def execute(self) -> tuple[bool, str | None]:
        """顺序执行降级方案，直到某个成功.

        Returns:
            (是否成功, 最终执行的方案标签)

        """
        for label, action in self._fallbacks:
            logger.info(f"执行降级策略 [{self.name}]: {label}")
            try:
                action()
                logger.info(f"降级策略 [{self.name}] {label} 成功")
                return True, label
            except Exception as e:
                logger.warning(f"降级策略 [{self.name}] {label} 失败: {e}")

        logger.error(f"降级策略 [{self.name}] 所有方案均失败")
        return False, None

    @property
    def fallback_count(self) -> int:
        """Get number of registered fallbacks."""
        return len(self._fallbacks)


class ErrorRecoveryManager:
    """统一错误恢复管理器.

    管理重试状态、降级策略执行和统计信息。
    线程安全：所有状态操作使用锁保护。

    功能:
    - 为不同错误类别注册降级策略
    - 追踪重试历史，防止无限重试
    - 自动根据错误类别选择恢复动作
    - 收集并导出恢复统计

    使用示例:
        recovery = ErrorRecoveryManager()

        # 注册 GPU 资源不足的降级策略
        fs = FallbackStrategy("gpu_resource")
        fs.add_fallback("reduce_batch", lambda: gpu_device.reduce_batch(0.5))
        fs.add_fallback("reinit", lambda: gpu_device.reinitialize())
        recovery.register_fallback(RecoverableErrorCategory.GPU_RESOURCE, fs)

        # 应用装饰器
        @recovery.recoverable(
            max_retries=3, category=RecoverableErrorCategory.GPU_RESOURCE,
        )
        def run_gpu_batch(seed, batch_size):
            ...
    """

    MAX_HISTORY_PER_CATEGORY = 200

    def __init__(self, name: str = "default") -> None:
        """Initialize error recovery manager.

        Args:
            name: Manager name

        """
        self.name = name
        self._fallbacks: dict[RecoverableErrorCategory, FallbackStrategy] = {}
        self._lock = threading.RLock()
        self._stats = RecoveryStats()
        self._retry_history: dict[RecoverableErrorCategory, list[RetryRecord]] = {}
        self._disabled_categories: set[RecoverableErrorCategory] = set()

    def register_fallback(
        self,
        category: RecoverableErrorCategory,
        strategy: FallbackStrategy,
    ) -> None:
        """Register a fallback strategy for an error category.

        Args:
            category: Error category
            strategy: Fallback strategy

        """
        with self._lock:
            self._fallbacks[category] = strategy
            logger.debug(
                f"[{self.name}] 注册 {category.value} 降级策略: {strategy.name}",
            )

    def get_fallback(self, category: RecoverableErrorCategory) -> FallbackStrategy | None:
        """Get fallback strategy for an error category.

        Args:
            category: Error category

        Returns:
            FallbackStrategy or None

        """
        with self._lock:
            return self._fallbacks.get(category)

    def record_retry(
        self,
        category: RecoverableErrorCategory,
        error: Exception,
        attempt: int,
        success: bool,
    ) -> None:
        """Record a retry attempt.

        Args:
            category: Error category
            error: Exception that occurred
            attempt: Attempt number
            success: Whether the attempt succeeded

        """
        record = RetryRecord(
            error_type=type(error).__name__,
            error_message=_sanitize_error_message(str(error)),
            attempt=attempt,
            success=success,
        )
        with self._lock:
            if category not in self._retry_history:
                self._retry_history[category] = []
            history = self._retry_history[category]
            history.append(record)
            if len(history) > self.MAX_HISTORY_PER_CATEGORY:
                trimmed = len(history) - self.MAX_HISTORY_PER_CATEGORY
                del history[:trimmed]

            self._stats.total_errors += 1
            if attempt > 0:
                self._stats.total_retries += 1
                if success:
                    self._stats.successful_retries += 1
                else:
                    self._stats.failed_retries += 1

    def record_action(self, action: RecoveryAction) -> None:
        """Record a recovery action.

        Args:
            action: Recovery action type

        """
        with self._lock:
            if action == RecoveryAction.FALLBACK:
                self._stats.fallbacks_triggered += 1
            elif action == RecoveryAction.SKIP:
                self._stats.skips_triggered += 1
            elif action == RecoveryAction.DEGRADE:
                self._stats.degrades_triggered += 1

    def execute_fallback(self, category: RecoverableErrorCategory) -> tuple[bool, str | None]:
        """Execute fallback strategy for an error category.

        Args:
            category: Error category

        Returns:
            (success, label) tuple

        """
        strategy = self.get_fallback(category)
        if strategy is None:
            logger.warning(f"[{self.name}] {category.value} 无已注册的降级策略")
            return False, None

        self.record_action(RecoveryAction.FALLBACK)
        return strategy.execute()

    def disable_category(self, category: RecoverableErrorCategory) -> None:
        """Disable recovery for an error category.

        Args:
            category: Error category to disable

        """
        with self._lock:
            self._disabled_categories.add(category)
            logger.info(f"[{self.name}] {category.value} 恢复策略已禁用")

    def enable_category(self, category: RecoverableErrorCategory) -> None:
        """Enable recovery for an error category.

        Args:
            category: Error category to enable

        """
        with self._lock:
            self._disabled_categories.discard(category)
            logger.info(f"[{self.name}] {category.value} 恢复策略已启用")

    def is_category_disabled(self, category: RecoverableErrorCategory) -> bool:
        """Check if recovery is disabled for a category.

        Args:
            category: Error category

        Returns:
            True if disabled

        """
        with self._lock:
            return category in self._disabled_categories

    def get_stats(self) -> RecoveryStats:
        """Get recovery statistics.

        Returns:
            RecoveryStats instance

        """
        with self._lock:
            return RecoveryStats(
                total_errors=self._stats.total_errors,
                total_retries=self._stats.total_retries,
                successful_retries=self._stats.successful_retries,
                failed_retries=self._stats.failed_retries,
                fallbacks_triggered=self._stats.fallbacks_triggered,
                skips_triggered=self._stats.skips_triggered,
                degrades_triggered=self._stats.degrades_triggered,
            )

    def get_history(self, category: RecoverableErrorCategory | None = None) -> dict:
        """Get retry history.

        Args:
            category: Optional category filter

        Returns:
            History dictionary

        """
        with self._lock:
            if category is not None:
                records = self._retry_history.get(category, [])
                return {
                    "category": category.value,
                    "total": len(records),
                    "recent": [
                        {
                            "error_type": r.error_type,
                            "error_message": r.error_message[:200],
                            "attempt": r.attempt,
                            "success": r.success,
                            "timestamp": r.timestamp,
                        }
                        for r in records[-10:]
                    ],
                }

            result = {}
            for cat, records in self._retry_history.items():
                result[cat.value] = {
                    "total": len(records),
                    "recent": [
                        {
                            "error_type": r.error_type,
                            "error_message": r.error_message[:200],
                            "attempt": r.attempt,
                            "success": r.success,
                            "timestamp": r.timestamp,
                        }
                        for r in records[-5:]
                    ],
                }
            return result

    def reset_stats(self) -> None:
        """Reset recovery statistics."""
        with self._lock:
            self._stats = RecoveryStats()
            logger.info(f"[{self.name}] 恢复统计已重置")

    def reset_history(self, category: RecoverableErrorCategory | None = None) -> None:
        """Reset retry history.

        Args:
            category: Optional category to reset (None resets all)

        """
        with self._lock:
            if category is not None:
                self._retry_history.pop(category, None)
            else:
                self._retry_history.clear()
            logger.info(f"[{self.name}] 重试历史已重置")

    def recoverable(  # noqa: C901
        self,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        max_delay: float = 60.0,
        category: RecoverableErrorCategory | None = None,
    ) -> Callable[[F], F]:
        """实例方法的装饰器：为函数添加重试和降级能力.

        与 @retry_on_error 的区别：
        - 自动记录重试历史到管理器
        - 重试耗尽后自动触发降级策略
        - 尊重 disabled_categories 设置

        Args:
            max_retries: 最大重试次数
            delay: 初始延迟
            backoff: 退避因子
            max_delay: 最大延迟
            category: 错误类别（None=自动检测）

        Returns:
            装饰后的函数

        """
        manager = self

        def decorator(func: F) -> F:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                _ensure_random_seed()
                last_exception: Exception | None = None
                resolved_category: RecoverableErrorCategory | None = category

                for attempt in range(max_retries + 1):
                    try:
                        result = func(*args, **kwargs)
                        if resolved_category is not None and attempt > 0:
                            if last_exception is None:
                                raise RuntimeError(
                                    "last_exception not set for retry recording",
                                )
                            manager.record_retry(
                                resolved_category,
                                last_exception,
                                attempt,
                                True,
                            )
                        return result
                    except Exception as e:
                        last_exception = e

                        if isinstance(e, (SystemExit, KeyboardInterrupt)):
                            raise

                        if resolved_category is None:
                            resolved_category = classify_recoverable_error(e)

                        if resolved_category is None:
                            raise

                        if manager.is_category_disabled(resolved_category):
                            logger.debug(
                                f"[{manager.name}] {func.__name__} "
                                f"类别 {resolved_category.value} 已禁用，跳过重试",
                            )
                            raise

                        if attempt >= max_retries:
                            break

                        sleep_time = min(
                            delay * (backoff**attempt),
                            max_delay,
                        )
                        jitter_factor = 0.75 + random.SystemRandom().random() * 0.5  # nosec B311
                        sleep_time *= jitter_factor

                        logger.warning(
                            f"[{manager.name}] {func.__name__} "
                            f"第{attempt + 1}次重试 "
                            f"({resolved_category.value}, "
                            f"{type(e).__name__}: "
                            f"{_sanitize_error_message(str(e))}, "
                            f"延迟: {sleep_time:.2f}s)",
                        )

                        time.sleep(sleep_time)

                if last_exception is None:
                    raise RuntimeError(
                        "error_recovery: last_exception is None after retry loop",
                    )
                manager.record_retry(
                    resolved_category,
                    last_exception,
                    max_retries,
                    False,
                )

                if resolved_category is not None:
                    fallback_ok, fallback_label = manager.execute_fallback(
                        resolved_category,
                    )
                    if fallback_ok:
                        try:
                            result = func(*args, **kwargs)
                            logger.info(
                                f"[{manager.name}] {func.__name__} "
                                f"降级后重试成功 (方案: {fallback_label})",
                            )
                            return result
                        except Exception as fb_err:
                            logger.error(
                                f"[{manager.name}] {func.__name__} 降级后重试也失败: {fb_err}",
                            )
                            raise fb_err

                raise last_exception

            return wrapper

        return decorator


# 全局默认恢复管理器实例
_default_recovery_manager: ErrorRecoveryManager | None = None
_default_recovery_lock = threading.Lock()


def get_default_recovery_manager() -> ErrorRecoveryManager:
    """获取全局默认恢复管理器（懒初始化，线程安全）."""
    global _default_recovery_manager
    if _default_recovery_manager is None:
        with _default_recovery_lock:
            if _default_recovery_manager is None:
                _default_recovery_manager = ErrorRecoveryManager(name="global")
                logger.info("全局默认恢复管理器已初始化")
    return _default_recovery_manager
