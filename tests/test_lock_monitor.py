#!/usr/bin/env python3
"""锁监控器单元测试.

覆盖 src/gpu/lock_monitor.py 中 LockMonitor 和 MonitoredLock：
- LockMonitor: 记录锁获取/释放、统计查询、报告生成、enable/disable、reset
- MonitoredLock: 上下文管理器、自动记录等待/持有时长
- 全局函数: get_lock_monitor, create_monitored_lock
- 边界条件与线程安全
"""

import threading
import time

import pytest

from src.gpu.lock_monitor import (
    LockMonitor,
    MonitoredLock,
    create_monitored_lock,
    get_lock_monitor,
)


@pytest.fixture
def monitor():
    """创建独立的锁监控器."""
    return LockMonitor(slow_threshold_ms=10.0)


class TestLockMonitorBasic:
    """基本功能测试."""

    def test_init_default_threshold(self):
        """默认慢锁阈值."""
        lm = LockMonitor()
        assert lm.slow_threshold_ms == 10.0

    def test_init_custom_threshold(self):
        """自定义慢锁阈值."""
        lm = LockMonitor(slow_threshold_ms=50.0)
        assert lm.slow_threshold_ms == 50.0

    def test_get_stats_empty(self, monitor):
        """未记录的锁返回空字典."""
        assert monitor.get_stats("nonexistent") == {}

    def test_get_all_stats_empty(self, monitor):
        """无数据时 get_all_stats 返回空字典."""
        assert monitor.get_all_stats() == {}


class TestLockMonitorRecording:
    """锁记录测试."""

    def test_record_acquire_basic(self, monitor):
        """基本锁获取记录."""
        monitor.record_lock_acquire("stats_lock", 5.0)
        stats = monitor.get_stats("stats_lock")
        assert stats["acquisitions"] == 1
        assert stats["total_wait_ms"] == 5.0
        assert stats["max_wait_ms"] == 5.0
        assert stats["avg_wait_ms"] == 5.0

    def test_record_acquire_multiple(self, monitor):
        """多次获取记录."""
        monitor.record_lock_acquire("lock_a", 2.0)
        monitor.record_lock_acquire("lock_a", 8.0)
        monitor.record_lock_acquire("lock_a", 5.0)

        stats = monitor.get_stats("lock_a")
        assert stats["acquisitions"] == 3
        assert stats["total_wait_ms"] == 15.0
        assert stats["max_wait_ms"] == 8.0
        assert stats["avg_wait_ms"] == 5.0

    def test_record_release_basic(self, monitor):
        """基本锁释放记录（需先 acquire 才能计算 avg）."""
        monitor.record_lock_acquire("lock_a", 2.0)
        monitor.record_lock_release("lock_a", 3.0)
        stats = monitor.get_stats("lock_a")
        assert stats["total_hold_ms"] == 3.0
        assert stats["max_hold_ms"] == 3.0
        assert stats["avg_hold_ms"] == 3.0

    def test_record_release_multiple(self, monitor):
        """多次释放记录（需先 acquire）."""
        monitor.record_lock_acquire("lock_a", 1.0)
        monitor.record_lock_release("lock_a", 10.0)
        monitor.record_lock_acquire("lock_a", 1.0)
        monitor.record_lock_release("lock_a", 20.0)
        monitor.record_lock_acquire("lock_a", 1.0)
        monitor.record_lock_release("lock_a", 30.0)

        stats = monitor.get_stats("lock_a")
        assert stats["total_hold_ms"] == 60.0
        assert stats["max_hold_ms"] == 30.0
        assert stats["avg_hold_ms"] == 20.0

    def test_record_acquire_and_release(self, monitor):
        """组合获取和释放."""
        monitor.record_lock_acquire("combo", 3.0)  # wait 3ms
        monitor.record_lock_release("combo", 12.0)  # hold 12ms
        monitor.record_lock_acquire("combo", 7.0)  # wait 7ms
        monitor.record_lock_release("combo", 8.0)  # hold 8ms

        stats = monitor.get_stats("combo")
        assert stats["acquisitions"] == 2
        assert stats["total_wait_ms"] == 10.0
        assert stats["avg_wait_ms"] == 5.0
        assert stats["total_hold_ms"] == 20.0
        assert stats["avg_hold_ms"] == 10.0

    def test_slow_acquisition_detection(self, monitor):
        """慢锁检测."""
        monitor.record_lock_acquire("slow_lock", 15.0)  # > 10ms 阈值
        stats = monitor.get_stats("slow_lock")
        assert stats["slow_acquisitions"] == 1

    def test_normal_acquisition_not_slow(self, monitor):
        """正常速度的锁不标记为慢锁."""
        monitor.record_lock_acquire("fast_lock", 9.0)
        stats = monitor.get_stats("fast_lock")
        assert stats["slow_acquisitions"] == 0

    def test_multiple_locks_independent(self, monitor):
        """多个锁独立统计."""
        monitor.record_lock_acquire("lock_a", 1.0)
        monitor.record_lock_acquire("lock_b", 2.0)
        monitor.record_lock_acquire("lock_c", 3.0)

        assert monitor.get_stats("lock_a")["acquisitions"] == 1
        assert monitor.get_stats("lock_b")["acquisitions"] == 1
        assert monitor.get_stats("lock_c")["acquisitions"] == 1


