# -*- coding: utf-8 -*-
"""
性能监控模块 - 实时监控优化效果

监控碰撞引擎的性能指标,包括:
- 地址生成速度
- 内存使用情况
- 优化模块启用状态
- 性能退化检测
- 性能趋势分析
"""

import time
import threading
import logging
from typing import Dict, List, Optional, Any, Callable
from collections import deque
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("PerformanceMonitor")


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""

    timestamp: float
    addresses_generated: int
    elapsed_time: float
    speed: float  # 地址/秒
    memory_usage_mb: float
    optimization_enabled: bool
    precomputed_table: bool
    simd_hash: bool
    memory_pool: bool
    gpu_memory_pool: bool

    # 延迟统计
    avg_generation_time_ms: float = 0.0
    min_generation_time_ms: float = 0.0
    max_generation_time_ms: float = 0.0

    # 错误统计
    error_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "addresses_generated": self.addresses_generated,
            "elapsed_time": self.elapsed_time,
            "speed": self.speed,
            "memory_usage_mb": self.memory_usage_mb,
            "optimization_enabled": self.optimization_enabled,
            "precomputed_table": self.precomputed_table,
            "simd_hash": self.simd_hash,
            "memory_pool": self.memory_pool,
            "gpu_memory_pool": self.gpu_memory_pool,
            "avg_generation_time_ms": self.avg_generation_time_ms,
            "min_generation_time_ms": self.min_generation_time_ms,
            "max_generation_time_ms": self.max_generation_time_ms,
            "error_count": self.error_count,
        }


