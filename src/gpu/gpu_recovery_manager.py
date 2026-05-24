"""GPU异常恢复管理器

提供GPU失败时的优雅降级、自动恢复和负载重分配功能。
解决P1-2问题：GPU碰撞引擎异常恢复机制不完善。
"""

# 统一日志获取
import concurrent.futures  # M3修复: 移到文件顶部
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, cast

from ..utils import get_configured_logger

logger = get_configured_logger("GPURecoveryManager")


class GPUFailureType(Enum):
    """GPU失败类型"""

    OUT_OF_MEMORY = "out_of_memory"  # 内存不足
    COMPUTE_ERROR = "compute_error"  # 计算错误
    DEVICE_LOST = "device_lost"  # 设备丢失
    TIMEOUT = "timeout"  # 超时
    UNKNOWN = "unknown"  # 未知错误


class RecoveryStrategy(Enum):
    """恢复策略"""

    RETRY_IMMEDIATE = "retry_immediate"  # 立即重试
    RETRY_WITH_DELAY = "retry_with_delay"  # 延迟重试
    REDUCE_BATCH_SIZE = "reduce_batch_size"  # 减小批次
    REINITIALIZE = "reinitialize"  # 重新初始化
    DISABLE_GPU = "disable_gpu"  # 禁用GPU
    RESET_BATCH_SIZE = "reset_batch_size"  # v4.2.1: 重置批次大小


@dataclass
class GPUFailureRecord:
    """GPU失败记录

    Attributes:
        gpu_id: 发生故障的GPU设备ID
        failure_type: 故障类型枚举（CRASH/TIMEOUT/MEMORY/PERFORMANCE_DEGRADATION等）
        error_message: 故障详细描述或异常消息
        timestamp: 故障发生时间戳（Unix时间，默认field(default_factory=time.time)）

    """

    gpu_id: int
    failure_type: GPUFailureType
    error_message: str
    timestamp: float = field(default_factory=time.time)
    recovery_attempted: bool = False
    recovery_successful: bool = False
    retry_count: int = 0


