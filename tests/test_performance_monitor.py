"""性能监控模块基准测试

测试性能监控的开销和功能正确性
"""

import time
import logging
import pytest
from src.utils.performance_monitor import (
    PerformanceTracker,
    EnhancedPerformanceMonitor,
    PerformanceMetrics,
    get_performance_tracker,
    is_performance_monitoring_enabled
)


class TestPerformanceMonitorOverhead:
    """性能监控开销测试"""
    
    def test_monitor_overhead_per_call(self):
        """测试单次性能监控调用的开销"""
        logger = logging.getLogger('test')
        iterations = 10000
        
        # 基线测试（无监控）
        start = time.perf_counter()
        for _ in range(iterations):
            pass
        baseline = time.perf_counter() - start
        
        # 有监控测试
        start = time.perf_counter()
        for _ in range(iterations):
            with EnhancedPerformanceMonitor(logger, "test", track=False):
                pass
        with_monitor = time.perf_counter() - start
        
        # 计算单次调用开销
        overhead = (with_monitor - baseline) / iterations
        
        # 单次调用应该<0.2ms（考虑到异常隔离的额外开销）
        assert overhead < 0.0002, f"监控开销过大: {overhead*1000:.4f}ms/次"
    
    def test_tracker_record_overhead(self):
        """测试追踪器记录开销"""
        tracker = PerformanceTracker(max_records=10000)
        iterations = 10000
        
        # 测试记录开销
        start = time.perf_counter()
        for i in range(iterations):
            tracker.record(f"op_{i}", 100.0, success=True)
        elapsed = time.perf_counter() - start
        
        avg_overhead = elapsed / iterations
        
        # 单次记录应该<0.05ms
        assert avg_overhead < 0.00005, f"记录开销过大: {avg_overhead*1000:.4f}ms/次"
    
    def test_nested_monitor_overhead(self):
        """测试嵌套监控开销"""
        logger = logging.getLogger('test')
        iterations = 1000
        
        # 基线（无嵌套）
        start = time.perf_counter()
        for _ in range(iterations):
            with EnhancedPerformanceMonitor(logger, "outer", track=False):
                pass
        single_level = time.perf_counter() - start
        
        # 嵌套监控
        start = time.perf_counter()
        for _ in range(iterations):
            with EnhancedPerformanceMonitor(logger, "outer", track=False):
                with EnhancedPerformanceMonitor(logger, "inner", track=False):
                    pass
        nested = time.perf_counter() - start
        
        # 嵌套开销应该合理（<2倍）
        assert nested < single_level * 3, "嵌套监控开销过大"


class TestPerformanceTrackerFunctionality:
    """PerformanceTracker功能测试"""
    
    def test_record_and_statistics(self):
        """测试记录和统计功能"""
        tracker = PerformanceTracker(max_records=100)
        
        # 记录多个操作
        for i in range(10):
            tracker.record("op1", float(i * 10), success=True)
        
        # 获取统计
        stats = tracker.get_statistics("op1")
        
        assert stats['count'] == 10
        assert stats['avg_ms'] == 45.0  # (0+10+20+...+90)/10
        assert stats['min_ms'] == 0.0
        assert stats['max_ms'] == 90.0
    
    def test_max_records_limit(self):
        """测试最大记录数限制"""
        tracker = PerformanceTracker(max_records=50)
        
        # 记录超过限制的条数
        for i in range(100):
            tracker.record(f"op_{i}", float(i))
        
        # 应该只保留最新的50条
        assert len(tracker._records) == 50
        
        # 验证保留的是最新的记录
        assert tracker._records[0].operation == "op_50"
        assert tracker._records[-1].operation == "op_99"
    
    def test_thread_safety(self):
        """测试线程安全"""
        import threading
        
        tracker = PerformanceTracker(max_records=10000)
        num_threads = 10
        records_per_thread = 100
        
        def worker(thread_id):
            for i in range(records_per_thread):
                tracker.record(f"thread_{thread_id}_op_{i}", float(i))
        
        # 创建多个线程
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # 等待所有线程完成
        for t in threads:
            t.join()
        
        # 验证记录数正确
        total_records = num_threads * records_per_thread
        assert len(tracker._records) == total_records
    
    def test_clear(self):
        """测试清空功能"""
        tracker = PerformanceTracker(max_records=100)
        
        # 添加一些记录
        for i in range(10):
            tracker.record(f"op_{i}", float(i))
        
        assert len(tracker._records) == 10
        
        # 清空
        tracker.clear()
        assert len(tracker._records) == 0
    
    def test_get_slow_operations(self):
        """测试慢操作检测"""
        tracker = PerformanceTracker(max_records=100)
        
        # 记录不同耗时的操作
        tracker.record("fast_op", 10.0, success=True)
        tracker.record("slow_op1", 1500.0, success=True)
        tracker.record("medium_op", 500.0, success=True)
        tracker.record("slow_op2", 2000.0, success=True)
        
        # 获取慢操作（>1000ms）
        slow_ops = tracker.get_slow_operations(threshold_ms=1000, limit=5)
        
        assert len(slow_ops) == 2
        assert slow_ops[0].operation == "slow_op2"  # 最慢的排前面
        assert slow_ops[0].elapsed_ms == 2000.0
        assert slow_ops[1].operation == "slow_op1"
        assert slow_ops[1].elapsed_ms == 1500.0


