# -*- coding: utf-8 -*-
"""
GPU性能监控模块单元测试
"""

import pytest
import time
from src.monitoring.gpu_performance_monitor import (
    GPUPerformanceMonitor,
    GPUKernelMetrics,
    GPUMemoryMetrics,
    GPUPerformanceReport,
    get_gpu_performance_monitor,
    reset_gpu_performance_monitor,
)


class TestGPUKernelMetrics:
    """GPU内核指标测试"""

    def test_creation(self):
        """测试创建"""
        metrics = GPUKernelMetrics(
            timestamp=time.time(),
            batch_size=10000,
            execution_time_ms=50.0,
            keys_per_second=200000.0,
            memory_allocated_mb=128.0,
            error_count=0,
            match_count=1,
        )

        assert metrics.batch_size == 10000
        assert metrics.execution_time_ms == 50.0
        assert metrics.keys_per_second == 200000.0

    def test_to_dict(self):
        """测试转换为字典"""
        metrics = GPUKernelMetrics(
            timestamp=time.time(),
            batch_size=10000,
            execution_time_ms=50.0,
            keys_per_second=200000.0,
            memory_allocated_mb=128.0,
            error_count=0,
            match_count=1,
        )

        d = metrics.to_dict()
        assert "batch_size" in d
        assert "execution_time_ms" in d
        assert "keys_per_second" in d
        assert d["batch_size"] == 10000


class TestGPUMemoryMetrics:
    """GPU显存指标测试"""

    def test_creation(self):
        """测试创建"""
        metrics = GPUMemoryMetrics(
            timestamp=time.time(),
            total_memory_mb=8192.0,
            used_memory_mb=1024.0,
            free_memory_mb=7168.0,
            usage_percent=12.5,
            peak_usage_mb=2048.0,
            allocation_count=100,
            deallocation_count=50,
        )

        assert metrics.total_memory_mb == 8192.0
        assert metrics.used_memory_mb == 1024.0
        assert metrics.usage_percent == 12.5

    def test_pool_hit_rate(self):
        """测试内存池命中率"""
        metrics = GPUMemoryMetrics(
            timestamp=time.time(),
            total_memory_mb=8192.0,
            used_memory_mb=1024.0,
            free_memory_mb=7168.0,
            usage_percent=12.5,
            peak_usage_mb=2048.0,
            allocation_count=100,
            deallocation_count=50,
            pool_hits=80,
            pool_misses=20,
        )

        d = metrics.to_dict()
        assert d["pool_hit_rate"] == 80.0  # 80/(80+20)*100


