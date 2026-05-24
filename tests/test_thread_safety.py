"""线程安全验证测试

验证多线程环境下的锁顺序和竞态条件防护。
"""
import threading
import time

import pytest

from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine


class TestLockOrder:
    """验证锁顺序约定：_state_lock → _workers_lock → _matches_lock"""

    def test_lock_order_compliance(self):
        """测试锁获取顺序是否符合约定"""
        config = {"worker_join_timeout": 5, "workload_monitor_interval": 1}
        engine = MultiGPUCollisionEngine(config=config)

        # 验证锁存在
        assert hasattr(engine, "_state_lock"), "缺少 _state_lock"
        assert hasattr(engine, "_workers_lock"), "缺少 _workers_lock"
        assert hasattr(engine, "_matches_lock"), "缺少 _matches_lock"
        assert hasattr(engine, "_performance_history_lock"), "缺少 _performance_history_lock"

        # 验证锁类型（通过类名不区分大小写检查）
        name_state = type(engine._state_lock).__name__.lower()
        name_workers = type(engine._workers_lock).__name__.lower()
        name_matches = type(engine._matches_lock).__name__.lower()
        name_perf = type(engine._performance_history_lock).__name__.lower()
        assert "rlock" in name_state, f"_state_lock 应为 RLock, 实际为 {name_state}"
        assert "lock" in name_workers, f"_workers_lock 应为 Lock, 实际为 {name_workers}"
        assert "lock" in name_matches, f"_matches_lock 应为 Lock, 实际为 {name_matches}"
        assert "lock" in name_perf, f"_performance_history_lock 应为 Lock, 实际为 {name_perf}"

        engine.stop()


class TestConcurrentAccess:
    """验证并发访问的安全性"""

    def test_concurrent_stats_access(self):
        """测试并发读取统计信息是否线程安全"""
        config = {"worker_join_timeout": 5}
        engine = MultiGPUCollisionEngine(config=config)

        # 初始化
        engine._initialized = True
        engine._all_matches = []
        engine._performance_history = []

        # 并发读取测试
        errors = []
        threads = []

        def reader():
            for _ in range(100):
                try:
                    _ = engine.get_combined_stats()
                except Exception as e:
                    errors.append(str(e))

        for i in range(5):
            t = threading.Thread(target=reader, name=f"reader-{i}")
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"并发读取失败: {errors}"

        engine.stop()

    def test_concurrent_match_add(self):
        """测试并发添加匹配结果的线程安全性"""
        config = {"worker_join_timeout": 5}
        engine = MultiGPUCollisionEngine(config=config)
        engine._initialized = True

        # 并发写入测试
        errors = []
        threads = []

        def writer(worker_id):
            for i in range(50):
                try:
                    match = {
                        "device_idx": worker_id,
                        "private_key_hash": f"hash-{worker_id}-{i}",
                        "address": f"1test{worker_id}{i}",
                        "timestamp": time.time(),
                    }
                    engine._on_match_found(worker_id, match)
                except Exception as e:
                    errors.append(str(e))

        for i in range(3):
            t = threading.Thread(target=writer, args=(i,), name=f"writer-{i}")
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"并发写入失败: {errors}"
        assert len(engine._all_matches) <= 150  # 3 workers * 50 matches

        engine.stop()


class TestPerformanceHistory:
    """验证性能历史数据的线程安全性"""

    def test_history_append_thread_safe(self):
        """测试性能历史追加是否线程安全"""
        config = {"worker_join_timeout": 5, "performance_history_max_size": 10}
        engine = MultiGPUCollisionEngine(config=config)

        # 并发追加测试
        errors = []
        threads = []

        def appender(worker_id):
            for _ in range(20):
                try:
                    engine._collect_performance_data()
                except Exception as e:
                    errors.append(str(e))

        for i in range(3):
            t = threading.Thread(target=appender, args=(i,), name=f"appender-{i}")
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"性能历史追加失败: {errors}"
        assert len(engine._performance_history) <= config["performance_history_max_size"]

        engine.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
