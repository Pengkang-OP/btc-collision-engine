"""统计系统性能监控模块

实时监控统计系统本身的性能指标。
"""

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import psutil


@dataclass
class PerformanceSample:
    """性能采样点"""

    timestamp: float
    latency_ms: float
    lock_contention: float
    throughput: float
    memory_usage_mb: float
    cpu_usage: float


class StatsPerformanceMonitor:
    """统计系统性能监控器

    监控指标：
    - 更新延迟：统计更新操作的响应时间
    - 锁竞争：锁等待时间占比
    - 吞吐量：每秒处理的统计更新次数
    - 内存使用：统计系统占用的内存
    - CPU使用率：统计系统消耗的CPU

    告警机制：
    - 延迟超过阈值时告警
    - 锁竞争严重时告警
    - 内存使用过高时告警
    """

    def __init__(self, alert_thresholds: dict[str, float] | None = None) -> None:
        """
        Args:
            alert_thresholds: 告警阈值配置
        """
        # 停止标志（必须在启动线程前初始化）
        self._stop_event = threading.Event()

        # 告警阈值
        self._thresholds = alert_thresholds or {
            "latency_ms": 100.0,
            "lock_contention": 0.5,
            "memory_mb": 512.0,
            "cpu_usage": 80.0,
        }

        # 性能采样队列
        self._samples: deque[PerformanceSample] = deque(maxlen=100)
        self._samples_lock = threading.Lock()

        # 统计计数器
        self._update_count = 0
        self._total_latency_ms = 0.0
        self._lock_wait_time_ms = 0.0
        self._last_check_time = time.time()

        # 监控线程
        self._monitor_interval = 1.0
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        # 告警回调
        self._alert_callback: Callable[..., Any] | None = None

        # 进程信息
        self._process = psutil.Process()

    def set_alert_callback(self, callback: Callable | None) -> None:
        """设置告警回调函数"""
        self._alert_callback = callback

    def record_update(self, latency_ms: float, lock_wait_ms: float = 0.0) -> None:
        """记录统计更新操作"""
        with self._samples_lock:
            self._update_count += 1
            self._total_latency_ms += latency_ms
            self._lock_wait_time_ms += lock_wait_ms

    def _monitor_loop(self) -> None:
        """监控循环"""
        while not self._stop_event.is_set():
            self._take_sample()
            time.sleep(self._monitor_interval)

    def _take_sample(self) -> None:
        """采集性能样本"""
        current_time = time.time()
        elapsed = current_time - self._last_check_time

        if elapsed <= 0:
            return

        with self._samples_lock:
            avg_latency = self._total_latency_ms / max(self._update_count, 1)
            avg_lock_wait = self._lock_wait_time_ms / max(self._update_count, 1)
            throughput = self._update_count / elapsed

            self._update_count = 0
            self._total_latency_ms = 0.0
            self._lock_wait_time_ms = 0.0

        self._last_check_time = current_time

        try:
            memory_usage_mb = self._process.memory_info().rss / (1024 * 1024)
            cpu_usage = self._process.cpu_percent(interval=0.1)
        except Exception:
            memory_usage_mb = 0.0
            cpu_usage = 0.0

        lock_contention = avg_lock_wait / (avg_latency + 0.001) * 100

        sample = PerformanceSample(
            timestamp=current_time,
            latency_ms=avg_latency,
            lock_contention=lock_contention,
            throughput=throughput,
            memory_usage_mb=memory_usage_mb,
            cpu_usage=cpu_usage,
        )

        with self._samples_lock:
            self._samples.append(sample)

        self._check_alerts(sample)

    def _check_alerts(self, sample: PerformanceSample) -> None:
        """检查告警条件

        使用 .get() 安全访问阈值，避免 partial 自定义阈值时的 KeyError。
        """
        if self._alert_callback is None:
            return

        alerts = []
        th = self._thresholds
        lat_th = th.get("latency_ms", 100.0)
        lock_th = th.get("lock_contention", 0.5)
        mem_th = th.get("memory_mb", 512.0)
        cpu_th = th.get("cpu_usage", 80.0)

        if sample.latency_ms > lat_th:
            alerts.append(("latency_ms", sample.latency_ms, lat_th))

        if sample.lock_contention > lock_th * 100:
            alerts.append(("lock_contention", sample.lock_contention, lock_th * 100))

        if sample.memory_usage_mb > mem_th:
            alerts.append(("memory_mb", sample.memory_usage_mb, mem_th))

        if sample.cpu_usage > cpu_th:
            alerts.append(("cpu_usage", sample.cpu_usage, cpu_th))

        for metric, value, threshold in alerts:
            with contextlib.suppress(Exception):
                self._alert_callback(metric, value, threshold)

    def get_recent_performance(self, window_seconds: float = 10.0) -> dict[str, Any]:
        """获取最近一段时间的性能统计"""
        now = time.time()
        recent_samples = []

        with self._samples_lock:
            for sample in self._samples:
                if now - sample.timestamp <= window_seconds:
                    recent_samples.append(sample)

        if not recent_samples:
            return {
                "average_latency_ms": 0.0,
                "average_lock_contention": 0.0,
                "average_throughput": 0.0,
                "average_memory_mb": 0.0,
                "average_cpu_usage": 0.0,
                "sample_count": 0,
            }

        return {
            "average_latency_ms": sum(s.latency_ms for s in recent_samples) / len(recent_samples),
            "average_lock_contention": sum(s.lock_contention for s in recent_samples)
            / len(recent_samples),
            "average_throughput": sum(s.throughput for s in recent_samples) / len(recent_samples),
            "average_memory_mb": sum(s.memory_usage_mb for s in recent_samples)
            / len(recent_samples),
            "average_cpu_usage": sum(s.cpu_usage for s in recent_samples) / len(recent_samples),
            "sample_count": len(recent_samples),
        }

    def get_performance_report(self) -> dict[str, Any]:
        """获取完整的性能报告"""
        recent = self.get_recent_performance()

        return {
            "timestamp": time.time(),
            "recent_performance": recent,
            "thresholds": self._thresholds,
            "status": self._get_health_status(recent),
        }

    def _get_health_status(self, recent: dict[str, Any]) -> str:
        """根据最近性能判断健康状态

        使用 .get() 安全访问阈值，避免 partial 自定义阈值时的 KeyError。
        """
        th = self._thresholds
        if recent["average_latency_ms"] > th.get("latency_ms", 100.0):
            return "warning"
        if recent["average_lock_contention"] > th.get("lock_contention", 0.5) * 100:
            return "warning"
        if recent["average_memory_mb"] > th.get("memory_mb", 512.0):
            return "critical"
        if recent["average_cpu_usage"] > th.get("cpu_usage", 80.0):
            return "warning"
        return "healthy"

    def stop(self) -> None:
        """停止监控器"""
        self._stop_event.set()
        self._monitor_thread.join(timeout=1.0)


class StatsUpdateProfiler:
    """统计更新性能分析器"""

    def __init__(self, monitor: StatsPerformanceMonitor) -> None:
        self._monitor = monitor

    def profile_update(self, update_func: Callable, *args: Any, **kwargs: Any) -> Any:
        """分析更新操作的性能"""
        start_time = time.perf_counter()
        lock_wait_start = time.perf_counter()

        result = update_func(*args, **kwargs)

        lock_wait_end = time.perf_counter()
        end_time = time.perf_counter()

        latency_ms = (end_time - start_time) * 1000
        lock_wait_ms = (lock_wait_end - lock_wait_start) * 1000

        if self._monitor:
            self._monitor.record_update(latency_ms, lock_wait_ms)

        return result


_global_monitor = None


def get_global_monitor() -> StatsPerformanceMonitor:
    """获取全局性能监控器"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = StatsPerformanceMonitor()
    return _global_monitor


def profile_stats_update(func: Callable) -> Callable:
    """装饰器：分析统计更新函数"""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        monitor = get_global_monitor()
        profiler = StatsUpdateProfiler(monitor)
        return profiler.profile_update(func, *args, **kwargs)

    return wrapper