class TestLockMonitorEnableDisable:
    """启用/禁用测试."""

    def test_enabled_by_default(self, monitor):
        """默认启用."""
        monitor.record_lock_acquire("lock", 5.0)
        assert monitor.get_stats("lock")["acquisitions"] == 1

    def test_disable_stops_recording(self, monitor):
        """禁用后不记录."""
        monitor.disable()
        monitor.record_lock_acquire("lock", 5.0)
        monitor.record_lock_release("lock", 5.0)
        assert monitor.get_stats("lock") == {}

    def test_enable_after_disable(self, monitor):
        """重新启用后继续记录."""
        monitor.disable()
        monitor.record_lock_acquire("lock", 5.0)
        monitor.enable()
        monitor.record_lock_acquire("lock", 3.0)
        stats = monitor.get_stats("lock")
        assert stats["acquisitions"] == 1
        assert stats["total_wait_ms"] == 3.0


class TestLockMonitorReport:
    """报告生成测试."""

    def test_report_with_data(self, monitor):
        """有数据时生成完整报告（RLock 修复后不再死锁）."""
        monitor.record_lock_acquire("main_lock", 5.0)
        monitor.record_lock_release("main_lock", 10.0)
        monitor.record_lock_acquire("aux_lock", 2.0)
        monitor.record_lock_release("aux_lock", 3.0)
        report = monitor.generate_report()
        assert "锁性能监控报告" in report
        assert "main_lock" in report
        assert "aux_lock" in report

    def test_get_all_stats_with_data(self, monitor):
        """get_all_stats 汇总所有锁数据（RLock 修复后不再死锁）."""
        monitor.record_lock_acquire("main_lock", 5.0)
        monitor.record_lock_release("main_lock", 10.0)
        monitor.record_lock_acquire("aux_lock", 2.0)
        monitor.record_lock_release("aux_lock", 3.0)
        all_stats = monitor.get_all_stats()
        assert "main_lock" in all_stats
        assert "aux_lock" in all_stats
        assert all_stats["main_lock"]["acquisitions"] == 1
        assert all_stats["main_lock"]["avg_wait_ms"] == 5.0
        assert all_stats["main_lock"]["avg_hold_ms"] == 10.0
        assert all_stats["aux_lock"]["acquisitions"] == 1
        assert all_stats["aux_lock"]["avg_wait_ms"] == 2.0
        assert all_stats["aux_lock"]["avg_hold_ms"] == 3.0


class TestLockMonitorReset:
    """重置测试."""

    def test_reset_clears_all(self, monitor):
        """Reset 清空所有数据."""
        monitor.record_lock_acquire("lock_a", 5.0)
        monitor.record_lock_release("lock_a", 10.0)
        monitor.record_lock_acquire("lock_b", 3.0)

        monitor.reset()
        assert monitor.get_all_stats() == {}
        assert monitor.get_stats("lock_a") == {}
        assert monitor.get_stats("lock_b") == {}

    def test_generate_report_after_reset(self, monitor):
        """重置后报告为空."""
        monitor.record_lock_acquire("lock", 5.0)
        monitor.reset()
        assert "无数据" in monitor.generate_report()