class OptimizationPerformanceMonitor:
    """优化性能监控器

    实时监控碰撞引擎的性能指标,检测性能退化,生成性能报告。

    使用示例:
        monitor = OptimizationPerformanceMonitor()
        monitor.start()

        # 在碰撞引擎中记录指标
        monitor.record_metrics(
            addresses_generated=1000,
            elapsed_time=10.5,
            optimization_enabled=True
        )

        # 获取报告
        report = monitor.get_performance_report()

        monitor.stop()
    """

    def __init__(
        self,
        check_interval: float = 5.0,
        degradation_threshold: float = 0.8,
        history_size: int = 1000,
    ) -> None:
        """
        初始化性能监控器

        Args:
            check_interval: 检查间隔(秒)
            degradation_threshold: 性能退化阈值(相对于峰值的比值,默认0.8表示下降20%触发告警)
            history_size: 历史记录大小
        """
        self.check_interval = check_interval
        self.degradation_threshold = degradation_threshold
        self.history_size = history_size

        # 历史记录
        self._metrics_history: deque = deque(maxlen=history_size)

        # 统计信息
        self._peak_speed = 0.0
        self._total_addresses = 0
        self._total_errors = 0
        self._start_time: Optional[float] = None

        # 线程控制
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # 告警回调
        self._degradation_callbacks: list[Callable] = []

        logger.info(
            "OptimizationPerformanceMonitor初始化: "
            f"check_interval={check_interval}s, "
            f"degradation_threshold={degradation_threshold}"
        )

    def start(self) -> None:
        """启动监控"""
        if self._running:
            return

        self._running = True
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

        logger.info("性能监控已启动")

    def stop(self) -> None:
        """停止监控"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

        logger.info("性能监控已停止")

    def record_metrics(
        self,
        addresses_generated: int,
        elapsed_time: float,
        optimization_enabled: bool = True,
        precomputed_table: bool = True,
        simd_hash: bool = True,
        memory_pool: bool = True,
        gpu_memory_pool: bool = False,
        memory_usage_mb: float = 0.0,
        generation_times: Optional[List[float]] = None,
        error_count: int = 0,
    ) -> None:
        """
        记录性能指标

        Args:
            addresses_generated: 生成的地址数量
            elapsed_time: 耗时(秒)
            optimization_enabled: 是否启用优化
            precomputed_table: 是否使用预计算表
            simd_hash: 是否使用SIMD哈希
            memory_pool: 是否使用内存池
            gpu_memory_pool: 是否使用GPU内存池
            memory_usage_mb: 内存使用(MB)
            generation_times: 单个地址生成时间列表(毫秒)
            error_count: 错误数量
        """
        speed = addresses_generated / elapsed_time if elapsed_time > 0 else 0

        # 计算延迟统计
        avg_time = 0.0
        min_time = 0.0
        max_time = 0.0

        if generation_times:
            avg_time = sum(generation_times) / len(generation_times)
            min_time = min(generation_times)
            max_time = max(generation_times)

        metrics = PerformanceMetrics(
            timestamp=time.time(),
            addresses_generated=addresses_generated,
            elapsed_time=elapsed_time,
            speed=speed,
            memory_usage_mb=memory_usage_mb,
            optimization_enabled=optimization_enabled,
            precomputed_table=precomputed_table,
            simd_hash=simd_hash,
            memory_pool=memory_pool,
            gpu_memory_pool=gpu_memory_pool,
            avg_generation_time_ms=avg_time,
            min_generation_time_ms=min_time,
            max_generation_time_ms=max_time,
            error_count=error_count,
        )

        with self._lock:
            self._metrics_history.append(metrics)
            self._total_addresses += addresses_generated
            self._total_errors += error_count

            # 更新峰值速度
            if speed > self._peak_speed:
                self._peak_speed = speed

            # 检测性能退化
            if self._peak_speed > 0 and speed < self._peak_speed * self.degradation_threshold:
                self._on_performance_degradation(metrics)

        logger.debug(
            f"记录性能指标: speed={speed:.0f} addr/s, " f"optimization={optimization_enabled}"
        )

    def get_current_metrics(self) -> Optional[PerformanceMetrics]:
        """获取当前指标"""
        with self._lock:
            if self._metrics_history:
                return self._metrics_history[-1]
        return None

    def get_average_speed(self, window_seconds: float = 60.0) -> float:
        """
        获取平均速度

        Args:
            window_seconds: 时间窗口(秒)

        Returns:
            平均速度(地址/秒)
        """
        with self._lock:
            if not self._metrics_history:
                return 0.0

            cutoff_time = time.time() - window_seconds
            recent_metrics = [m for m in self._metrics_history if m.timestamp >= cutoff_time]

            if not recent_metrics:
                return 0.0

            total_speed = sum(m.speed for m in recent_metrics)
            return total_speed / len(recent_metrics)

    def get_performance_report(self) -> Dict[str, Any]:
        """
        获取性能报告

        Returns:
            性能报告字典
        """
        with self._lock:
            if not self._metrics_history:
                return {"status": "no_data"}

            # 计算统计
            speeds = [m.speed for m in self._metrics_history]
            avg_speed = sum(speeds) / len(speeds)
            min_speed = min(speeds)
            max_speed = max(speeds)

            # 优化配置统计
            opt_enabled = sum(1 for m in self._metrics_history if m.optimization_enabled)
            opt_percentage = (opt_enabled / len(self._metrics_history)) * 100

            # 内存使用
            memory_usages = [
                m.memory_usage_mb for m in self._metrics_history if m.memory_usage_mb > 0
            ]
            avg_memory = sum(memory_usages) / len(memory_usages) if memory_usages else 0

            # 错误率
            error_rate = (self._total_errors / max(self._total_addresses, 1)) * 100

            # 性能稳定性
            if avg_speed > 0:
                stability = (min_speed / avg_speed) * 100
            else:
                stability = 0

            report = {
                "status": "running" if self._running else "stopped",
                "summary": {
                    "total_addresses": self._total_addresses,
                    "total_errors": self._total_errors,
                    "error_rate": error_rate,
                    "peak_speed": self._peak_speed,
                    "avg_speed": avg_speed,
                    "min_speed": min_speed,
                    "max_speed": max_speed,
                    "stability": stability,
                },
                "optimization": {
                    "enabled_percentage": opt_percentage,
                    "precomputed_table_usage": sum(
                        1 for m in self._metrics_history if m.precomputed_table
                    ),
                    "simd_hash_usage": sum(1 for m in self._metrics_history if m.simd_hash),
                    "memory_pool_usage": sum(1 for m in self._metrics_history if m.memory_pool),
                    "gpu_memory_pool_usage": sum(
                        1 for m in self._metrics_history if m.gpu_memory_pool
                    ),
                },
                "memory": {
                    "current_mb": (
                        self._metrics_history[-1].memory_usage_mb if self._metrics_history else 0
                    ),
                    "average_mb": avg_memory,
                },
                "latency": {
                    "avg_ms": (
                        self._metrics_history[-1].avg_generation_time_ms
                        if self._metrics_history
                        else 0
                    ),
                    "min_ms": (
                        self._metrics_history[-1].min_generation_time_ms
                        if self._metrics_history
                        else 0
                    ),
                    "max_ms": (
                        self._metrics_history[-1].max_generation_time_ms
                        if self._metrics_history
                        else 0
                    ),
                },
                "history_size": len(self._metrics_history),
                "uptime_seconds": time.time() - self._start_time if self._start_time else 0,
            }

            return report

    def on_degradation(self, callback: Callable) -> None:
        """
        注册性能退化回调

        Args:
            callback: 回调函数 fn(metrics, degradation_ratio)
        """
        self._degradation_callbacks.append(callback)

    def export_metrics(self, format: str = "json") -> str:
        """
        导出指标数据

        Args:
            format: 导出格式 ('json' 或 'csv')

        Returns:
            导出的数据字符串
        """
        from src.utils.fast_json import fast_dumps

        with self._lock:
            metrics_list = [m.to_dict() for m in self._metrics_history]

            if format == "json":
                return fast_dumps(metrics_list, indent=2, ensure_ascii=False)
            elif format == "csv":
                if not metrics_list:
                    return ""

                headers = metrics_list[0].keys()
                csv_lines = [",".join(headers)]

                for m in metrics_list:
                    row = [str(m[h]) for h in headers]
                    csv_lines.append(",".join(row))

                return "\n".join(csv_lines)
            else:
                raise ValueError(f"不支持的格式: {format}")

    def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                # 定期检查性能状态
                current = self.get_current_metrics()
                if current:
                    logger.debug(
                        f"当前性能: {current.speed:.0f} addr/s, "
                        f"峰值: {self._peak_speed:.0f} addr/s"
                    )

                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                time.sleep(self.check_interval)

    def _on_performance_degradation(self, metrics: PerformanceMetrics):
        """性能退化处理"""
        degradation_ratio = metrics.speed / self._peak_speed if self._peak_speed > 0 else 0

        logger.warning(
            "⚠️ 检测到性能退化: "
            f"当前={metrics.speed:.0f} addr/s, "
            f"峰值={self._peak_speed:.0f} addr/s, "
            f"退化率={degradation_ratio:.2%}"
        )

        # 触发回调
        for callback in self._degradation_callbacks:
            try:
                callback(metrics, degradation_ratio)
            except Exception as e:
                logger.error(f"性能退化回调执行失败: {e}")


# 全局性能监控器实例
_global_monitor: Optional[OptimizationPerformanceMonitor] = None
_monitor_lock = threading.Lock()


def get_performance_monitor() -> OptimizationPerformanceMonitor:
    """获取全局性能监控器"""
    global _global_monitor

    with _monitor_lock:
        if _global_monitor is None:
            _global_monitor = OptimizationPerformanceMonitor()

        return _global_monitor


def reset_performance_monitor() -> None:
    """重置全局性能监控器"""
    global _global_monitor

    with _monitor_lock:
        if _global_monitor:
            _global_monitor.stop()
        _global_monitor = None
