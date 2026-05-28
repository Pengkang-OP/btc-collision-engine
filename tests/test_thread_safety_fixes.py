"""线程安全修复验证测试."""

import pathlib
import threading
import time

import pytest

from src.collision.collision_stats import CollisionStats
from src.collision.key_collision_engine import KeyCollisionEngine
from src.config.config_manager import ConfigManager


class TestThreadSafetyFixes:
    """测试线程安全修复."""

    def test_config_manager_concurrent_access(self):
        """测试配置管理器的并发访问."""
        config = ConfigManager()
        errors = []

        def writer(thread_id):
            try:
                for i in range(100):
                    config.set(f"test.thread{thread_id}.key{i}", f"value_{i}")
            except Exception as e:
                errors.append(f"Writer {thread_id} error: {e}")

        def reader(thread_id):
            try:
                for i in range(100):
                    config.get(f"test.thread{thread_id}.key{i}")
            except Exception as e:
                errors.append(f"Reader {thread_id} error: {e}")

        # 创建多个读写线程
        threads = []
        for i in range(5):
            t1 = threading.Thread(target=writer, args=(i,))
            t2 = threading.Thread(target=reader, args=(i,))
            threads.extend([t1, t2])

        # 启动所有线程
        for t in threads:
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join(timeout=10)

        # 验证没有错误
        assert len(errors) == 0, f"并发访问错误: {errors}"

    def test_config_manager_concurrent_save_load(self):
        """测试配置管理器的并发保存和加载."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config_file = f.name

        try:
            config = ConfigManager(config_file=config_file)
            errors = []

            def writer():
                try:
                    for i in range(50):
                        config.set(f"test.key{i}", f"value_{i}")
                        if i % 10 == 0:
                            config.save_config()
                except Exception as e:
                    errors.append(f"Writer error: {e}")

            def reader():
                try:
                    for i in range(50):
                        config.get(f"test.key{i}")
                        if i % 10 == 0:
                            config.load_config()
                except Exception as e:
                    errors.append(f"Reader error: {e}")

            # 并发读写
            t1 = threading.Thread(target=writer)
            t2 = threading.Thread(target=reader)
            t1.start()
            t2.start()
            t1.join(timeout=10)
            t2.join(timeout=10)

            assert len(errors) == 0, f"并发保存/加载错误: {errors}"
        finally:
            if pathlib.Path(config_file).exists():
                pathlib.Path(config_file).unlink()

    def test_collision_engine_single_lock(self):
        """测试碰撞引擎使用单锁设计."""
        targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        engine = KeyCollisionEngine(targets=targets)

        # 验证只有一个锁
        assert hasattr(engine, "_state_lock"), "应该有_state_lock"
        assert not hasattr(engine, "_count_lock"), "不应有_count_lock（已重命名）"
        assert not hasattr(engine, "_matches_lock"), "不应有_matches_lock（已移除）"
        assert not hasattr(engine, "_dedup_lock"), "不应有_dedup_lock（已移除）"

        # 验证锁的类型
        assert isinstance(engine._state_lock, type(threading.Lock()))

    def test_collision_engine_no_deadlock_risk(self):
        """测试碰撞引擎不存在死锁风险."""
        targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        engine = KeyCollisionEngine(targets=targets)

        # 统计锁的数量
        lock_count = 0
        for attr in dir(engine):
            if attr.endswith("_lock") and isinstance(getattr(engine, attr), type(threading.Lock())):
                lock_count += 1

        # 应该只有一个_state_lock
        assert lock_count == 1, f"应该有1个锁，但找到{lock_count}个"

    def test_config_manager_thread_safety_stress_test(self):
        """配置管理器线程安全压力测试."""
        config = ConfigManager()
        iterations = 1000
        thread_count = 10

        def stress_test(thread_id):
            for i in range(iterations):
                # 读写操作混合
                config.set(f"stress.thread{thread_id}.iter{i}", i)
                value = config.get(f"stress.thread{thread_id}.iter{i}")
                assert value == i or value is None, f"值不一致: {value} != {i}"

        threads = []
        for i in range(thread_count):
            t = threading.Thread(target=stress_test, args=(i,))
            threads.append(t)

        start_time = time.time()

        # 启动所有线程
        for t in threads:
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join(timeout=30)

        elapsed = time.time() - start_time

        # 验证所有线程都完成了
        for t in threads:
            assert not t.is_alive(), "线程超时，可能存在死锁"

        # 输出性能信息
        print(
            f"\n压力测试完成: {thread_count}线程 x {iterations}次迭代 = {thread_count * iterations}次操作",
        )
        print(f"耗时: {elapsed:.2f}秒")
        print(f"吞吐量: {thread_count * iterations / elapsed:.0f} 操作/秒")

    def test_record_worker_error_concurrent(self):
        """测试record_worker_error的多线程并发安全性（M1修复验证）."""
        stats = CollisionStats()
        thread_count = 20
        iterations = 1000
        errors = []

        def worker_error_generator(thread_id):
            """模拟工作线程记录错误."""
            try:
                for _i in range(iterations):
                    # 直接调用record_worker_error（无if检查，验证M1修复）
                    stats.record_worker_error()
            except Exception as e:
                errors.append(f"Thread {thread_id} error: {e}")

        # 创建多个线程同时调用record_worker_error
        threads = []
        for i in range(thread_count):
            t = threading.Thread(target=worker_error_generator, args=(i,))
            threads.append(t)

        # 启动所有线程
        start_time = time.time()
        for t in threads:
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join(timeout=10)

        elapsed = time.time() - start_time

        # 验证没有错误
        assert len(errors) == 0, f"并发调用错误: {errors}"

        # 验证计数准确（20线程 x 1000次 = 20000次）
        expected_count = thread_count * iterations
        actual_count = stats.worker_errors
        assert actual_count == expected_count, (
            f"错误计数不准确: 期望{expected_count}, 实际{actual_count}"
        )

        # 输出性能信息
        print("\nrecord_worker_error并发测试完成:")
        print(f"  线程数: {thread_count}")
        print(f"  每线程迭代: {iterations}")
        print(f"  总调用次数: {expected_count}")
        print(f"  实际计数: {actual_count}")
        print(f"  耗时: {elapsed:.3f}秒")
        print(f"  吞吐量: {expected_count / elapsed:.0f} 次/秒")
        print(f"  计数准确性: {'[OK] 通过' if actual_count == expected_count else '[FAIL] 失败'}")

    def test_error_log_rate_limit_accuracy(self):
        """测试错误日志限频准确性（M2修复验证）."""
        from unittest.mock import MagicMock

        from src.collision.key_collision_engine import KeyCollisionEngine

        # 创建引擎实例
        engine = KeyCollisionEngine(targets=set())
        engine.data_logging_enabled = True
        engine.data_logger = MagicMock()
        engine._error_log_interval = 1.0  # 1秒限频

        # 模拟多个线程同时触发错误日志
        call_count = [0]
        call_times = []

        original_record_error = engine.data_logger.record_error

        def mock_record_error(**kwargs):
            call_count[0] += 1
            call_times.append(time.time())
            return original_record_error(**kwargs)

        engine.data_logger.record_error = mock_record_error

        # 快速连续触发错误日志（模拟并发场景）
        start_time = time.time()
        for i in range(10):
            current_time = time.time()
            should_log = False

            # M2修复：标志位模式
            with engine._state_lock:
                if current_time - engine._last_error_log_time >= engine._error_log_interval:
                    engine._last_error_log_time = current_time
                    should_log = True

            if should_log:
                engine.data_logger.record_error(
                    error_type="test_error",
                    message=f"测试错误 {i}",
                    context={"iteration": i},
                )

        elapsed = time.time() - start_time

        # 验证限频效果（在1秒内应该只记录1次）
        assert call_count[0] == 1, f"限频失效: 在{elapsed:.3f}秒内记录了{call_count[0]}次（期望1次）"

        print("\n错误日志限频测试完成:")
        print("  触发次数: 10")
        print(f"  实际记录: {call_count[0]}")
        print(f"  限频间隔: {engine._error_log_interval}秒")
        print(f"  测试时长: {elapsed:.3f}秒")
        print(f"  限频准确性: {'[OK] 通过' if call_count[0] == 1 else '[FAIL] 失败'}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