class GPURecoveryManager:
    """GPU异常恢复管理器

    功能:
    - 检测GPU失败并分类
    - 执行自动恢复策略
    - 重新分配工作负载
    - 优雅降级（排除失败GPU）
    - 触发告警通知

    使用示例:
        recovery_mgr = GPURecoveryManager()

        # GPU失败时调用
        recovery_mgr.handle_gpu_failure(
            gpu_id=0,
            error=exception,
            redistribute_callback=redistribute_work
        )
    """

    __slots__ = (
        "max_retry_count", "retry_delay_seconds", "batch_size_reduction_factor",
        "auto_redistribute", "max_failed_gpus_before_fallback",
        "_max_failure_history_per_gpu",
        "_failed_gpus", "_failed_gpus_lock",
        "_fallback_lock", "_fallback_to_cpu", "_fallback_callback", "_recovery_callback",
        "_failure_history", "_history_lock",
        "_recovery_callbacks",
        "_total_failures", "_successful_recoveries", "_failed_recoveries", "_stats_lock",
        "health_check_timeout", "_health_check_executor",
    )

    def __init__(
        self,
        max_retry_count: int = 3,
        retry_delay_seconds: float = 5.0,
        batch_size_reduction_factor: float = 0.5,
        auto_redistribute: bool = True,
        max_failed_gpus_before_fallback: int | None = None,  # 新增：降级阈值
    ) -> None:
        """初始化恢复管理器

        Args:
            max_retry_count: 最大重试次数
            retry_delay_seconds: 重试延迟（秒）
            batch_size_reduction_factor: 批次缩减因子
            auto_redistribute: 是否自动重新分配负载
            max_failed_gpus_before_fallback: GPU失败数量超过此值时降级到CPU模式

        """
        self.max_retry_count = max_retry_count
        self.retry_delay_seconds = retry_delay_seconds
        self.batch_size_reduction_factor = batch_size_reduction_factor
        self.auto_redistribute = auto_redistribute
        self.max_failed_gpus_before_fallback = max_failed_gpus_before_fallback or 2  # 默认2个

        # 失败历史数量上限（防止内存无限增长）
        self._max_failure_history_per_gpu = 100

        # 失败GPU集合
        self._failed_gpus: set[int] = set()
        self._failed_gpus_lock = threading.Lock()

        # 降级状态（审查修复#1: 添加线程锁保护）
        self._fallback_lock = threading.Lock()
        self._fallback_to_cpu = False
        self._fallback_callback: Callable[..., Any] | None = None
        self._recovery_callback: Callable[..., Any] | None = None  # 恢复回调

        # 失败历史记录
        self._failure_history: dict[int, list] = {}
        self._history_lock = threading.Lock()

        # 恢复回调
        self._recovery_callbacks: dict[int, Callable[..., Any]] = {}

        # H2修复: 统计信息（添加线程保护）
        self._total_failures = 0
        self._successful_recoveries = 0
        self._failed_recoveries = 0
        self._stats_lock = threading.Lock()  # H2修复: 统计信息锁

        # H3修复: 健康检查超时配置
        self.health_check_timeout = 5.0  # 默认5秒超时

        # 健康检查线程池复用：避免每次 _verify_gpu_health 都创建/销毁线程
        self._health_check_executor: concurrent.futures.ThreadPoolExecutor = (
            concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="gpu_health_check")
        )

        logger.info("GPURecoveryManager已初始化")

    def handle_gpu_failure(
        self,
        gpu_id: int,
        error: Exception,
        redistribute_callback: Callable[..., Any] | None = None,
        alert_callback: Callable[..., Any] | None = None,
    ) -> bool:
        """处理GPU失败

        Args:
            gpu_id: GPU设备ID
            error: 捕获的异常
            redistribute_callback: 负载重分配回调
            alert_callback: 告警通知回调

        Returns:
            True表示已处理，False表示需要外部干预

        """
        logger.error(f"GPU {gpu_id} 失败: {type(error).__name__}: {error}")

        # 1. 分类失败类型
        failure_type = self._classify_failure(error)

        # 2. 记录失败
        failure_record = GPUFailureRecord(
            gpu_id=gpu_id, failure_type=failure_type, error_message=str(error),
        )
        self._record_failure(gpu_id, failure_record)

        # 3. 选择恢复策略
        strategy = self._select_recovery_strategy(gpu_id, failure_type)
        logger.info(f"GPU {gpu_id} 恢复策略: {strategy.value}")

        # 4. 执行恢复
        recovery_success = self._execute_recovery(gpu_id, failure_type, strategy)

        failure_record.recovery_attempted = True
        failure_record.recovery_successful = recovery_success

        if recovery_success:
            logger.info("GPU %s 恢复成功", gpu_id)
            # H2修复: 添加线程保护
            with self._stats_lock:
                self._successful_recoveries += 1

            # 从失败列表中移除
            with self._failed_gpus_lock:
                self._failed_gpus.discard(gpu_id)
        else:
            logger.warning("GPU %s 恢复失败", gpu_id)
            # H2修复: 添加线程保护
            with self._stats_lock:
                self._failed_recoveries += 1

            # 标记为失败GPU
            with self._failed_gpus_lock:
                self._failed_gpus.add(gpu_id)

            # 新增：检查是否需要降级到 CPU模式
            self._check_and_trigger_fallback(gpu_id)

            # 5. 重新分配负载
            if self.auto_redistribute and redistribute_callback:
                try:
                    logger.info("GPU %s 正在重新分配负载...", gpu_id)
                    redistribute_callback(gpu_id)
                except Exception as e:
                    logger.error("负载重分配失败: %s", e)

            # 6. 触发告警
            if alert_callback:
                try:
                    alert_callback(gpu_id, failure_type, error)
                except Exception as e:
                    logger.error("告警通知失败: %s", e)

        return True

    def _classify_failure(self, error: Exception) -> GPUFailureType:
        """分类失败类型

        Args:
            error: 异常对象

        Returns:
            失败类型

        """
        error_msg = str(error).lower()

        # 超时（优先检查）
        if isinstance(error, TimeoutError) or "timeout" in error_msg:
            return GPUFailureType.TIMEOUT

        # 内存不足
        if any(
            kw in error_msg
            for kw in [
                "out of memory",
                "oom",
                "memory allocation",
                "cl_mem_object_allocation_failure",
                "insufficient memory",
            ]
        ):
            return GPUFailureType.OUT_OF_MEMORY

        # 计算错误
        if any(
            kw in error_msg
            for kw in [
                "compute error",
                "kernel execution",
                "cl_invalid_value",
                "invalid argument",
                "arithmetic error",
            ]
        ):
            return GPUFailureType.COMPUTE_ERROR

        # 设备丢失
        if any(
            kw in error_msg for kw in ["device lost", "device removed", "cl_invalid_device", "gpu hang"]
        ):
            return GPUFailureType.DEVICE_LOST

        # 未知错误
        return GPUFailureType.UNKNOWN

    def set_fallback_callback(self, callback: Callable[..., Any]) -> None:
        """设置降级到CPU模式的回调函数

        Args:
            callback: 回调函数，签名为 callback(reason: str)

        """
        with self._fallback_lock:
            self._fallback_callback = callback

    def set_recovery_callback(self, callback: Callable[..., Any]) -> None:
        """设置从CPU模式恢复到GPU模式的回调函数

        Args:
            callback: 回调函数，签名为 callback()

        """
        with self._fallback_lock:
            self._recovery_callback = callback

    def _check_and_trigger_fallback(self, gpu_id: int):
        """检查是否需要降级到CPU模式

        当失败GPU数量超过阈值时，触发降级。

        Args:
            gpu_id: 新失败的GPU ID

        """
        with self._failed_gpus_lock:
            failed_count = len(self._failed_gpus)

        # 审查修复#1: 使用降级锁保护状态检查
        with self._fallback_lock:
            should_fallback = (
                failed_count >= self.max_failed_gpus_before_fallback and not self._fallback_to_cpu
            )

        if should_fallback:
            self._trigger_cpu_fallback(
                f"{failed_count}个GPU失败，超过阈值{self.max_failed_gpus_before_fallback}",
            )

    def _trigger_cpu_fallback(self, reason: str):
        """触发降级到CPU模式

        Args:
            reason: 降级原因

        """
        # 审查修复#1: 使用锁保护状态检查和修改
        with self._fallback_lock:
            if self._fallback_to_cpu:
                return  # 已经降级

            self._fallback_to_cpu = True

        logger.critical("🚨 GPU引擎降级到CPU模式: %s", reason)

        # 调用降级回调
        with self._fallback_lock:
            callback = self._fallback_callback

        if callback:
            try:
                callback(reason)
            except Exception as e:
                logger.error("降级回调执行失败: %s", e)

    def recover_from_fallback(self) -> None:
        """从CPU模式恢复到GPU模式

        当GPU恢复正常后调用。
        """
        # 先读取失败GPU数量（_failed_gpus_lock），再检查降级状态（_fallback_lock）
        # 避免与 _check_fallback_threshold 中的锁顺序冲突导致死锁
        with self._failed_gpus_lock:
            should_recover = len(self._failed_gpus) < self.max_failed_gpus_before_fallback

        if not should_recover:
            return

        # 审查修复#1: 使用锁保护状态检查
        with self._fallback_lock:
            if not self._fallback_to_cpu:
                return

            self._fallback_to_cpu = False
            logger.info("[OK] GPU引擎恢复到GPU模式")
            # 保存回调引用
            callback = self._recovery_callback

        # 调用恢复回调（在锁外）
        if should_recover and callback:
            try:
                callback()
            except Exception as e:
                logger.error("恢复回调执行失败: %s", e)

    @property
    def is_fallback_to_cpu(self) -> bool:
        """是否已降级到CPU模式"""
        # 审查修复#1: 使用锁保护状态读取
        with self._fallback_lock:
            return self._fallback_to_cpu

    def _select_recovery_strategy(self, gpu_id: int, failure_type: GPUFailureType) -> RecoveryStrategy:
        """选择恢复策略

        Args:
            gpu_id: GPU ID
            failure_type: 失败类型

        Returns:
            恢复策略

        """
        # 获取该GPU的失败历史
        with self._history_lock:
            failure_count = len(self._failure_history.get(gpu_id, []))

        # 根据失败类型和次数选择策略
        if failure_count <= 1:
            # 第1-2次失败：立即重试
            return RecoveryStrategy.RETRY_IMMEDIATE

        if failure_count == 2:
            # 第3次失败：延迟重试
            return RecoveryStrategy.RETRY_WITH_DELAY

        if failure_count == 3:
            # 第4次失败：减小批次
            return RecoveryStrategy.REDUCE_BATCH_SIZE

        if failure_count < self.max_retry_count:
            # 多次失败：重新初始化
            return RecoveryStrategy.REINITIALIZE

        # 超过最大重试：禁用GPU
        return RecoveryStrategy.DISABLE_GPU

    def _execute_recovery(
        self, gpu_id: int, failure_type: GPUFailureType, strategy: RecoveryStrategy,
    ) -> bool:
        """执行恢复策略

        Args:
            gpu_id: GPU ID
            failure_type: 失败类型
            strategy: 恢复策略

        Returns:
            True表示恢复成功

        """
        try:
            if strategy == RecoveryStrategy.RETRY_IMMEDIATE:
                # H1修复: 立即重试后验证GPU状态
                time.sleep(1.0)
                return self._verify_gpu_health(gpu_id)

            if strategy == RecoveryStrategy.RETRY_WITH_DELAY:
                # H1修复: 延迟重试后验证GPU状态
                logger.info(f"GPU {gpu_id} 延迟 {self.retry_delay_seconds}秒后重试")
                time.sleep(self.retry_delay_seconds)
                return self._verify_gpu_health(gpu_id)

            if strategy == RecoveryStrategy.REDUCE_BATCH_SIZE:
                # M1修复: 减小批次大小后验证GPU状态
                if gpu_id in self._recovery_callbacks:
                    callback = self._recovery_callbacks[gpu_id]
                    callback("reduce_batch_size", self.batch_size_reduction_factor)
                # 验证GPU是否真正恢复
                return self._verify_gpu_health(gpu_id)

            if strategy == RecoveryStrategy.REINITIALIZE:
                # H1修复: 重新初始化后验证GPU状态
                if gpu_id in self._recovery_callbacks:
                    callback = self._recovery_callbacks[gpu_id]
                    result = callback("reinitialize")
                    # 检查初始化结果
                    if result and isinstance(result, dict) and result.get("success"):
                        time.sleep(2.0)
                        return self._verify_gpu_health(gpu_id)
                return False

            if strategy == RecoveryStrategy.DISABLE_GPU:
                # 禁用GPU（无法恢复）
                logger.warning("GPU %s 已达到最大重试次数，标记为禁用", gpu_id)
                return False

            return False

        except Exception as e:
            logger.error("GPU %s 恢复执行失败: %s", gpu_id, e)
            return False

    def _record_failure(self, gpu_id: int, record: GPUFailureRecord):
        """记录失败历史（带容量上限防止内存无限增长）

        Args:
            gpu_id: GPU ID
            record: 失败记录

        """
        with self._history_lock:
            if gpu_id not in self._failure_history:
                self._failure_history[gpu_id] = []
            history = self._failure_history[gpu_id]
            history.append(record)
            # 超过上限时移除最旧的记录
            if len(history) > self._max_failure_history_per_gpu:
                trimmed = history[: -self._max_failure_history_per_gpu]
                del history[: len(history) - self._max_failure_history_per_gpu]
                logger.debug(f"GPU {gpu_id} 失败历史超过上限, 已清理 {len(trimmed)} 条最旧记录")

        # H2修复: 添加线程保护
        with self._stats_lock:
            self._total_failures += 1

        logger.warning(
            f"GPU {gpu_id} 失败记录: {record.failure_type.value} (总计: {self._total_failures})",
        )

    def _verify_gpu_health(self, gpu_id: int, timeout: float | None = None) -> bool:
        """H1/H3/H4修复: 验证GPU是否健康（带超时控制和取消机制）

        通过回调函数执行GPU健康检查，验证GPU是否真正恢复。
        使用超时机制防止健康检查阻塞恢复流程。
        超时时尝试取消future，防止资源泄露。

        Args:
            gpu_id: GPU ID
            timeout: 超时时间（秒），默认使用health_check_timeout

        Returns:
            True表示GPU健康，False表示GPU仍然失败或超时

        """
        if timeout is None:
            timeout = self.health_check_timeout

        if gpu_id in self._recovery_callbacks:
            try:
                callback = self._recovery_callbacks[gpu_id]

                # H3/H4修复: 使用实例级线程池复用，避免每次创建/销毁开销
                future = self._health_check_executor.submit(callback, "health_check")
                try:
                    result = future.result(timeout=timeout)
                except concurrent.futures.TimeoutError:
                    # H4修复: 超时时尝试取消future
                    cancelled = future.cancel()
                    if cancelled:
                        logger.warning(
                            "GPU %s 健康检查超时（%s秒），已取消未执行的任务",
                            gpu_id, timeout,
                        )
                    else:
                        logger.warning(
                            "GPU %s 健康检查超时（%s秒），任务已在运行，无法取消", gpu_id, timeout,
                        )
                    return False

                # 检查结果
                if result is None:
                    # 回调无返回值，假设健康
                    logger.debug("GPU %s 健康检查: 无返回值，假设健康", gpu_id)
                    return True

                if isinstance(result, dict):
                    healthy = result.get("healthy", result.get("success", False))
                    if healthy:
                        logger.debug("GPU %s 健康检查通过", gpu_id)
                    else:
                        logger.warning("GPU %s 健康检查失败", gpu_id)
                    return bool(healthy)

                # 其他类型，转换为bool
                return bool(result)

            except concurrent.futures.CancelledError:
                logger.warning("GPU %s 健康检查已取消", gpu_id)
                return False
            except Exception as e:
                logger.error("GPU %s 健康检查异常: %s", gpu_id, e)
                return False
        else:
            # 没有注册回调，假设健康（向后兼容）
            logger.debug("GPU %s 健康检查: 无回调，假设健康", gpu_id)
            return True

    def register_recovery_callback(self, gpu_id: int, callback: Callable[[str, Any], None]) -> None:
        """注册恢复回调

        Args:
            gpu_id: GPU ID
            callback: 回调函数(action, params)

        """
        self._recovery_callbacks[gpu_id] = callback
        logger.info("GPU %s 恢复回调已注册", gpu_id)

    def is_gpu_failed(self, gpu_id: int) -> bool:
        """检查GPU是否已失败

        Args:
            gpu_id: GPU ID

        Returns:
            True表示GPU已失败并被禁用

        """
        with self._failed_gpus_lock:
            return gpu_id in self._failed_gpus

    def get_failed_gpus(self) -> set[int]:
        """获取所有失败的GPU ID

        Returns:
            失败GPU ID集合

        """
        with self._failed_gpus_lock:
            return self._failed_gpus.copy()

    def get_recovery_stats(self) -> dict:
        """M2修复: 获取恢复统计（一致性快照）

        使用锁保护读取操作，确保统计数据的一致性。

        Returns:
            统计字典

        """
        # M2修复: 添加一致性快照
        with self._stats_lock:
            total = self._total_failures
            successful = self._successful_recoveries
            failed = self._failed_recoveries

        with self._failed_gpus_lock:
            failed_gpus_count = len(self._failed_gpus)

        return {
            "total_failures": total,
            "successful_recoveries": successful,
            "failed_recoveries": failed,
            "failed_gpus": failed_gpus_count,
            "success_rate": (successful / total * 100 if total > 0 else 100.0),
        }

    def reset_failure_history(self, gpu_id: int | None = None) -> None:
        """重置失败历史

        Args:
            gpu_id: GPU ID（None表示重置所有）

        """
        with self._history_lock:
            if gpu_id is None:
                self._failure_history.clear()
            elif gpu_id in self._failure_history:
                del self._failure_history[gpu_id]

        with self._failed_gpus_lock:
            if gpu_id is None:
                self._failed_gpus.clear()
            else:
                self._failed_gpus.discard(gpu_id)

        logger.info(f"GPU {gpu_id or '所有'} 失败历史已重置")

    def reset_batch_size(self, gpu_id: int, initial_batch_size: int) -> None:
        """v4.2.1: 重置GPU的batch_size到初始值

        当性能持续下降时，调用此方法恢复初始batch_size。

        Args:
            gpu_id: GPU ID
            initial_batch_size: 初始batch_size值

        """
        if gpu_id in self._recovery_callbacks:
            callback = self._recovery_callbacks[gpu_id]
            callback("reset_batch_size", initial_batch_size)
            logger.info("GPU %s batch_size已重置为: %s", gpu_id, initial_batch_size)
        else:
            logger.warning("GPU %s 未注册回调，无法重置batch_size", gpu_id)

    def cleanup(self) -> None:
        """清理资源：关闭健康检查线程池

        在 GPURecoveryManager 生命周期结束时调用，确保线程资源正确释放。
        """
        if hasattr(self, "_health_check_executor") and self._health_check_executor is not None:
            try:
                self._health_check_executor.shutdown(wait=True)
                logger.debug("健康检查线程池已关闭")
            except Exception as e:
                logger.warning("关闭健康检查线程池时异常: %s", e)
            self._health_check_executor = None  # type: ignore[assignment]
