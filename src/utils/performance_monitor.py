"""Enhanced performance monitoring module.

Provides systematic performance monitoring including:
- Operation duration tracking
- 性能瓶颈识别
- 性能趋势分析
- 性能告警
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""

    operation: str
    elapsed_ms: float
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error: str | None = None
    metadata: dict = field(default_factory=dict)


class PerformanceTracker:
    """性能追踪器

    记录和追踪性能指标，支持统计分析
    """

    def __init__(self, max_records: int = 10000) -> None:
        """Args:
        max_records: 最大记录数（超过后自动清理旧记录）

        """
        self.max_records = max_records
        self._records: list[PerformanceMetrics] = []
        self._lock = threading.Lock()

    def record(
        self,
        operation: str,
        elapsed_ms: float,
        success: bool = True,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录性能指标

        Args:
            operation: 操作名称
            elapsed_ms: 耗时（毫秒）
            success: 是否成功
            error: 错误信息（如果失败）
            metadata: 额外元数据

        """
        metric = PerformanceMetrics(
            operation=operation,
            elapsed_ms=elapsed_ms,
            success=success,
            error=error,
            metadata=metadata or {},
        )

        with self._lock:
            self._records.append(metric)

            # 清理旧记录（使用del避免列表切片的内存峰值）
            if len(self._records) > self.max_records:
                # 删除最旧的记录，保留最新的max_records条
                excess = len(self._records) - self.max_records
                del self._records[:excess]

    def get_statistics(self, operation: str | None = None) -> dict:
        """获取性能统计

        Args:
            operation: 操作名称（None=全部）

        Returns:
            统计字典

        """
        with self._lock:
            records = self._records
            if operation:
                records = [r for r in records if r.operation == operation]

        if not records:
            return {
                "count": 0,
                "avg_ms": 0,
                "min_ms": 0,
                "max_ms": 0,
                "p50_ms": 0,
                "p95_ms": 0,
                "p99_ms": 0,
                "success_rate": 0,
            }

        elapsed_list = [r.elapsed_ms for r in records]
        elapsed_list.sort()

        success_count = sum(1 for r in records if r.success)

        return {
            "count": len(records),
            "avg_ms": sum(elapsed_list) / len(elapsed_list),
            "min_ms": min(elapsed_list),
            "max_ms": max(elapsed_list),
            "p50_ms": elapsed_list[len(elapsed_list) // 2],
            "p95_ms": elapsed_list[int(len(elapsed_list) * 0.95)],
            "p99_ms": elapsed_list[int(len(elapsed_list) * 0.99)],
            "success_rate": success_count / len(records),
        }

    def get_slow_operations(
        self, threshold_ms: float = 1000, limit: int = 10,
    ) -> list[PerformanceMetrics]:
        """获取慢操作记录

        Args:
            threshold_ms: 耗时阈值（毫秒）
            limit: 返回数量限制

        Returns:
            慢操作记录列表

        """
        with self._lock:
            slow_ops = [r for r in self._records if r.elapsed_ms > threshold_ms]
            slow_ops.sort(key=lambda x: x.elapsed_ms, reverse=True)
            return slow_ops[:limit]

    def clear(self) -> None:
        """清空所有记录"""
        with self._lock:
            self._records.clear()


# 全局性能追踪器实例
_global_tracker = None
_tracker_lock = threading.Lock()


def _get_tracker_config():
    """从配置获取追踪器配置"""
    try:
        from ..config.config_manager import ConfigManager

        config_mgr = ConfigManager()
        return {
            "enabled": config_mgr.get("performance_monitoring.enabled", True),
            "max_records": config_mgr.get("performance_monitoring.max_records", 10000),
            "slow_threshold_ms": config_mgr.get("performance_monitoring.slow_threshold_ms", 30000),
            "track_slow_operations": config_mgr.get(
                "performance_monitoring.track_slow_operations", True,
            ),
            "log_level": config_mgr.get("performance_monitoring.log_level", "INFO"),
        }
    except Exception as e:
        # 配置加载失败，使用默认值并记录警告日志
        logger.warning(f"性能监控配置加载失败，使用默认值: {type(e).__name__}: {e}")
        return {
            "enabled": True,
            "max_records": 10000,
            "slow_threshold_ms": 30000,
            "_comment_slow_threshold_ms": "GPU内核编译通常需要10-30秒，默认30000ms以避免编译期误报",
            "track_slow_operations": True,
            "log_level": "INFO",
        }


def get_performance_tracker() -> PerformanceTracker:
    """获取全局性能追踪器（单例模式，支持配置）"""
    global _global_tracker

    if _global_tracker is None:
        # 先在锁外获取配置，避免在持有锁时执行可能失败的操作
        try:
            config = _get_tracker_config()
        except (OSError, ValueError, RuntimeError, ImportError):
            # 配置获取失败时使用默认值
            config = {"max_records": 10000}

        with _tracker_lock:
            if _global_tracker is None:  # 双重检查
                _global_tracker = PerformanceTracker(max_records=config["max_records"])

    return _global_tracker


def is_performance_monitoring_enabled() -> bool:
    """检查性能监控是否启用"""
    config = _get_tracker_config()
    return config["enabled"]


class EnhancedPerformanceMonitor:
    """增强型性能监控上下文管理器

    用法:
        with EnhancedPerformanceMonitor(logger, "GPU内核编译") as pm:
            program = compile_kernel()
            pm.add_metadata('kernel_size', size)

    嵌套监控说明:
        支持嵌套使用，内层和外层监控独立记录。
        如果内层抛出异常：
        1. 内层监控会记录为FAILED
        2. 异常继续传播到外层
        3. 外层监控也会记录为FAILED

        示例:
            with EnhancedPerformanceMonitor(logger, "外层操作", level="INFO"):
                with EnhancedPerformanceMonitor(logger, "内层操作", level="DEBUG"):
                    do_something()  # 如果这里抛出异常
                # 内层记录: [Performance] 内层操作: FAILED after Xms
            # 外层记录: [Performance] 外层操作: FAILED after Yms
    """

    def __init__(
        self,
        logger: logging.Logger,
        operation: str,
        level: str = "INFO",
        log_result: bool = True,
        track: bool = True,
    ) -> None:
        """Args:
        logger: 日志记录器
        operation: 操作名称
        level: 日志级别
        log_result: 是否记录日志
        track: 是否记录到性能追踪器
            - True: 记录到全局追踪器，支持统计分析（默认）
            - False: 仅记录日志，不存储到追踪器（适用于调试操作）

        """
        self.logger = logger
        self.operation = operation
        self.level = getattr(logging, level.upper())
        self.log_result = log_result
        self.track = track
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.metadata: dict[str, Any] = {}

    def __enter__(self) -> "EnhancedPerformanceMonitor":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any | None) -> None:
        """退出上下文时的处理

        注意: 此方法中的所有异常都被捕获，确保监控失败不会影响业务逻辑
        """
        try:
            # 检查性能监控是否启用
            if not is_performance_monitoring_enabled():
                return

            self.end_time = time.perf_counter()
            if self.start_time is None:
                raise RuntimeError("PerformanceMonitor 未正确进入上下文: start_time 为 None")
            elapsed_ms = (self.end_time - self.start_time) * 1000

            success = exc_type is None

            # 记录日志（异常安全）
            if self.log_result:
                try:
                    if success:
                        self.logger.log(
                            self.level, f"[Performance] {self.operation}: {elapsed_ms:.2f}ms",
                        )
                    else:
                        _ms = elapsed_ms
                        self.logger.error(
                            f"[Performance] {self.operation}: FAILED after {_ms:.2f}ms - {exc_val}",
                        )
                except Exception as log_error:
                    # 日志失败不应影响业务，静默失败
                    logger.debug("性能监控日志记录失败: %s", log_error)

            # 记录到追踪器（异常安全）
            if self.track:
                try:
                    tracker = get_performance_tracker()
                    tracker.record(
                        operation=self.operation,
                        elapsed_ms=elapsed_ms,
                        success=success,
                        error=str(exc_val) if exc_val else None,
                        metadata=self.metadata.copy(),
                    )

                    # 检查是否为慢操作并告警
                    config = _get_tracker_config()
                    if config["track_slow_operations"] and elapsed_ms > config["slow_threshold_ms"]:
                        self.logger.warning(
                            f"[Performance] 慢操作检测: {self.operation} "
                            f"耗时 {elapsed_ms:.2f}ms > {config['slow_threshold_ms']}ms",
                        )
                except Exception as track_error:
                    # 追踪失败不应影响业务，静默失败
                    logger.debug("性能追踪记录失败: %s", track_error)
        except (OSError, ValueError) as monitor_error:
            # 监控本身失败不应影响业务逻辑
            logger.debug("性能监控执行失败: %s", monitor_error)

    def add_metadata(self, key: str, value: Any) -> None:
        """添加元数据"""
        self.metadata[key] = value

    @property
    def elapsed_ms(self) -> float:
        """获取已耗时的毫秒数"""
        if self.start_time is None:
            raise RuntimeError("PerformanceMonitor 未正确进入上下文: start_time 为 None")
        if self.end_time is None:
            return (time.perf_counter() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000


def log_performance_summary(logger: logging.Logger, tracker: PerformanceTracker | None = None) -> None:
    """记录性能统计摘要

    Args:
        logger: 日志记录器
        tracker: 性能追踪器（None=使用全局追踪器）

    """
    if tracker is None:
        tracker = _global_tracker

    if tracker is None:
        logger.info("性能追踪器未初始化，无法生成摘要")
        return

    stats = tracker.get_statistics()

    if stats["count"] == 0:
        logger.info("无可记录的性能数据")
        return

    logger.info("=" * 60)
    logger.info("性能统计摘要")
    logger.info("=" * 60)
    logger.info(f"总操作数: {stats['count']}")
    logger.info(f"平均耗时: {stats['avg_ms']:.2f}ms")
    logger.info(f"最小耗时: {stats['min_ms']:.2f}ms")
    logger.info(f"最大耗时: {stats['max_ms']:.2f}ms")
    logger.info(f"P50耗时: {stats['p50_ms']:.2f}ms")
    logger.info(f"P95耗时: {stats['p95_ms']:.2f}ms")
    logger.info(f"P99耗时: {stats['p99_ms']:.2f}ms")
    logger.info(f"成功率: {stats['success_rate']:.2%}")
    logger.info("=" * 60)

    # 记录慢操作
    slow_ops = tracker.get_slow_operations(threshold_ms=1000, limit=5)
    if slow_ops:
        logger.warning(f"检测到 {len(slow_ops)} 个慢操作:")
        for op in slow_ops:
            logger.warning(f"  - {op.operation}: {op.elapsed_ms:.2f}ms")


# 兼容性包装器
def create_performance_monitor(
    logger: logging.Logger, operation: str, level: str = "INFO",
) -> "EnhancedPerformanceMonitor":
    """创建性能监控器（兼容旧API）

    Args:
        logger: 日志记录器
        operation: 操作名称
        level: 日志级别

    Returns:
        EnhancedPerformanceMonitor实例

    """
    return EnhancedPerformanceMonitor(logger, operation, level)