class TestGPUPerformanceMonitor:
    """GPU性能监控器测试"""

    def setup_method(self):
        """测试前重置"""
        reset_gpu_performance_monitor()

    def teardown_method(self):
        """测试后清理"""
        reset_gpu_performance_monitor()

    def test_creation(self):
        """测试创建"""
        monitor = GPUPerformanceMonitor()
        assert monitor._running is False
        assert monitor._total_batches == 0
        assert monitor._peak_throughput == 0.0

    def test_start_stop(self):
        """测试启动和停止"""
        monitor = GPUPerformanceMonitor()
        monitor.start()
        assert monitor._running is True

        monitor.stop()
        assert monitor._running is False

    def test_record_kernel_metrics(self):
        """测试记录内核指标"""
        monitor = GPUPerformanceMonitor()

        monitor.record_kernel_metrics(
            batch_size=10000, execution_time_ms=50.0, memory_allocated_mb=128.0
        )

        assert monitor._total_batches == 1
        assert monitor._total_keys == 10000
        assert monitor._peak_throughput == 200000.0  # 10000/50*1000

    def test_record_multiple_metrics(self):
        """测试记录多个指标"""
        monitor = GPUPerformanceMonitor()

        # 记录3个批次
        monitor.record_kernel_metrics(
            batch_size=10000, execution_time_ms=50.0, memory_allocated_mb=128.0
        )

        monitor.record_kernel_metrics(
            batch_size=20000, execution_time_ms=80.0, memory_allocated_mb=256.0
        )

        monitor.record_kernel_metrics(
            batch_size=15000, execution_time_ms=60.0, memory_allocated_mb=192.0
        )

        assert monitor._total_batches == 3
        assert monitor._total_keys == 45000
        assert monitor._peak_throughput == 250000.0  # 20000/80*1000

    def test_get_current_throughput(self):
        """测试获取当前吞吐量"""
        monitor = GPUPerformanceMonitor()

        assert monitor.get_current_throughput() == 0.0

        monitor.record_kernel_metrics(
            batch_size=10000, execution_time_ms=50.0, memory_allocated_mb=128.0
        )

        throughput = monitor.get_current_throughput()
        assert throughput == 200000.0

    def test_get_average_throughput(self):
        """测试获取平均吞吐量"""
        monitor = GPUPerformanceMonitor()

        # 记录多个批次
        for i in range(5):
            monitor.record_kernel_metrics(
                batch_size=10000, execution_time_ms=50.0, memory_allocated_mb=128.0
            )

        avg = monitor.get_average_throughput(window_seconds=60.0)
        assert avg == 200000.0

    def test_record_memory_metrics(self):
        """测试记录显存指标"""
        monitor = GPUPerformanceMonitor()

        monitor.record_memory_metrics(
            used_memory_mb=1024.0, total_memory_mb=8192.0, allocation=True, pool_hit=True
        )

        memory = monitor.get_memory_usage()
        assert memory["used_mb"] == 1024.0
        assert memory["usage_percent"] == 12.5
        assert memory["pool_hit_rate"] == 100.0

    def test_get_performance_report(self):
        """测试获取性能报告"""
        monitor = GPUPerformanceMonitor()
        monitor.start()

        # 记录一些指标
        for i in range(10):
            monitor.record_kernel_metrics(
                batch_size=10000, execution_time_ms=50.0, memory_allocated_mb=128.0
            )

        report = monitor.get_performance_report()

        assert report.total_batches == 10
        assert report.total_keys_processed == 100000
        assert report.avg_throughput_keys_per_sec == 200000.0
        assert report.peak_throughput_keys_per_sec == 200000.0
        assert report.error_rate_percent == 0.0

        monitor.stop()

    def test_performance_degradation_detection(self):
        """测试性能退化检测"""
        monitor = GPUPerformanceMonitor(degradation_threshold=0.8)

        degradation_detected = [False]

        def on_degradation(metrics, ratio):
            degradation_detected[0] = True

        monitor.on_degradation(on_degradation)

        # P1修复后需要越过预热期（warmup_batches=10），且基准使用P50滑动窗口
        # 先注入足够的高性能批次建立温定基准
        for _ in range(12):
            monitor.record_kernel_metrics(
                batch_size=10000, execution_time_ms=50.0, memory_allocated_mb=128.0  # 200k keys/s
            )

        # 再记录严重退化性能（低于基准的 25%，远超退化阈值75%）
        monitor.record_kernel_metrics(
            batch_size=1000,
            execution_time_ms=200.0,  # 5k keys/s (2.5%，远低于阈值)
            memory_allocated_mb=128.0,
        )

        assert degradation_detected[0] is True

    def test_export_metrics_json(self):
        """测试导出JSON格式"""
        monitor = GPUPerformanceMonitor()

        monitor.record_kernel_metrics(
            batch_size=10000, execution_time_ms=50.0, memory_allocated_mb=128.0
        )

        json_data = monitor.export_metrics(format="json")
        assert "kernel_metrics" in json_data
        assert "memory_metrics" in json_data
        assert "device_info" in json_data

    def test_export_metrics_csv(self):
        """测试导出CSV格式"""
        monitor = GPUPerformanceMonitor()

        monitor.record_kernel_metrics(
            batch_size=10000, execution_time_ms=50.0, memory_allocated_mb=128.0
        )

        csv_data = monitor.export_metrics(format="csv")
        assert "batch_size" in csv_data
        assert "execution_time_ms" in csv_data

    def test_global_monitor_singleton(self):
        """测试全局监控器单例"""
        monitor1 = get_gpu_performance_monitor()
        monitor2 = get_gpu_performance_monitor()

        assert monitor1 is monitor2

    def test_reset_global_monitor(self):
        """测试重置全局监控器"""
        monitor1 = get_gpu_performance_monitor()
        reset_gpu_performance_monitor()
        monitor2 = get_gpu_performance_monitor()

        assert monitor1 is not monitor2


class TestGPUPerformanceReport:
    """GPU性能报告测试"""

    def test_creation(self):
        """测试创建"""
        report = GPUPerformanceReport(
            device_name="Test GPU",
            vendor="Test Vendor",
            monitoring_duration_sec=60.0,
            total_batches=100,
            total_keys_processed=1000000,
            avg_throughput_keys_per_sec=16666.67,
            peak_throughput_keys_per_sec=20000.0,
            avg_execution_time_ms=50.0,
            min_execution_time_ms=40.0,
            max_execution_time_ms=60.0,
            memory_usage_avg_mb=256.0,
            memory_usage_peak_mb=512.0,
            error_rate_percent=0.5,
            pool_hit_rate_percent=85.0,
            performance_stability_percent=90.0,
        )

        assert report.device_name == "Test GPU"
        assert report.total_batches == 100
        assert report.error_rate_percent == 0.5

    def test_to_dict(self):
        """测试转换为字典"""
        report = GPUPerformanceReport(
            device_name="Test GPU",
            vendor="Test Vendor",
            monitoring_duration_sec=60.0,
            total_batches=100,
            total_keys_processed=1000000,
            avg_throughput_keys_per_sec=16666.67,
            peak_throughput_keys_per_sec=20000.0,
            avg_execution_time_ms=50.0,
            min_execution_time_ms=40.0,
            max_execution_time_ms=60.0,
            memory_usage_avg_mb=256.0,
            memory_usage_peak_mb=512.0,
            error_rate_percent=0.5,
            pool_hit_rate_percent=85.0,
            performance_stability_percent=90.0,
        )

        d = report.to_dict()
        assert "device_name" in d
        assert "total_batches" in d
        assert d["device_name"] == "Test GPU"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
