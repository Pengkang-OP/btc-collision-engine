# -*- coding: utf-8 -*-
"""
性能监控模块单元测试
"""
import pytest
import time
import threading
from src.monitoring.optimization_monitor import (
    OptimizationPerformanceMonitor,
    PerformanceMetrics,
    get_performance_monitor,
    reset_performance_monitor
)


class TestPerformanceMetrics:
    """性能指标数据类测试"""
    
    def test_creation(self):
        """测试创建"""
        metrics = PerformanceMetrics(
            timestamp=time.time(),
            addresses_generated=100,
            elapsed_time=10.0,
            speed=10.0,
            memory_usage_mb=50.0,
            optimization_enabled=True,
            precomputed_table=True,
            simd_hash=True,
            memory_pool=True,
            gpu_memory_pool=False
        )
        
        assert metrics.addresses_generated == 100
        assert metrics.speed == 10.0
        assert metrics.optimization_enabled == True
    
    def test_to_dict(self):
        """测试转换为字典"""
        metrics = PerformanceMetrics(
            timestamp=1234567890.0,
            addresses_generated=100,
            elapsed_time=10.0,
            speed=10.0,
            memory_usage_mb=50.0,
            optimization_enabled=True,
            precomputed_table=True,
            simd_hash=True,
            memory_pool=True,
            gpu_memory_pool=False
        )
        
        d = metrics.to_dict()
        
        assert 'timestamp' in d
        assert 'datetime' in d
        assert d['addresses_generated'] == 100
        assert d['speed'] == 10.0
        assert d['optimization_enabled'] == True


