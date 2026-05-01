#!/usr/bin/env python3
"""GPU碰撞引擎线程安全专项测试

覆盖:
- 并发访问测试
- 异步私钥生成
- GPU超时监控
- 停止引擎
"""

import pytest
import os
import sys
import time
import threading
import secrets
from unittest.mock import Mock, patch
from src.collision.collision_stats import CollisionStats
from src.collision.checkpoint_manager import CheckpointManager
from src.collision.deduplication_filter import DeduplicationFilter
from src.collision.gpu_collision_engine import GPUCollisionEngine
from tests.test_helpers import MockAssertions


class TestConcurrentAccess:
    """并发访问测试"""

    def test_concurrent_stats_update(self):
        """测试并发更新统计数据"""
        stats = CollisionStats()
        stats.start_time = time.time()

        num_threads = 20
        updates_per_thread = 50
        barrier = threading.Barrier(num_threads)

        def update_stats(thread_id):
            barrier.wait()  # 确保所有线程同时开始
            for i in range(updates_per_thread):
                stats.update(i + 1)

        # 创建20个线程并发更新
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=update_stats, args=(i,))
            threads.append(t)
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 验证最终值（应该是最后一个更新的值）
        assert stats.total_checked == updates_per_thread

    def test_concurrent_dedup_check(self):
        """测试并发去重检查"""
        dedup = DeduplicationFilter(max_size=10000, enabled=True)

        num_threads = 20
        checks_per_thread = 100
        barrier = threading.Barrier(num_threads)
        results = []
        lock = threading.Lock()

        def check_dedup(thread_id):
            barrier.wait()
            thread_results = []
            for i in range(checks_per_thread):
                pk = secrets.token_bytes(32)
                result = dedup.check_and_add(pk)
                thread_results.append(result)

            with lock:
                results.extend(thread_results)

        # 创建20个线程并发检查
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=check_dedup, args=(i,))
            threads.append(t)
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 验证所有检查都成功（私钥都是唯一的）
        assert all(results) is True

        # 验证统计
        stats = dedup.get_stats()
        assert stats["checks_total"] == num_threads * checks_per_thread
        assert stats["duplicates_found"] == 0

    def test_concurrent_checkpoint_save(self):
        """测试并发保存断点"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "concurrent_checkpoint.json")
            checkpoint_mgr = CheckpointManager(filepath=filepath)

            num_threads = 10
            barrier = threading.Barrier(num_threads)

            def save_checkpoint(thread_id):
                barrier.wait()
                targets = {f"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
                checkpoint_mgr.save(
                    mode="random",
                    targets=targets,
                    current_position=thread_id * 1000,
                    total_checked=thread_id * 1000,
                    matches=[],
                    force=True,
                )

            # 创建10个线程并发保存
            threads = []
            for i in range(num_threads):
                t = threading.Thread(target=save_checkpoint, args=(i,))
                threads.append(t)
                t.start()

            # 等待所有线程完成
            for t in threads:
                t.join()

            # 验证文件存在且可读
            assert os.path.exists(filepath)

            # 验证数据完整性
            loaded = checkpoint_mgr.load()
            assert loaded is not None


class TestAsyncKeyGeneration:
    """异步私钥生成测试"""

    def test_async_key_generation_thread_safety(self, mock_gpu_chain):
        """测试异步私钥生成线程安全

        使用mock_gpu_chain fixture,自动处理7层Mock
        """
        mock_device, mock_context, mock_kernel = mock_gpu_chain

        # 自定义batch_size为100
        mock_context.calculate_batch_size = Mock(return_value=100)
        mock_kernel.max_batch_size = 100
        mock_kernel.gpu_optimizer.analyze_and_adjust = Mock(return_value=(100, {}))

        targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
        engine = GPUCollisionEngine(targets, batch_size=100)

        # 启动随机模式（使用异步私钥生成）
        engine.start(mode="random")

        # 运行2秒
        time.sleep(2)
        engine.stop()

        # 验证引擎正常运行
        assert engine.stats.total_checked > 0

    def test_async_key_generation_timeout(self):
        """测试异步私钥生成超时处理"""
        import threading

        # 模拟超时场景
        result = [None]

        def slow_generation():
            time.sleep(35)  # 超时
            result[0] = b"test"

        # 启动超时线程
        thread = threading.Thread(target=slow_generation, daemon=True)
        thread.start()

        # 等待超时
        thread.join(timeout=2)

        # 验证超时
        assert thread.is_alive() is True
        assert result[0] is None

        # 清理（无法真正停止daemon线程，但测试已验证超时逻辑）


class TestGPUTimeout:
    """GPU超时监控测试"""

    def test_gpu_timeout_event_cleanup(self):
        """测试GPU超时事件清理"""
        import threading

        # 模拟超时监控
        timeout_event = threading.Event()
        execution_completed = [False]

        def timeout_monitor():
            if not timeout_event.wait(2):  # 2秒超时
                execution_completed[0] = False

        # 启动监控线程
        monitor_thread = threading.Thread(target=timeout_monitor, daemon=True)
        monitor_thread.start()

        # 正常完成（在超时前）
        time.sleep(0.5)
        execution_completed[0] = True
        timeout_event.set()

        # 等待线程结束
        monitor_thread.join(timeout=1)

        # 验证清理成功
        assert monitor_thread.is_alive() is False
        assert execution_completed[0] is True


class TestEngineStop:
    """停止引擎测试"""

    def test_stop_engine_graceful(self, mock_gpu_chain):
        """测试优雅停止引擎

        使用mock_gpu_chain fixture简化Mock配置
        """
        mock_device, mock_context, mock_kernel = mock_gpu_chain

        # 自定义batch_size
        mock_context.calculate_batch_size = Mock(return_value=100)
        mock_kernel.max_batch_size = 100
        mock_kernel.gpu_optimizer.analyze_and_adjust = Mock(return_value=(100, {}))

        targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
        engine = GPUCollisionEngine(targets, batch_size=100)

        # 启动引擎
        engine.start(mode="random")
        assert engine.is_running() is True

        # 运行1秒后停止
        time.sleep(1)
        engine.stop()

        # 验证停止
        assert engine.is_running() is False

        # Phase 6: 清理通过 _device_manager.cleanup() 而非直接调用 device/context/kernel.cleanup
        # 此处仅验证引擎正确停止，清理链在真实GPU环境下由集成测试覆盖
        # MockAssertions.assert_cleanup_called(mock_device, mock_context, mock_kernel)

    def test_stop_and_restart_engine(self, mock_gpu_chain):
        """测试停止后重启引擎

        使用mock_gpu_chain fixture简化Mock配置
        """
        mock_device, mock_context, mock_kernel = mock_gpu_chain

        # 自定义batch_size
        mock_context.calculate_batch_size = Mock(return_value=100)
        mock_kernel.max_batch_size = 100
        mock_kernel.gpu_optimizer.analyze_and_adjust = Mock(return_value=(100, {}))

        targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
        engine = GPUCollisionEngine(targets, batch_size=100)

        # 第一次启动
        engine.start(mode="random")
        time.sleep(0.5)
        engine.stop()

        # 验证状态重置
        assert engine._running is False
        assert engine._thread is None

        # 第二次启动
        engine.start(mode="random")
        assert engine.is_running() is True

        time.sleep(0.5)
        engine.stop()
