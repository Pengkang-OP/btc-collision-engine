#!/usr/bin/env python3
"""GPU Metrics 单元测试

覆盖 src/gpu/metrics.py 中 GPUMetricsCollector 的核心功能：
- 计数器 (counters): keys_checked, matches, errors, recovery
- 瞬时值 (gauges): throughput, memory, device_status
- 直方图 (histogram): kernel latency
- 内存池统计: pool hit/miss ratio
- 导出: Prometheus / JSON 格式
- 线程安全: 并发记录
- 单例生命周期: get/reset
"""

import pytest
import threading
import time
from src.gpu.metrics import (
    GPUMetricsCollector,
    get_metrics_collector,
    reset_metrics_collector,
)


@pytest.fixture(autouse=True)
def reset_metrics():
    """每个测试后重置全局指标收集器"""
    yield
    reset_metrics_collector()


@pytest.fixture
def collector():
    """创建独立的指标收集器"""
    return GPUMetricsCollector()


class TestCounters:
    """计数器测试 (单调递增)"""

    def test_record_keys_checked(self, collector):
        """记录已检查私钥数"""
        collector.record_keys_checked(0, 10000)
        assert collector.get_total_keys_checked() == 10000
        collector.record_keys_checked(0, 5000)
        assert collector.get_total_keys_checked() == 15000

    def test_record_keys_checked_multi_device(self, collector):
        """多设备独立计数"""
        collector.record_keys_checked(0, 100)
        collector.record_keys_checked(1, 200)
        collector.record_keys_checked(2, 300)
        assert collector.get_total_keys_checked() == 600

    def test_record_match_found(self, collector):
        """记录匹配发现"""
        collector.record_match_found(0)
        collector.record_match_found(0)
        assert collector.get_total_matches() == 2

    def test_record_match_found_multi_device(self, collector):
        """多设备匹配计数"""
        collector.record_match_found(0)
        collector.record_match_found(0)
        collector.record_match_found(1)
        assert collector.get_total_matches() == 3

    def test_record_error(self, collector):
        """记录错误事件"""
        collector.record_error(0, "OOM")
        collector.record_error(1, "timeout")
        # 验证导出包含错误计数
        data = collector.export_json()
        assert data["total_errors"] == 2

    def test_record_recovery_event(self, collector):
        """记录恢复事件"""
        collector.record_recovery_event(0)
        collector.record_recovery_event(0)
        collector.record_recovery_event(1)
        prom = collector.export_prometheus()
        assert 'gpu_recovery_events_total{device="0"} 2' in prom
        assert 'gpu_recovery_events_total{device="1"} 1' in prom


class TestGauges:
    """瞬时值测试 (gauge)"""

    def test_record_throughput(self, collector):
        """记录吞吐量"""
        collector.record_throughput(0, 1500000.5)
        assert collector.get_combined_throughput() == 1500000.5
        collector.record_throughput(0, 2000000.0)
        assert collector.get_combined_throughput() == 2000000.0

    def test_combined_throughput_multi_device(self, collector):
        """多设备组合吞吐量"""
        collector.record_throughput(0, 1e6)
        collector.record_throughput(1, 2e6)
        collector.record_throughput(2, 3e6)
        assert collector.get_combined_throughput() == 6e6

    def test_record_memory_usage(self, collector):
        """记录 GPU 内存使用"""
        collector.record_memory_usage(0, 1024 * 1024 * 512)  # 512MB
        prom = collector.export_prometheus()
        assert f'gpu_memory_usage_bytes{{device="0"}} {1024*1024*512}' in prom

    def test_record_device_status(self, collector):
        """记录设备活跃状态"""
        collector.record_device_status(0, True)
        collector.record_device_status(1, False)
        prom = collector.export_prometheus()
        assert 'gpu_device_active{device="0"} 1' in prom
        assert 'gpu_device_active{device="1"} 0' in prom


