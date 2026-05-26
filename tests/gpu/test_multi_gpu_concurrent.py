"""多GPU并发场景测试

验证多线程环境下的线程安全性和锁机制正确性。
"""

import threading
import time
import unittest
from unittest.mock import Mock

import pytest

pytestmark = pytest.mark.gpu


class TestConcurrentAccess:
    """测试并发访问场景"""

    def test_concurrent_state_access(self):
        """测试并发状态访问"""
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

        engine = MultiGPUCollisionEngine()
        errors = []

        def toggle_running():
            """并发切换运行状态"""
            try:
                for _ in range(100):
                    with engine._state_lock:
                        engine._running = not engine._running
                        time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))

        # 创建10个线程并发修改状态
        threads = [threading.Thread(target=toggle_running) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证无错误
        assert len(errors) == 0, f"并发访问出错: {errors}"

    def test_concurrent_workers_dict_access(self):
        """测试并发workers字典访问"""
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

        engine = MultiGPUCollisionEngine()
        errors = []

        def add_workers():
            """并发添加工作器"""
            try:
                for i in range(50):
                    with engine._workers_lock:
                        engine.workers[f"worker_{i}"] = Mock()
                        time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))

        def read_workers():
            """并发读取工作器"""
            try:
                for _ in range(50):
                    with engine._workers_lock:
                        _ = dict(engine.workers)
                        time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))

        # 创建并发线程
        threads = []
        threads.extend([threading.Thread(target=add_workers) for _ in range(5)])
        threads.extend([threading.Thread(target=read_workers) for _ in range(5)])

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证无错误
        assert len(errors) == 0, f"并发访问出错: {errors}"

    def test_concurrent_start_stop(self):
        """测试并发启动停止"""
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

        engine = MultiGPUCollisionEngine()
        engine._initialized = True
        results = {"starts": 0, "stops": 0}
        lock = threading.Lock()

        def try_start():
            """尝试启动"""
            result = engine.start(targets=set(), mode="random", total_keys=1000)
            if result:
                with lock:
                    results["starts"] += 1

        def try_stop():
            """尝试停止"""
            engine.stop()
            with lock:
                results["stops"] += 1

        # 并发调用start和stop
        threads = []
        threads.extend([threading.Thread(target=try_start) for _ in range(10)])
        threads.extend([threading.Thread(target=try_stop) for _ in range(10)])

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证最多只有1次成功启动
        assert results["starts"] <= 1, "并发启动应该只有1次成功"


class TestThreadSafety:
    """测试线程安全机制"""

    def test_worker_stats_thread_safety(self):
        """测试工作器统计信息线程安全"""
        from src.gpu.worker import SingleGPUWorker

        worker = SingleGPUWorker(device_idx=0, key_range=(0, 1000), targets=set(), config={})
        errors = []

        def update_stats():
            """并发更新统计"""
            try:
                for _ in range(100):
                    with worker._lock:
                        worker._stats["keys_checked"] += 1
                        time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))

        def read_stats():
            """并发读取统计"""
            try:
                for _ in range(100):
                    stats = worker.get_stats()
                    assert "keys_checked" in stats
                    time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))

        # 并发读写
        threads = []
        threads.extend([threading.Thread(target=update_stats) for _ in range(5)])
        threads.extend([threading.Thread(target=read_stats) for _ in range(5)])

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证无错误
        assert len(errors) == 0, f"线程安全测试失败: {errors}"

        # 验证统计数据正确
        final_stats = worker.get_stats()
        assert final_stats["keys_checked"] == 500  # 5线程 × 100次

    def test_worker_event_control(self):
        """测试工作器事件控制"""
        from src.gpu.worker import SingleGPUWorker

        worker = SingleGPUWorker(device_idx=0, key_range=(0, 1000), targets=set(), config={})

        # 测试停止事件
        assert not worker._stop_event.is_set()
        worker.stop_search()
        assert worker._stop_event.is_set()

        # 测试暂停事件
        assert worker._pause_event.is_set()  # 初始为运行
        worker.pause_search()
        assert not worker._pause_event.is_set()
        worker.resume_search()
        assert worker._pause_event.is_set()


class TestResourceCleanup:
    """测试资源清理机制"""

    def test_cleanup_idempotent(self):
        """测试清理操作的幂等性"""
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

        engine = MultiGPUCollisionEngine()
        engine._initialized = True
        # 不设置_running=True,避免调用stop()等待workers

        # 多次调用cleanup应该不报错
        for _ in range(5):
            try:
                engine.cleanup()
            except Exception as e:
                pytest.fail(f"cleanup()不是幂等的: {e}")

        # 验证最终状态
        assert not engine._running
        assert not engine._initialized
        assert len(engine.workers) == 0

    def test_context_manager_cleanup(self):
        """测试上下文管理器自动清理"""
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

        with MultiGPUCollisionEngine() as engine:
            engine._initialized = True
            # 不设置_running=True,避免stop()

        # 退出with块后应该已清理
        assert not engine._running
        assert not engine._initialized

    def test_del_cleanup(self):
        """测试析构函数清理"""
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

        engine = MultiGPUCollisionEngine()
        engine._initialized = True
        # 不设置_running=True,避免stop()

        # 模拟析构
        engine.__del__()

        # 验证已清理
        assert not engine._running


class TestDeadlockPrevention:
    """测试死锁预防"""

    def test_no_deadlock_on_rapid_start_stop(self):
        """测试快速启动停止不会死锁"""
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

        engine = MultiGPUCollisionEngine()
        engine._initialized = True

        # 快速启动停止10次
        for _ in range(10):
            engine.start(targets=set(), mode="random", total_keys=100)
            engine.stop()

        # 如果能执行到这里,说明没有死锁
        assert True

    @pytest.mark.skip(
        reason=(
            "P2修复(76b1327): _state_lock 已改用 threading.RLock() 可重入锁，"
            "消除了回调路径重入死锁风险。测试仍需 GPU mock/真实硬件环境验证，"
            "当前 skip 因 engine.start() 依赖 load_balancer (需真实GPU设备)。"
        ),
    )
    @pytest.mark.timeout(30)  # 安全网: 即使 skip 被移除，30s 超时自动终止
    def test_no_deadlock_concurrent_operations(self):
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

        engine = MultiGPUCollisionEngine()
        engine._initialized = True
        deadlock_detected = [False]

        def operation():
            """执行操作"""
            try:
                for _ in range(20):
                    engine.start(targets=set(), mode="random", total_keys=100)
                    engine.pause()
                    engine.resume()
                    engine.stop()
                    time.sleep(0.01)
            except (RuntimeError, ValueError):
                pass  # 并发操作导致的预期内状态冲突

        # 并发执行
        threads = [threading.Thread(target=operation) for _ in range(5)]
        for t in threads:
            t.start()

        # 设置超时检测死锁
        for t in threads:
            t.join(timeout=10)
            if t.is_alive():
                deadlock_detected[0] = True

        assert not deadlock_detected[0], "检测到死锁!"

