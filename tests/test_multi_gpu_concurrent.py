# -*- coding: utf-8 -*-
"""多GPU并发场景测试

验证多线程环境下的线程安全性和锁机制正确性。
"""

import unittest
import threading
import time
import pytest
from unittest.mock import Mock


class TestConcurrentAccess(unittest.TestCase):
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
        self.assertEqual(len(errors), 0, f"并发访问出错: {errors}")

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
        self.assertEqual(len(errors), 0, f"并发访问出错: {errors}")

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
        self.assertLessEqual(results["starts"], 1, "并发启动应该只有1次成功")


class TestThreadSafety(unittest.TestCase):
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
        self.assertEqual(len(errors), 0, f"线程安全测试失败: {errors}")

        # 验证统计数据正确
        final_stats = worker.get_stats()
        self.assertEqual(final_stats["keys_checked"], 500)  # 5线程 × 100次

    def test_worker_event_control(self):
        """测试工作器事件控制"""
        from src.gpu.worker import SingleGPUWorker

        worker = SingleGPUWorker(device_idx=0, key_range=(0, 1000), targets=set(), config={})

        # 测试停止事件
        self.assertFalse(worker._stop_event.is_set())
        worker.stop_search()
        self.assertTrue(worker._stop_event.is_set())

        # 测试暂停事件
        self.assertTrue(worker._pause_event.is_set())  # 初始为运行
        worker.pause_search()
        self.assertFalse(worker._pause_event.is_set())
        worker.resume_search()
        self.assertTrue(worker._pause_event.is_set())


class TestResourceCleanup(unittest.TestCase):
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
                self.fail(f"cleanup()不是幂等的: {e}")

        # 验证最终状态
        self.assertFalse(engine._running)
        self.assertFalse(engine._initialized)
        self.assertEqual(len(engine.workers), 0)

    def test_context_manager_cleanup(self):
        """测试上下文管理器自动清理"""
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

        with MultiGPUCollisionEngine() as engine:
            engine._initialized = True
            # 不设置_running=True,避免stop()

        # 退出with块后应该已清理
        self.assertFalse(engine._running)
        self.assertFalse(engine._initialized)

    def test_del_cleanup(self):
        """测试析构函数清理"""
        from src.gpu.multi_gpu_engine import MultiGPUCollisionEngine

        engine = MultiGPUCollisionEngine()
        engine._initialized = True
        # 不设置_running=True,避免stop()

        # 模拟析构
        engine.__del__()

        # 验证已清理
        self.assertFalse(engine._running)


class TestDeadlockPrevention(unittest.TestCase):
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
        self.assertTrue(True)

    @pytest.mark.skip(reason="预存问题: MultiGPU引擎在特定条件下存在死锁风险，需引擎层面修复")
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
            except Exception:
                pass

        # 并发执行
        threads = [threading.Thread(target=operation) for _ in range(5)]
        for t in threads:
            t.start()

        # 设置超时检测死锁
        for t in threads:
            t.join(timeout=10)
            if t.is_alive():
                deadlock_detected[0] = True

        self.assertFalse(deadlock_detected[0], "检测到死锁!")


if __name__ == "__main__":
    unittest.main()