class TestHistogram:
    """直方图测试"""

    def test_record_kernel_latency(self, collector):
        """记录内核执行延迟"""
        collector.record_kernel_latency(0, 0.005)  # 5ms → 第2桶
        collector.record_kernel_latency(0, 0.015)  # 15ms → 第3桶
        collector.record_kernel_latency(0, 0.100)  # 100ms → 第8桶

        stats = collector.get_kernel_latency_stats(0)
        assert stats["count"] == 3
        # avg = (0.005 + 0.015 + 0.100) / 3 ≈ 0.04
        assert 0.039 < stats["avg_sec"] < 0.041

    def test_kernel_latency_empty_device(self, collector):
        """未记录延迟的设备统计"""
        stats = collector.get_kernel_latency_stats(99)
        assert stats == {"count": 0, "avg_sec": 0, "p50_sec": 0, "p99_sec": 0}

    def test_kernel_latency_bucket_boundaries(self, collector):
        """测试延迟桶边界"""
        # 精确命中桶边界
        collector.record_kernel_latency(0, 0.001)  # 桶0
        collector.record_kernel_latency(0, 0.002)  # 桶1
        collector.record_kernel_latency(0, 1.5)    # 桶9 (inf)
        stats = collector.get_kernel_latency_stats(0)
        assert stats["count"] == 3

    def test_kernel_latency_prometheus_export(self, collector):
        """Prometheus 直方图导出"""
        collector.record_kernel_latency(0, 0.003)
        collector.record_kernel_latency(0, 0.008)
        prom = collector.export_prometheus()
        assert 'gpu_kernel_latency_seconds_bucket{device="0",le="0.005"}' in prom
        assert 'gpu_kernel_latency_seconds_sum{device="0"}' in prom
        assert 'gpu_kernel_latency_seconds_count{device="0"} 2' in prom


class TestPoolStats:
    """内存池统计测试"""

    def test_pool_hit_recording(self, collector):
        """记录内存池命中"""
        collector.record_pool_access(0, True)
        collector.record_pool_access(0, True)
        collector.record_pool_access(0, False)
        ratio = collector.get_pool_hit_ratio(0)
        assert ratio == pytest.approx(2.0 / 3.0)

    def test_pool_hit_ratio_no_data(self, collector):
        """无数据时命中率为 None"""
        assert collector.get_pool_hit_ratio(0) is None

    def test_pool_hit_ratio_all_hits(self, collector):
        """100% 命中率"""
        collector.record_pool_access(0, True)
        collector.record_pool_access(0, True)
        assert collector.get_pool_hit_ratio(0) == 1.0

    def test_pool_hit_ratio_all_misses(self, collector):
        """0% 命中率"""
        collector.record_pool_access(0, False)
        collector.record_pool_access(0, False)
        assert collector.get_pool_hit_ratio(0) == 0.0

    def test_pool_ratio_in_prometheus(self, collector):
        """Prometheus 导出包含命中率（RLock 修复后不再死锁）"""
        collector.record_pool_access(0, True)
        collector.record_pool_access(0, False)
        prom = collector.export_prometheus()
        assert 'gpu_memory_pool_hit_ratio{device="0"} 0.5000' in prom


class TestExport:
    """导出格式测试"""

    def test_export_prometheus_has_help(self, collector):
        """Prometheus 导出包含 HELP/TYPE 注释"""
        prom = collector.export_prometheus()
        assert "# HELP gpu_keys_checked_total" in prom
        assert "# TYPE gpu_keys_checked_total counter" in prom
        assert "# HELP gpu_throughput_keys_per_sec" in prom
        assert "# TYPE gpu_throughput_keys_per_sec gauge" in prom
        assert "# HELP gpu_kernel_latency_seconds" in prom
        assert "# TYPE gpu_kernel_latency_seconds histogram" in prom

    def test_export_prometheus_ends_with_newline(self, collector):
        """Prometheus 导出以换行结尾"""
        prom = collector.export_prometheus()
        assert prom.endswith("\n")

    def test_export_json_structure_with_data(self, collector):
        """有数据时 JSON 导出结构完整（RLock 修复后不再死锁）"""
        collector.record_keys_checked(0, 100)
        collector.record_match_found(0)
        collector.record_throughput(0, 5000.0)
        collector.record_kernel_latency(0, 0.015)
        collector.record_pool_access(0, True)
        data = collector.export_json()
        assert "uptime_sec" in data
        assert "total_keys_checked" in data
        assert data["total_keys_checked"] == 100
        assert data["total_matches"] == 1
        assert "per_device" in data
        assert 0 in data["per_device"]
        dev = data["per_device"][0]
        assert dev["keys_checked"] == 100
        assert dev["matches"] == 1
        assert dev["throughput"] == 5000.0
        assert "kernel_latency" in dev
        assert dev["kernel_latency"]["count"] == 1
        assert dev["pool_hit_ratio"] == 1.0

    def test_export_json_per_device_empty(self, collector):
        """空收集器 per_device 为空"""
        data = collector.export_json()
        assert data["per_device"] == {}