class TestOptimizationPerformanceMonitor:
    """性能监控器测试类"""
    
    def test_initialization(self):
        """测试初始化"""
        monitor = OptimizationPerformanceMonitor(
            check_interval=5.0,
            degradation_threshold=0.8,
            history_size=1000
        )
        
        assert monitor.check_interval == 5.0
        assert monitor.degradation_threshold == 0.8
        assert monitor.history_size == 1000
        assert monitor._peak_speed == 0.0
        assert monitor._total_addresses == 0
    
    def test_start_stop(self):
        """测试启动和停止"""
        monitor = OptimizationPerformanceMonitor()
        
        # 启动
        monitor.start()
        assert monitor._running == True
        assert monitor._thread is not None
        assert monitor._thread.is_alive()
        
        # 停止
        monitor.stop()
        assert monitor._running == False
    
    def test_record_metrics(self):
        """测试记录指标"""
        monitor = OptimizationPerformanceMonitor()
        
        monitor.record_metrics(
            addresses_generated=100,
            elapsed_time=10.0,
            optimization_enabled=True,
            precomputed_table=True,
            simd_hash=True,
            memory_pool=True
        )
        
        assert monitor._total_addresses == 100
        assert monitor._peak_speed == 10.0  # 100/10
        
        # 获取当前指标
        current = monitor.get_current_metrics()
        assert current is not None
        assert current.addresses_generated == 100
        assert current.speed == 10.0
    
    def test_peak_speed_tracking(self):
        """测试峰值速度跟踪"""
        monitor = OptimizationPerformanceMonitor()
        
        # 记录不同速度
        monitor.record_metrics(addresses_generated=100, elapsed_time=10.0)  # 10 addr/s
        monitor.record_metrics(addresses_generated=200, elapsed_time=10.0)  # 20 addr/s
        monitor.record_metrics(addresses_generated=150, elapsed_time=10.0)  # 15 addr/s
        
        assert monitor._peak_speed == 20.0
    
    def test_average_speed(self):
        """测试平均速度计算"""
        monitor = OptimizationPerformanceMonitor()
        
        # 记录多个指标
        monitor.record_metrics(addresses_generated=100, elapsed_time=10.0)  # 10 addr/s
        monitor.record_metrics(addresses_generated=200, elapsed_time=10.0)  # 20 addr/s
        monitor.record_metrics(addresses_generated=300, elapsed_time=10.0)  # 30 addr/s
        
        avg_speed = monitor.get_average_speed(window_seconds=60.0)
        assert avg_speed == 20.0  # (10+20+30)/3
    
    def test_performance_report(self):
        """测试性能报告生成"""
        monitor = OptimizationPerformanceMonitor()
        
        # 记录一些指标
        for i in range(5):
            monitor.record_metrics(
                addresses_generated=100,
                elapsed_time=10.0,
                optimization_enabled=True,
                precomputed_table=True,
                simd_hash=True,
                memory_pool=True,
                memory_usage_mb=50.0 + i
            )
        
        report = monitor.get_performance_report()
        
        assert report['status'] == 'stopped'
        assert report['summary']['total_addresses'] == 500
        assert report['summary']['avg_speed'] == 10.0
        assert report['optimization']['enabled_percentage'] == 100.0
        assert report['memory']['average_mb'] > 0
    
    def test_degradation_detection(self):
        """测试性能退化检测"""
        monitor = OptimizationPerformanceMonitor(degradation_threshold=0.8)
        
        degradation_detected = []
        
        def on_degradation(metrics, ratio):
            degradation_detected.append((metrics, ratio))
        
        monitor.on_degradation(on_degradation)
        
        # 记录正常性能
        monitor.record_metrics(addresses_generated=100, elapsed_time=10.0)  # 10 addr/s
        
        # 记录性能退化(下降30%)
        monitor.record_metrics(addresses_generated=70, elapsed_time=10.0)  # 7 addr/s
        
        assert len(degradation_detected) == 1
        assert degradation_detected[0][1] == 0.7  # 退化率70%
    
    def test_export_json(self):
        """测试JSON导出"""
        import json
        
        monitor = OptimizationPerformanceMonitor()
        
        monitor.record_metrics(addresses_generated=100, elapsed_time=10.0)
        monitor.record_metrics(addresses_generated=200, elapsed_time=10.0)
        
        json_data = monitor.export_metrics(format='json')
        data = json.loads(json_data)
        
        assert len(data) == 2
        assert data[0]['addresses_generated'] == 100
        assert data[1]['addresses_generated'] == 200
    
    def test_export_csv(self):
        """测试CSV导出"""
        monitor = OptimizationPerformanceMonitor()
        
        monitor.record_metrics(addresses_generated=100, elapsed_time=10.0)
        monitor.record_metrics(addresses_generated=200, elapsed_time=10.0)
        
        csv_data = monitor.export_metrics(format='csv')
        lines = csv_data.split('\n')
        
        assert len(lines) == 3  # 头部 + 2行数据
        assert 'addresses_generated' in lines[0]
        assert '100' in lines[1]
        assert '200' in lines[2]
    
    def test_thread_safety(self):
        """测试线程安全性"""
        monitor = OptimizationPerformanceMonitor()
        errors = []
        
        def worker():
            try:
                for _ in range(50):
                    monitor.record_metrics(
                        addresses_generated=10,
                        elapsed_time=1.0
                    )
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert monitor._total_addresses == 5000  # 10*50*10
    
    def test_history_size_limit(self):
        """测试历史记录大小限制"""
        monitor = OptimizationPerformanceMonitor(history_size=10)
        
        # 记录20个指标
        for i in range(20):
            monitor.record_metrics(
                addresses_generated=10,
                elapsed_time=1.0
            )
        
        assert len(monitor._metrics_history) == 10


class TestGlobalPerformanceMonitor:
    """全局性能监控器测试"""
    
    def setup_method(self):
        """每个测试前重置"""
        reset_performance_monitor()
    
    def test_get_performance_monitor(self):
        """测试获取全局监控器"""
        monitor1 = get_performance_monitor()
        monitor2 = get_performance_monitor()
        
        assert monitor1 is monitor2
    
    def test_reset_performance_monitor(self):
        """测试重置全局监控器"""
        monitor1 = get_performance_monitor()
        reset_performance_monitor()
        monitor2 = get_performance_monitor()
        
        assert monitor1 is not monitor2