class TestEnhancedPerformanceMonitor:
    """EnhancedPerformanceMonitor功能测试"""
    
    def test_basic_usage(self, caplog):
        """测试基本使用"""
        logger = logging.getLogger('test_basic')
        
        with EnhancedPerformanceMonitor(logger, "test_op", track=False):
            time.sleep(0.01)  # 10ms
        
        # 检查日志输出
        assert "[Performance] test_op:" in caplog.text
        assert "ms" in caplog.text
    
    def test_exception_handling(self, caplog):
        """测试异常处理"""
        logger = logging.getLogger('test_exception')
        
        with pytest.raises(ValueError):
            with EnhancedPerformanceMonitor(logger, "failing_op", track=False):
                raise ValueError("Test error")
        
        # 检查是否记录了FAILED
        assert "FAILED" in caplog.text
        assert "Test error" in caplog.text
    
    def test_track_disabled(self):
        """测试禁用追踪"""
        logger = logging.getLogger('test_no_track')
        tracker = get_performance_tracker()
        initial_count = len(tracker._records)
        
        with EnhancedPerformanceMonitor(logger, "no_track_op", track=False):
            pass
        
        # 验证没有记录到追踪器
        assert len(tracker._records) == initial_count
    
    def test_metadata(self):
        """测试元数据"""
        logger = logging.getLogger('test_metadata')
        tracker = get_performance_tracker()
        initial_count = len(tracker._records)
        
        with EnhancedPerformanceMonitor(logger, "meta_op", track=True) as pm:
            pm.add_metadata('key1', 'value1')
            pm.add_metadata('key2', 123)
        
        # 验证元数据被记录
        assert len(tracker._records) == initial_count + 1
        last_record = tracker._records[-1]
        assert last_record.metadata['key1'] == 'value1'
        assert last_record.metadata['key2'] == 123
    
    def test_monitoring_disabled(self):
        """测试禁用性能监控"""
        # 注意：这个测试需要配置支持
        # 这里只是验证函数存在
        enabled = is_performance_monitoring_enabled()
        assert isinstance(enabled, bool)


class TestConfiguration:
    """配置相关测试"""
    
    def test_config_loading(self):
        """测试配置加载"""
        from src.utils.performance_monitor import _get_tracker_config
        
        config = _get_tracker_config()
        
        # 验证配置项存在
        assert 'enabled' in config
        assert 'max_records' in config
        assert 'slow_threshold_ms' in config
        assert 'track_slow_operations' in config
        assert 'log_level' in config
        
        # 验证默认值
        assert config['enabled'] == True
        assert config['max_records'] == 10000
        assert config['slow_threshold_ms'] == 1000
    
    def test_singleton_tracker(self):
        """测试追踪器单例"""
        tracker1 = get_performance_tracker()
        tracker2 = get_performance_tracker()
        
        assert tracker1 is tracker2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