class TestReset:
    """重置功能测试"""

    def test_reset_clears_all_counters(self, collector):
        """reset() 清空所有计数器"""
        collector.record_keys_checked(0, 10000)
        collector.record_match_found(0)
        collector.record_error(0)
        collector.record_throughput(0, 1e6)
        collector.record_pool_access(0, True)

        collector.reset()

        assert collector.get_total_keys_checked() == 0
        assert collector.get_total_matches() == 0
        assert collector.get_combined_throughput() == 0
        assert collector.get_pool_hit_ratio(0) is None
        assert collector.get_kernel_latency_stats(0)["count"] == 0


class TestThreadSafety:
    """线程安全测试"""

    def test_concurrent_record_keys_checked(self, collector):
        """并发记录 keys_checked"""
        errors = []

        def recorder(start, count):
            try:
                for i in range(start, start + count):
                    collector.record_keys_checked(i % 4, 1)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=recorder, args=(i * 250, 250)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert collector.get_total_keys_checked() == 1000

    def test_concurrent_record_mixed(self, collector):
        """并发混合记录各类指标"""
        errors = []

        def worker(tid):
            try:
                for i in range(100):
                    collector.record_keys_checked(tid % 2, 1)
                    collector.record_throughput(tid % 2, 1000.0)
                    collector.record_pool_access(tid % 2, i % 2 == 0)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_export_during_recording(self, collector):
        """录制期间并发导出（Prometheus+JSON）不崩溃（RLock 修复后安全）"""
        errors = []
        stop = threading.Event()

        def recorder():
            i = 0
            while not stop.is_set():
                collector.record_keys_checked(0, 1)
                collector.record_throughput(0, 1000.0)
                i += 1

        def exporter():
            while not stop.is_set():
                collector.export_prometheus()
                collector.export_json()

        threads = [
            threading.Thread(target=recorder),
            threading.Thread(target=recorder),
            threading.Thread(target=exporter),
            threading.Thread(target=exporter),
        ]
        for t in threads:
            t.start()

        time.sleep(0.2)
        stop.set()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestSingleton:
    """单例生命周期测试"""

    def test_get_metrics_collector_same_instance(self):
        """get_metrics_collector 返回同一实例"""
        c1 = get_metrics_collector()
        c2 = get_metrics_collector()
        assert c1 is c2

    def test_reset_metrics_collector(self):
        """reset 后创建新实例"""
        c1 = get_metrics_collector()
        c1.record_keys_checked(0, 100)
        reset_metrics_collector()
        c2 = get_metrics_collector()
        assert c1 is not c2
        assert c2.get_total_keys_checked() == 0

    def test_reset_metrics_collector_when_none(self):
        """None 状态 reset 不崩溃"""
        reset_metrics_collector()
        reset_metrics_collector()  # 二次 reset
        c = get_metrics_collector()
        assert c.get_total_keys_checked() == 0


class TestEdgeCases:
    """边界情况测试"""

    def test_zero_count_record(self, collector):
        """记录 0 个 keys_checked"""
        collector.record_keys_checked(0, 0)
        assert collector.get_total_keys_checked() == 0

    def test_negative_throughput(self, collector):
        """负吞吐量（边界值）"""
        collector.record_throughput(0, -1.0)
        assert collector.get_combined_throughput() == -1.0

    def test_very_large_count(self, collector):
        """极大计数值（不溢出）"""
        collector.record_keys_checked(0, 2**63 - 1)
        assert collector.get_total_keys_checked() == 2**63 - 1

    def test_empty_export_prometheus(self, collector):
        """空收集器导出 Prometheus"""
        prom = collector.export_prometheus()
        assert "# HELP" in prom
        assert prom.endswith("\n")

    def test_empty_export_json(self, collector):
        """空收集器导出 JSON"""
        data = collector.export_json()
        assert data["total_keys_checked"] == 0
        assert data["total_matches"] == 0
