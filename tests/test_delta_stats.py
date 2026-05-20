#!/usr/bin/env python3
"""增量统计 (DeltaStats / ThreadLocalDeltaStats) 单元测试

覆盖：
- DeltaStats: 初始化、queue_update、flush_loop、_flush_updates
- DeltaStats: get_stats、reset、stop、派生指标
- ThreadLocalDeltaStats: 线程本地缓冲、add_check/add_match/add_error
- ThreadLocalDeltaStats: flush_to_global、get_global_stats
- 边界值：空更新、大增量、并发安全、stop 后操作
"""

import threading
import time

import pytest

from src.collision.delta_stats import DeltaStats, ThreadLocalDeltaStats

# ============================================================================
# DeltaStats 测试
# ============================================================================

@pytest.mark.unit
class TestDeltaStatsInit:
    """DeltaStats 初始化测试"""

    def test_default_initialization(self):
        """测试默认初始化"""
        ds = DeltaStats()
        assert ds._stats["total_checked"] == 0
        assert ds._stats["matches_found"] == 0
        assert ds._stats["gpu_errors"] == 0
        assert ds._delta_queue == []

    def test_custom_flush_interval(self):
        """测试自定义刷新间隔"""
        ds = DeltaStats(flush_interval=0.5)
        assert ds._flush_interval == 0.5

    def test_stop_event_initialized(self):
        """测试停止事件已初始化"""
        ds = DeltaStats()
        assert not ds._stop_event.is_set()

    def test_flush_thread_started(self):
        """测试刷新线程已启动"""
        ds = DeltaStats()
        assert ds._flush_thread.is_alive()

    def test_flush_thread_daemon(self):
        """测试刷新线程为 daemon 线程"""
        ds = DeltaStats()
        assert ds._flush_thread.daemon is True


@pytest.mark.unit
class TestDeltaStatsQueueUpdate:
    """queue_update 测试"""

    def test_single_update(self):
        """测试单个增量更新"""
        ds = DeltaStats(flush_interval=0.01)
        ds.queue_update({"total_checked": 100})
        # 等待 flush
        time.sleep(0.05)
        stats = ds.get_stats()
        assert stats["total_checked"] == 100

    def test_multiple_updates_same_key(self):
        """测试相同键多次更新累加"""
        ds = DeltaStats(flush_interval=0.01)
        ds.queue_update({"total_checked": 50})
        ds.queue_update({"total_checked": 50})
        time.sleep(0.05)
        stats = ds.get_stats()
        assert stats["total_checked"] == 100

    def test_multiple_updates_different_keys(self):
        """测试不同键的更新"""
        ds = DeltaStats(flush_interval=0.01)
        ds.queue_update({"total_checked": 100, "matches_found": 5})
        ds.queue_update({"gpu_errors": 2, "worker_errors": 1})
        time.sleep(0.05)
        stats = ds.get_stats()
        assert stats["total_checked"] == 100
        assert stats["matches_found"] == 5
        assert stats["gpu_errors"] == 2
        assert stats["worker_errors"] == 1

    def test_empty_update_no_error(self):
        """测试空字典更新不报错"""
        ds = DeltaStats(flush_interval=0.01)
        ds.queue_update({})
        time.sleep(0.05)
        stats = ds.get_stats()
        assert stats["total_checked"] == 0

    def test_unknown_key_ignored(self):
        """测试未知键被忽略"""
        ds = DeltaStats(flush_interval=0.01)
        ds.queue_update({"unknown_field": 999})
        time.sleep(0.05)
        stats = ds.get_stats()
        assert "unknown_field" not in stats

    # ── 边界值 ──

    def test_large_delta(self):
        """测试大增量值"""
        ds = DeltaStats(flush_interval=0.01)
        ds.queue_update({"total_checked": 10**9})
        time.sleep(0.05)
        stats = ds.get_stats()
        assert stats["total_checked"] == 10**9

    def test_zero_delta(self):
        """测试零增量"""
        ds = DeltaStats(flush_interval=0.01)
        ds.queue_update({"total_checked": 0})
        time.sleep(0.05)
        stats = ds.get_stats()
        assert stats["total_checked"] == 0


@pytest.mark.unit
class TestDeltaStatsDerivedMetrics:
    """派生指标测试"""

    def test_elapsed_time_updated(self):
        """测试 elapsed_time 被更新"""
        ds = DeltaStats(flush_interval=0.01)
        ds.queue_update({"total_checked": 100})
        time.sleep(0.05)
        stats = ds.get_stats()
        assert stats["elapsed_time"] > 0

    def test_throughput_calculated(self):
        """测试吞吐量计算"""
        ds = DeltaStats(flush_interval=0.01)
        # 设置 start_time 为过去
        ds._stats["start_time"] = time.time() - 10
        ds.queue_update({"total_checked": 10000})
        time.sleep(0.05)
        stats = ds.get_stats()
        assert stats["throughput"] > 0

    def test_throughput_zero_when_no_checks(self):
        """测试无检查时吞吐量为 0"""
        ds = DeltaStats(flush_interval=0.01)
        time.sleep(0.05)
        stats = ds.get_stats()
        assert stats["throughput"] == 0.0


