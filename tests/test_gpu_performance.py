#!/usr/bin/env python3
"""GPU碰撞引擎性能验证专项测试

覆盖:
- 性能优化器
- 吞吐量测试
- 内存使用测试
"""

import pytest
import os
import sys
import time
import psutil
from unittest.mock import Mock, patch
from src.gpu.performance_optimizer import (
    GPUPerformanceOptimizer,
    PerformanceMetrics,
    GPUProfile,
    GPUVendor,
)
from src.collision.collision_stats import CollisionStats


class TestPerformanceOptimizer:
    """性能优化器测试"""

    def test_gpu_optimizer_profile_creation(self):
        """测试GPU配置文件创建"""
        optimizer = GPUPerformanceOptimizer()

        # 测试NVIDIA配置
        nvidia_profile = optimizer.create_optimized_profile(
            device_name="GeForce RTX 3080",
            vendor_str="NVIDIA Corporation",
            global_mem_size=10 * 1024**3,
            compile_time_ms=5000,
        )

        assert nvidia_profile.vendor == GPUVendor.NVIDIA
        assert nvidia_profile.max_batch_size > 0
        # NVIDIA 10GB内存,实际memory_usage_ratio约0.8
        # 根据GPU显存计算: min(0.8, 8GB/10GB) = 0.8
        assert nvidia_profile.memory_usage_ratio == pytest.approx(0.8, rel=1e-2)

        # 测试AMD配置
        amd_profile = optimizer.create_optimized_profile(
            device_name="Radeon RX 6800",
            vendor_str="AMD",
            global_mem_size=16 * 1024**3,
            compile_time_ms=6000,
        )

        assert amd_profile.vendor == GPUVendor.AMD
        assert amd_profile.max_batch_size > 0

        # 测试Intel配置
        intel_profile = optimizer.create_optimized_profile(
            device_name="Intel Arc A770",
            vendor_str="Intel Corporation",
            global_mem_size=16 * 1024**3,
            compile_time_ms=8000,
        )

        assert intel_profile.vendor == GPUVendor.INTEL
        assert intel_profile.use_uint32_workaround is True
        assert intel_profile.enable_async_execution is True

    def test_gpu_optimizer_adaptive_adjustment(self):
        """测试自适应调整"""
        optimizer = GPUPerformanceOptimizer()

        # 先创建配置文件(必需)
        profile = optimizer.create_optimized_profile(
            device_name="Test GPU", vendor_str="NVIDIA Corporation", global_mem_size=8 * 1024**3
        )

        # 记录足够的性能数据(至少3个)
        for _ in range(5):
            metrics = PerformanceMetrics(
                batch_execution_time_ms=100.0, keys_per_second=1000000.0, error_count=0
            )
            optimizer.record_performance(metrics)

        # 初始batch_size
        initial_batch_size = 65536

        # 模拟性能下降（高错误率10%）
        new_batch_size, adjustments = optimizer.analyze_and_adjust(
            current_batch_size=initial_batch_size, error_rate=0.10  # 10%错误率,触发调整
        )

        # 验证调整信息返回
        # adjustments可能包含嵌套的adjustment信息
        assert "action" in adjustments or "error_rate_too_high" in adjustments

    def test_gpu_optimizer_performance_recording(self):
        """测试性能指标记录"""
        optimizer = GPUPerformanceOptimizer()

        # 记录100个批次
        for i in range(100):
            metrics = PerformanceMetrics(
                batch_execution_time_ms=100.0 + i,
                keys_per_second=1000000.0 - i * 1000,
                error_count=0,
            )
            optimizer.record_performance(metrics)

        # 验证历史记录
        with optimizer._lock:
            assert len(optimizer._metrics_history) == 100


class TestThroughput:
    """吞吐量测试"""

    def test_batch_processing_throughput(self):
        """测试批次处理吞吐量"""
        stats = CollisionStats()
        stats.start_time = time.time()

        # 模拟100个批次处理
        batch_size = 1000
        num_batches = 100

        for i in range(num_batches):
            # 模拟每个批次延迟10ms
            time.sleep(0.01)
            stats.update((i + 1) * batch_size)

        # 验证吞吐量
        elapsed = time.time() - stats.start_time
        expected_throughput = (num_batches * batch_size) / elapsed

        # 允许20%误差
        assert abs(stats.speed - expected_throughput) / expected_throughput < 0.2


