# -*- coding: utf-8 -*-
"""GPU 可观测性模块

提供结构化 metrics 收集和 Prometheus 格式导出。
在关键 GPU 执行路径收集性能指标，支持监控系统集成。

Key Metrics:
    - gpu_keys_checked_total: 总检查私钥数 (counter)
    - gpu_matches_found_total: 总匹配数 (counter)
    - gpu_throughput_keys_per_sec: 当前吞吐量 (gauge)
    - gpu_kernel_latency_seconds: 内核执行延迟直方图 (histogram)
    - gpu_memory_pool_hit_ratio: 内存池命中率 (gauge)
    - gpu_device_count: 活跃 GPU 设备数 (gauge)
    - gpu_errors_total: 总错误数 (counter)
    - gpu_recovery_events_total: 恢复事件数 (counter)

使用示例:
    >>> from src.gpu.metrics import get_metrics_collector
    >>> metrics = get_metrics_collector()
    >>> metrics.record_keys_checked(device_idx=0, count=10000)
    >>> metrics.record_kernel_latency(device_idx=0, latency_sec=0.015)
    >>> print(metrics.export_prometheus())
"""

import time
import threading
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


class GPUMetricsCollector:
    """GPU 指标收集器

    线程安全的指标收集单例，在关键执行路径记录性能数据。
    支持 Prometheus 文本格式导出。

    Attributes:
        _lock: 线程安全锁
        _created_at: 收集器创建时间戳
    """

    # 直方图桶边界（秒）：用于内核延迟分布
    KERNEL_LATENCY_BUCKETS = (
        0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, float("inf")
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._created_at = time.time()

        # --- Counters (单调递增) ---
        self._keys_checked_total: Dict[int, int] = defaultdict(int)
        self._matches_found_total: Dict[int, int] = defaultdict(int)
        self._errors_total: Dict[int, int] = defaultdict(int)
        self._recovery_events_total: Dict[int, int] = defaultdict(int)

        # --- Gauges (瞬时值) ---
        self._throughput: Dict[int, float] = {}
        self._memory_usage_bytes: Dict[int, int] = {}
        self._device_active: Dict[int, bool] = {}

        # --- Histograms ---
        # kernel latency: device_idx -> List[bucket_counts]
        self._kernel_latency_buckets: Dict[int, List[int]] = defaultdict(
            lambda: [0] * len(self.KERNEL_LATENCY_BUCKETS)
        )
        self._kernel_latency_sum: Dict[int, float] = defaultdict(float)
        self._kernel_latency_count: Dict[int, int] = defaultdict(int)

        # --- 内存池统计 ---
        self._pool_hits: Dict[int, int] = defaultdict(int)
        self._pool_misses: Dict[int, int] = defaultdict(int)

    # ========================================================================
    # Recording API
    # ========================================================================

    def record_keys_checked(self, device_idx: int, count: int) -> None:
        """记录已检查私钥数"""
        with self._lock:
            self._keys_checked_total[device_idx] += count

    def record_match_found(self, device_idx: int) -> None:
        """记录发现的匹配"""
        with self._lock:
            self._matches_found_total[device_idx] += 1

    def record_error(self, device_idx: int, error_type: str = "") -> None:
        """记录错误事件"""
        with self._lock:
            self._errors_total[device_idx] += 1

    def record_recovery_event(self, device_idx: int) -> None:
        """记录 GPU 恢复事件"""
        with self._lock:
            self._recovery_events_total[device_idx] += 1

    def record_throughput(self, device_idx: int, keys_per_sec: float) -> None:
        """记录当前吞吐量"""
        with self._lock:
            self._throughput[device_idx] = keys_per_sec

    def record_memory_usage(self, device_idx: int, bytes_used: int) -> None:
        """记录 GPU 内存使用"""
        with self._lock:
            self._memory_usage_bytes[device_idx] = bytes_used

    def record_device_status(self, device_idx: int, active: bool) -> None:
        """记录设备活跃状态"""
        with self._lock:
            self._device_active[device_idx] = active

    def record_kernel_latency(self, device_idx: int, latency_sec: float) -> None:
        """记录内核执行延迟（直方图）

        Args:
            device_idx: GPU 设备索引
            latency_sec: 单次内核调用耗时（秒）
        """
        with self._lock:
            self._kernel_latency_sum[device_idx] += latency_sec
            self._kernel_latency_count[device_idx] += 1
            # 找到对应的桶
            buckets = self._kernel_latency_buckets[device_idx]
            for i, boundary in enumerate(self.KERNEL_LATENCY_BUCKETS):
                if latency_sec <= boundary:
                    buckets[i] += 1
                    break

    def record_pool_access(self, device_idx: int, hit: bool) -> None:
        """记录内存池访问（命中/未命中）

        Args:
            device_idx: GPU 设备索引
            hit: True=命中, False=未命中
        """
        with self._lock:
            if hit:
                self._pool_hits[device_idx] += 1
            else:
                self._pool_misses[device_idx] += 1

    # ========================================================================
    # Query API
    # ========================================================================

    def get_total_keys_checked(self) -> int:
        """获取所有设备的总检查数"""
        with self._lock:
            return sum(self._keys_checked_total.values())

    def get_total_matches(self) -> int:
        """获取所有设备的总匹配数"""
        with self._lock:
            return sum(self._matches_found_total.values())

    def get_combined_throughput(self) -> float:
        """获取所有设备的组合吞吐量"""
        with self._lock:
            return sum(self._throughput.values())

    def get_pool_hit_ratio(self, device_idx: int) -> Optional[float]:
        """获取内存池命中率"""
        with self._lock:
            total = self._pool_hits[device_idx] + self._pool_misses[device_idx]
            if total == 0:
                return None
            return self._pool_hits[device_idx] / total

    def get_kernel_latency_stats(self, device_idx: int) -> Dict:
        """获取内核延迟统计"""
        with self._lock:
            count = self._kernel_latency_count[device_idx]
            if count == 0:
                return {"count": 0, "avg_sec": 0, "p50_sec": 0, "p99_sec": 0}
            avg = self._kernel_latency_sum[device_idx] / count
            buckets = self._kernel_latency_buckets[device_idx]
            # 简单百分位估算（基于桶）
            p50_idx = count // 2
            p99_idx = int(count * 0.99)
            p50, p99 = 0.0, 0.0
            cum = 0
            for i, cnt in enumerate(buckets):
                cum += cnt
                if cum >= p50_idx and p50 == 0.0:
                    p50 = self.KERNEL_LATENCY_BUCKETS[i]
                if cum >= p99_idx and p99 == 0.0:
                    p99 = self.KERNEL_LATENCY_BUCKETS[i]
                    break
            return {
                "count": count,
                "avg_sec": round(avg, 6),
                "p50_sec": round(p50, 6),
                "p99_sec": round(p99, 6),
            }

    # ========================================================================
    # Export API
    # ========================================================================

    def export_prometheus(self) -> str:
        """导出 Prometheus 格式文本

        Returns:
            Prometheus text exposition format 字符串
        """
        with self._lock:
            lines = []

            # HELP/TYPE headers
            lines.append("# HELP gpu_keys_checked_total Total private keys checked per device.")
            lines.append("# TYPE gpu_keys_checked_total counter")
            for dev, val in sorted(self._keys_checked_total.items()):
                lines.append(f'gpu_keys_checked_total{{device="{dev}"}} {val}')

            lines.append("# HELP gpu_matches_found_total Total matches found per device.")
            lines.append("# TYPE gpu_matches_found_total counter")
            for dev, val in sorted(self._matches_found_total.items()):
                lines.append(f'gpu_matches_found_total{{device="{dev}"}} {val}')

            lines.append("# HELP gpu_errors_total Total errors per device.")
            lines.append("# TYPE gpu_errors_total counter")
            for dev, val in sorted(self._errors_total.items()):
                lines.append(f'gpu_errors_total{{device="{dev}"}} {val}')

            lines.append("# HELP gpu_recovery_events_total GPU recovery events per device.")
            lines.append("# TYPE gpu_recovery_events_total counter")
            for dev, val in sorted(self._recovery_events_total.items()):
                lines.append(f'gpu_recovery_events_total{{device="{dev}"}} {val}')

            lines.append("# HELP gpu_throughput_keys_per_sec Current throughput per device.")
            lines.append("# TYPE gpu_throughput_keys_per_sec gauge")
            for dev, val in sorted(self._throughput.items()):  # type: ignore[assignment]
                lines.append(f'gpu_throughput_keys_per_sec{{device="{dev}"}} {val:.1f}')

            lines.append("# HELP gpu_memory_usage_bytes GPU memory usage per device.")
            lines.append("# TYPE gpu_memory_usage_bytes gauge")
            for dev, val in sorted(self._memory_usage_bytes.items()):
                lines.append(f'gpu_memory_usage_bytes{{device="{dev}"}} {val}')

            lines.append("# HELP gpu_device_active Whether GPU device is active (1=yes).")
            lines.append("# TYPE gpu_device_active gauge")
            for dev, val in sorted(self._device_active.items()):
                lines.append(f'gpu_device_active{{device="{dev}"}} {1 if val else 0}')

            # Kernel latency histogram
            lines.append("# HELP gpu_kernel_latency_seconds Kernel execution latency distribution.")
            lines.append("# TYPE gpu_kernel_latency_seconds histogram")
            for dev, buckets in sorted(self._kernel_latency_buckets.items()):
                s = self._kernel_latency_sum.get(dev, 0.0)
                c = self._kernel_latency_count.get(dev, 0)
                for i, cnt in enumerate(buckets):
                    boundary = self.KERNEL_LATENCY_BUCKETS[i]
                    le_str = f"{boundary:.3f}" if boundary != float("inf") else "+Inf"
                    lines.append(
                        f'gpu_kernel_latency_seconds_bucket{{device="{dev}",le="{le_str}"}} {cnt}'
                    )
                lines.append(f'gpu_kernel_latency_seconds_sum{{device="{dev}"}} {s:.6f}')
                lines.append(f'gpu_kernel_latency_seconds_count{{device="{dev}"}} {c}')

            # Pool hit ratio
            lines.append("# HELP gpu_memory_pool_hit_ratio Memory pool cache hit ratio per device.")
            lines.append("# TYPE gpu_memory_pool_hit_ratio gauge")
            for dev in set(list(self._pool_hits.keys()) + list(self._pool_misses.keys())):
                ratio = self.get_pool_hit_ratio(dev)
                if ratio is not None:
                    lines.append(f'gpu_memory_pool_hit_ratio{{device="{dev}"}} {ratio:.4f}')

            # Collector uptime
            lines.append("# HELP gpu_metrics_collector_uptime_seconds Collector uptime.")
            lines.append("# TYPE gpu_metrics_collector_uptime_seconds gauge")
            lines.append(f"gpu_metrics_collector_uptime_seconds {time.time() - self._created_at:.1f}")

            lines.append("")  # 末尾换行
            return "\n".join(lines)

    def export_json(self) -> Dict:
        """导出 JSON 格式指标摘要

        Returns:
            结构化指标字典，适合日志/API 使用
        """
        with self._lock:
            return {
                "uptime_sec": round(time.time() - self._created_at, 1),
                "total_keys_checked": sum(self._keys_checked_total.values()),
                "total_matches": sum(self._matches_found_total.values()),
                "total_errors": sum(self._errors_total.values()),
                "combined_throughput": sum(self._throughput.values()),
                "per_device": {
                    dev: {
                        "keys_checked": self._keys_checked_total.get(dev, 0),
                        "matches": self._matches_found_total.get(dev, 0),
                        "errors": self._errors_total.get(dev, 0),
                        "throughput": self._throughput.get(dev, 0.0),
                        "memory_bytes": self._memory_usage_bytes.get(dev, 0),
                        "kernel_latency": self.get_kernel_latency_stats(dev),
                        "pool_hit_ratio": self.get_pool_hit_ratio(dev),
                    }
                    for dev in sorted(
                        set(
                            list(self._keys_checked_total.keys())
                            + list(self._throughput.keys())
                        )
                    )
                },
            }

    def reset(self) -> None:
        """重置所有指标（用于测试）"""
        with self._lock:
            self._keys_checked_total.clear()
            self._matches_found_total.clear()
            self._errors_total.clear()
            self._recovery_events_total.clear()
            self._throughput.clear()
            self._memory_usage_bytes.clear()
            self._device_active.clear()
            self._kernel_latency_buckets.clear()
            self._kernel_latency_sum.clear()
            self._kernel_latency_count.clear()
            self._pool_hits.clear()
            self._pool_misses.clear()
            self._created_at = time.time()


# 全局单例
_global_metrics_collector: Optional[GPUMetricsCollector] = None


def get_metrics_collector() -> GPUMetricsCollector:
    """获取全局指标收集器实例"""
    global _global_metrics_collector
    if _global_metrics_collector is None:
        _global_metrics_collector = GPUMetricsCollector()
    return _global_metrics_collector


def reset_metrics_collector():
    """重置全局指标收集器"""
    global _global_metrics_collector
    if _global_metrics_collector is not None:
        _global_metrics_collector.reset()
    _global_metrics_collector = None