@pytest.mark.unit
class TestDeltaStatsReset:
    """reset 测试"""

    def test_reset_clears_all(self):
        """测试重置清除所有数据"""
        ds = DeltaStats(flush_interval=0.01)
        ds.queue_update({"total_checked": 100, "matches_found": 10})
        time.sleep(0.05)
        ds.reset()
        stats = ds.get_stats()
        assert stats["total_checked"] == 0
        assert stats["matches_found"] == 0
        assert ds._delta_queue == []

    def test_reset_updates_start_time(self):
        """测试重置更新 start_time"""
        ds = DeltaStats(flush_interval=0.01)
        old_start = ds._stats["start_time"]
        time.sleep(0.01)
        ds.reset()
        assert ds._stats["start_time"] >= old_start

    def test_reset_then_reuse(self):
        """测试重置后可正常使用"""
        ds = DeltaStats(flush_interval=0.01)
        ds.queue_update({"total_checked": 100})
        time.sleep(0.05)
        ds.reset()
        ds.queue_update({"total_checked": 50})
        time.sleep(0.05)
        stats = ds.get_stats()
        assert stats["total_checked"] == 50


@pytest.mark.unit
class TestDeltaStatsStop:
    """stop 测试"""

    def test_stop_sets_event(self):
        """测试 stop 设置停止事件"""
        ds = DeltaStats()
        ds.stop()
        assert ds._stop_event.is_set()

    def test_stop_flushes_remaining(self):
        """测试 stop 刷新剩余更新"""
        ds = DeltaStats(flush_interval=0.01)
        ds.queue_update({"total_checked": 500})
        # 直接停止（跳过定时刷新）
        ds.stop()
        stats = ds.get_stats()
        assert stats["total_checked"] == 500

    def test_stop_joins_thread(self):
        """测试 stop 后线程已退出"""
        ds = DeltaStats()
        ds.stop()
        # 线程应该已经停止
        ds._flush_thread.join(timeout=1.0)
        assert not ds._flush_thread.is_alive()


# ============================================================================
# ThreadLocalDeltaStats 测试
# ============================================================================

@pytest.mark.unit
class TestThreadLocalDeltaStats:
    """ThreadLocalDeltaStats 测试"""

    def test_add_check(self):
        """测试 add_check"""
        tds = ThreadLocalDeltaStats()
        tds.add_check(5)
        buffer = tds._get_thread_buffer()
        assert buffer["total_checked"] == 5

    def test_add_check_default_count(self):
        """测试 add_check 默认 count=1"""
        tds = ThreadLocalDeltaStats()
        tds.add_check()
        buffer = tds._get_thread_buffer()
        assert buffer["total_checked"] == 1

    def test_add_match(self):
        """测试 add_match"""
        tds = ThreadLocalDeltaStats()
        tds.add_match()
        tds.add_match()
        buffer = tds._get_thread_buffer()
        assert buffer["matches_found"] == 2

    def test_add_error_known_type(self):
        """测试 add_error 已知类型"""
        tds = ThreadLocalDeltaStats()
        tds.add_error("gpu_errors")
        tds.add_error("gpu_errors")
        buffer = tds._get_thread_buffer()
        assert buffer["gpu_errors"] == 2

    def test_add_error_unknown_type(self):
        """测试 add_error 未知类型被忽略"""
        tds = ThreadLocalDeltaStats()
        tds.add_error("unknown_error")
        buffer = tds._get_thread_buffer()
        # 未知类型不被添加到缓冲区
        assert "unknown_error" not in buffer

    def test_thread_local_isolation(self):
        """测试线程本地隔离"""
        tds = ThreadLocalDeltaStats()
        results = []

        def worker(tid: int):
            tds.add_check(tid * 100)
            buffer = tds._get_thread_buffer()
            results.append((tid, buffer["total_checked"]))

        t1 = threading.Thread(target=worker, args=(1,))
        t2 = threading.Thread(target=worker, args=(2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # 每个线程应有独立的缓冲区
        values = sorted([v for _, v in results])
        assert values == [100, 200]

    def test_flush_to_global(self):
        """测试 flush_to_global"""
        tds = ThreadLocalDeltaStats()
        # ThreadLocalDeltaStats 内部 DeltaStats 使用默认 flush_interval=0.1s
        tds.add_check(100)
        tds.add_match()

        tds.flush_to_global()
        # 等待后台刷新线程处理 (默认 flush_interval=0.1s)
        time.sleep(0.3)
        global_stats = tds.get_global_stats()
        assert global_stats["total_checked"] >= 100
        assert global_stats["matches_found"] >= 1

    def test_flush_clears_buffer(self):
        """测试 flush 后清除缓冲区"""
        tds = ThreadLocalDeltaStats()
        tds.add_check(50)
        tds.flush_to_global()

        buffer = tds._get_thread_buffer()
        assert buffer["total_checked"] == 0

    def test_flush_empty_buffer(self):
        """测试空缓冲区 flush 不报错"""
        tds = ThreadLocalDeltaStats()
        # 不应抛出异常
        tds.flush_to_global()

    def test_flush_multiple_times(self):
        """测试多次 flush"""
        tds = ThreadLocalDeltaStats()
        for i in range(3):
            tds.add_check(10)
            tds.flush_to_global()
            time.sleep(0.15)  # 每个周期等待足够时间让后台线程刷新

        global_stats = tds.get_global_stats()
        assert global_stats["total_checked"] >= 30

    def test_stop(self):
        """测试 stop 刷新并停止"""
        tds = ThreadLocalDeltaStats()
        tds.add_check(200)
        tds.add_match()
        tds.stop()

        # stop 调用内部 _global_stats.stop()，该函数会先设置 stop_event，
        # 然后 join 线程并调用 _flush_updates() 刷新剩余数据
        global_stats = tds.get_global_stats()
        assert global_stats["total_checked"] >= 200
        assert global_stats["matches_found"] >= 1