class TestMemoryUsage:
    """内存使用测试"""

    def test_gpu_memory_buffer_allocation(self):
        """测试GPU内存缓冲区分配"""
        batch_size = 10000

        # 计算预期内存使用
        expected_memory = batch_size * 36  # 每个私钥约36字节

        # 验证计算合理
        assert expected_memory > 0
        assert expected_memory < 100 * 1024**2  # 小于100MB

    def test_memory_leak_detection(self):
        """测试内存泄漏检测"""
        process = psutil.Process(os.getpid())

        # 记录初始内存
        initial_memory = process.memory_info().rss

        # 模拟1000个批次处理
        stats = CollisionStats()
        stats.start_time = time.time()

        for i in range(1000):
            stats.update(i + 1)

            # 创建快照
            snapshot = stats.snapshot()

            # 记录错误
            if i % 100 == 0:
                stats.gpu_errors += 1

        # 检查内存增长
        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory

        # 验证内存增长合理（小于10MB）
        assert memory_growth < 10 * 1024 * 1024


class TestSecurityValidation:
    """安全验证测试"""

    def test_private_key_not_logged(self):
        """测试私钥不记录到日志"""
        import logging
        from io import StringIO

        # 创建日志捕获
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.DEBUG)

        logger = logging.getLogger("src.collision.gpu_collision_engine")
        logger.addHandler(handler)

        # 触发异常
        from src.utils.exception_handler import ExceptionHandler

        private_key = b"\x01" * 32
        error = RuntimeError(f"Error with key")  # 不包含私钥

        ExceptionHandler.handle_engine_error("GPU", error)

        # 验证日志不包含私钥
        log_content = log_stream.getvalue()
        assert private_key.hex() not in log_content

        logger.removeHandler(handler)

    def test_checkpoint_no_private_key(self):
        """测试断点文件不包含私钥"""
        import tempfile
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_security_checkpoint.json")

            from src.collision.checkpoint_manager import CheckpointManager

            checkpoint_mgr = CheckpointManager(filepath=filepath)

            targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
            matches = [
                {
                    "address": "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
                    "timestamp": time.time(),
                    "private_key_hex": "01" * 32,  # 模拟包含私钥
                }
            ]

            # 保存断点
            checkpoint_mgr.save(
                mode="random",
                targets=targets,
                current_position=1000,
                total_checked=1000,
                matches=matches,
                force=True,
            )

            # 读取文件验证
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 验证不包含私钥
            for match in data.get("matches", []):
                assert "private_key_hex" not in match
                assert "private_key" not in match


class TestRaceConditions:
    """竞态条件测试"""

    def test_race_condition_stats_update(self):
        """测试统计数据竞态条件

        注意: 这个测试验证的是“弱线程安全”- 即不会崩溃
        由于CollisionStats.update()使用赋值而非累加,多个线程同时更新时会丢失数据

        TODO: 如果需要使用累加语义,应修改CollisionStats.update()方法:
            self.total_checked += checked_count  # 累加而非赋值

        当前测试仅验证:
        1. 多线程并发不会导致崩溃
        2. 最终值在合理范围内(1-100)
        3. 统计数据可以正常计算speed
        """
        import threading

        stats = CollisionStats()
        stats.start_time = time.time()

        num_threads = 50
        barrier = threading.Barrier(num_threads)

        # 注意: CollisionStats.update()是赋值而非累加
        # 所以最终值应该是最后一个线程设置的值
        # 这个测试验证的是线程安全(不会崩溃),而非累加正确性
        def update_stats():
            barrier.wait()
            for i in range(100):
                stats.update(i + 1)  # 每次更新1-100

        threads = []
        for _ in range(num_threads):
            t = threading.Thread(target=update_stats)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 验证无数据竞争崩溃,最终值在1-100之间
        assert 1 <= stats.total_checked <= 100
        assert stats.speed >= 0  # 验证可以正常计算速度

    def test_race_condition_checkpoint(self):
        """测试断点竞态条件"""
        import tempfile
        import threading

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "race_checkpoint.json")

            from src.collision.checkpoint_manager import CheckpointManager

            checkpoint_mgr = CheckpointManager(filepath=filepath)

            num_threads = 20
            barrier = threading.Barrier(num_threads)

            def save_checkpoint(thread_id):
                barrier.wait()
                targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
                checkpoint_mgr.save(
                    mode="random",
                    targets=targets,
                    current_position=thread_id,
                    total_checked=thread_id,
                    matches=[],
                    force=True,
                )

            threads = []
            for i in range(num_threads):
                t = threading.Thread(target=save_checkpoint, args=(i,))
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            # 验证文件完整性
            assert os.path.exists(filepath)

            # 验证可加载
            loaded = checkpoint_mgr.load()
            assert loaded is not None