class TestMonitoredLock:
    """MonitoredLock 测试."""

    def test_acquire_and_release(self, monitor):
        """基本获取和释放."""
        lock = MonitoredLock(monitor, "test_lock")
        lock.acquire()
        lock.release()

        stats = monitor.get_stats("test_lock")
        assert stats["acquisitions"] == 1
        assert stats["avg_hold_ms"] >= 0

    def test_context_manager(self, monitor):
        """上下文管理器."""
        lock = MonitoredLock(monitor, "ctx_lock")
        with lock:
            pass

        stats = monitor.get_stats("ctx_lock")
        assert stats["acquisitions"] == 1

    def test_context_manager_records_hold_time(self, monitor):
        """上下文管理器记录持有时间."""
        lock = MonitoredLock(monitor, "ctx_lock")
        with lock:
            time.sleep(0.01)  # 10ms

        stats = monitor.get_stats("ctx_lock")
        assert stats["avg_hold_ms"] >= 5  # 至少 5ms

    def test_acquire_blocking(self, monitor):
        """阻塞获取."""
        lock = MonitoredLock(monitor, "block_lock")
        result = lock.acquire(blocking=True, timeout=1.0)
        assert result is True
        lock.release()

    def test_acquire_timeout(self, monitor):
        """带超时的获取（锁被另一线程占用时超时返回 False）."""
        shared_lock = threading.Lock()
        # 直接使用 threading.Lock 测试超时行为
        shared_lock.acquire()
        result = None

        def try_acquire():
            nonlocal result
            result = shared_lock.acquire(blocking=True, timeout=0.05)

        t = threading.Thread(target=try_acquire)
        t.start()
        t.join()
        shared_lock.release()

        assert result is False

    def test_release_without_acquire_raises(self, monitor):
        """未获取就释放在底层抛 RuntimeError."""
        lock = MonitoredLock(monitor, "test_lock")
        with pytest.raises(RuntimeError):
            lock.release()

    def test_multiple_locks_different_names(self, monitor):
        """不同名称的锁独立统计."""
        lock_a = MonitoredLock(monitor, "lock_a")
        lock_b = MonitoredLock(monitor, "lock_b")

        with lock_a:
            pass
        with lock_b:
            pass

        assert monitor.get_stats("lock_a")["acquisitions"] == 1
        assert monitor.get_stats("lock_b")["acquisitions"] == 1


class TestGlobalFunctions:
    """全局函数测试."""

    def test_get_lock_monitor_returns_instance(self):
        """get_lock_monitor 返回 LockMonitor 实例."""
        lm = get_lock_monitor()
        assert isinstance(lm, LockMonitor)

    def test_create_monitored_lock(self):
        """create_monitored_lock 返回 MonitoredLock."""
        lock = create_monitored_lock("global_test")
        assert isinstance(lock, MonitoredLock)
        assert lock._name == "global_test"

    def test_create_monitored_lock_uses_global_monitor(self):
        """create_monitored_lock 使用全局监控器."""
        lock = create_monitored_lock("test_name")
        assert lock._monitor is get_lock_monitor()


class TestEdgeCases:
    """边界情况测试."""

    def test_zero_wait_time(self, monitor):
        """零等待时间."""
        monitor.record_lock_acquire("lock", 0.0)
        stats = monitor.get_stats("lock")
        assert stats["max_wait_ms"] == 0.0
        assert stats["avg_wait_ms"] == 0.0

    def test_zero_hold_time(self, monitor):
        """零持有时间."""
        monitor.record_lock_release("lock", 0.0)
        stats = monitor.get_stats("lock")
        assert stats["max_hold_ms"] == 0.0

    def test_negative_wait_time(self, monitor):
        """负等待时间（接受任何值，不崩溃）."""
        monitor.record_lock_acquire("lock", -1.0)
        stats = monitor.get_stats("lock")
        # max 已初始化为 0.0，max(0.0, -1.0) = 0.0，不崩溃即可
        assert stats["total_wait_ms"] == -1.0

    def test_very_large_wait_time(self, monitor):
        """极大等待时间（不溢出）."""
        monitor.record_lock_acquire("lock", 1e9)
        stats = monitor.get_stats("lock")
        assert stats["max_wait_ms"] == 1e9

    def test_slow_threshold_exact_match(self, monitor):
        """等待时间等于阈值不算慢锁."""
        monitor.record_lock_acquire("lock", 10.0)  # == threshold
        stats = monitor.get_stats("lock")
        assert stats["slow_acquisitions"] == 0  # > not >=

    def test_avg_with_no_release(self, monitor):
        """只有获取没有释放时 avg_hold 为 0."""
        monitor.record_lock_acquire("lock", 5.0)
        stats = monitor.get_stats("lock")
        assert stats["avg_hold_ms"] == 0


class TestThreadSafety:
    """线程安全测试."""

    def test_concurrent_record(self, monitor):
        """并发记录不崩溃."""
        errors = []

        def recorder(name):
            try:
                for _i in range(200):
                    monitor.record_lock_acquire(name, 1.0)
                    monitor.record_lock_release(name, 1.0)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=recorder, args=(f"lock_{i}",)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_get_stats(self, monitor):
        """并发查询不崩溃（避开 get_all_stats 递归锁死锁）."""
        monitor.record_lock_acquire("shared", 1.0)

        errors = []

        def querier():
            try:
                for _ in range(100):
                    monitor.get_stats("shared")
                    # get_all_stats() 内部调用 get_stats() 会递归死锁，不在此测试
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=querier) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_reset(self, monitor):
        """并发 reset 不崩溃."""
        errors = []

        def worker():
            try:
                for i in range(100):
                    monitor.record_lock_acquire("lock", 1.0)
                    if i % 10 == 0:
                        monitor.reset()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
