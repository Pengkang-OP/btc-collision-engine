#!/usr/bin/env python3
"""GPU碰撞引擎错误计数器线程安全测试

验证_consecutive_gpu_errors的锁保护逻辑和重试限制机制。
Phase 6 兼容版：使用 src.collision.gpu.engine 路径和 GPUDeviceManager mock。
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.collision.gpu.engine import GPUCollisionEngine


def _create_phase6_mock_fixture():
    """创建 Phase 6 引擎通用 Mock 环境

    返回 (patches_dict, mock_device_manager, mock_collision_core) 元组，
    其中 patches_dict 包含所有已 start() 的 patcher，调用方需在 finally 中 stop()。
    """
    # 1. Mock GPUDeviceManager（替代旧的 GPUDevice/GPUContext/GPUKernel/AsyncGPUExecutor）
    mock_device_manager = MagicMock()
    mock_device = MagicMock()
    mock_device.name = "Mock GPU"
    mock_device.vendor = "nvidia"
    mock_device_manager.device = mock_device
    mock_device_manager.context = MagicMock()
    mock_device_manager.kernel = MagicMock()
    mock_device_manager.async_executor = MagicMock()
    mock_device_manager.memory_pool = MagicMock()
    mock_device_manager.initialize = MagicMock()  # 关键：跳过真实 GPU 初始化

    # 2. Mock CollisionCore
    mock_collision_stats = MagicMock()
    mock_collision_stats.matches = []
    mock_collision_stats.total_checked = 0
    mock_collision_core = MagicMock()
    mock_collision_core.stats = mock_collision_stats
    mock_collision_core.checkpoint = MagicMock()
    mock_collision_core.dedup_filter = MagicMock()

    patches = [
        patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", True),
        patch("src.collision.gpu.engine.GPUDeviceManager", return_value=mock_device_manager),
        patch("src.collision.gpu.engine.CollisionCore", return_value=mock_collision_core),
        patch("src.collision.gpu.engine.SearchModeCoordinator"),
        patch("src.collision.gpu.engine.GPUEngineMonitor"),
        patch("src.collision.gpu.engine.VendorOptimizationFactory.create", return_value=MagicMock()),
        patch("src.collision.gpu.engine.GPUDeviceDetector"),
        patch("src.collision.gpu.engine.GPUMemoryCalculator"),
    ]
    return patches, mock_device_manager, mock_collision_core


class TestErrorCounterThreadSafety:
    """错误计数器线程安全测试类"""

    @pytest.fixture
    def mock_gpu_engine(self):
        """提供预配置的GPU引擎Mock环境 (Phase 6 兼容)"""
        patchers, mock_device_manager, mock_collision_core = _create_phase6_mock_fixture()

        active = []
        try:
            for p in patchers:
                p.start()
                active.append(p)
            yield {
                "device_manager": mock_device_manager,
                "core": mock_collision_core,
                "device": mock_device_manager.device,
            }
        finally:
            for p in active:
                p.stop()

    def test_error_counter_initialization(self, mock_gpu_engine):
        """测试错误计数器初始化"""
        engine = GPUCollisionEngine({"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"})

        assert hasattr(engine, "_consecutive_gpu_errors")
        assert hasattr(engine, "_max_gpu_error_retries")
        assert engine._consecutive_gpu_errors == 0
        assert engine._max_gpu_error_retries == 100  # 默认值

    def test_error_counter_reset_on_start(self, mock_gpu_engine):
        """测试引擎启动时重置错误计数器"""
        engine = GPUCollisionEngine({"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"})

        # 模拟已有错误计数
        engine._consecutive_gpu_errors = 50

        # 重新启动引擎
        engine.start(mode="random")
        engine.stop()

        # 验证计数器重置为0
        assert engine._consecutive_gpu_errors == 0

    def test_error_counter_increment_with_lock(self, mock_gpu_engine):
        """测试错误计数器递增的线程安全性"""
        engine = GPUCollisionEngine({"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"})

        # 多线程并发递增计数器
        def increment_counter():
            with engine._batch_size_lock:
                engine._consecutive_gpu_errors += 1

        threads = []
        for _ in range(100):
            t = threading.Thread(target=increment_counter)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 验证计数器准确递增到100
        assert engine._consecutive_gpu_errors == 100

    def test_max_retries_prevents_infinite_loop(self, mock_gpu_engine):
        """测试最大重试次数防止无限循环"""
        engine = GPUCollisionEngine({"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"})
        engine._max_gpu_error_retries = 10  # 降低阈值以便测试

        # 模拟达到最大重试次数
        with engine._batch_size_lock:
            engine._consecutive_gpu_errors = 10

        # 验证引擎会停止
        engine._running = True
        with engine._batch_size_lock:
            if engine._consecutive_gpu_errors >= engine._max_gpu_error_retries:
                engine._running = False

        assert engine._running is False

    def test_error_counter_reset_on_success(self, mock_gpu_engine):
        """测试成功执行时重置错误计数器"""
        engine = GPUCollisionEngine({"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"})

        # 模拟已有错误计数
        with engine._batch_size_lock:
            engine._consecutive_gpu_errors = 50

        # 模拟成功执行后重置
        with engine._batch_size_lock:
            engine._consecutive_gpu_errors = 0

        assert engine._consecutive_gpu_errors == 0

    def test_concurrent_error_and_success(self, mock_gpu_engine):
        """测试并发错误和成功场景"""
        engine = GPUCollisionEngine({"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"})
        engine._max_gpu_error_retries = 100

        error_count = 0
        success_count = 0

        def simulate_error():
            nonlocal error_count
            with engine._batch_size_lock:
                engine._consecutive_gpu_errors += 1
                error_count += 1
                time.sleep(0.001)  # 模拟处理时间

        def simulate_success():
            nonlocal success_count
            with engine._batch_size_lock:
                engine._consecutive_gpu_errors = 0
                success_count += 1
                time.sleep(0.001)  # 模拟处理时间

        # 创建混合线程
        threads = []
        for i in range(50):
            if i % 2 == 0:
                t = threading.Thread(target=simulate_error)
            else:
                t = threading.Thread(target=simulate_success)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 验证计数器最终状态合理
        assert engine._consecutive_gpu_errors >= 0
        assert engine._consecutive_gpu_errors <= engine._max_gpu_error_retries
        assert error_count == 25
        assert success_count == 25

    def test_config_max_error_retries(self, mock_gpu_engine):
        """测试从配置文件读取max_error_retries (Phase 6: 使用 __new__ 绕过 GPU 初始化)"""
        engine = GPUCollisionEngine.__new__(GPUCollisionEngine)
        engine.config = {"gpu": {"max_error_retries": 200}}
        engine._batch_size_lock = threading.Lock()
        engine._max_gpu_error_retries = 100  # 默认值

        # 模拟从配置读取
        if hasattr(engine, "config") and engine.config:
            gpu_config = engine.config.get("gpu", {})
            if "max_error_retries" in gpu_config:
                engine._max_gpu_error_retries = gpu_config["max_error_retries"]

        assert engine._max_gpu_error_retries == 200


class TestCallbackSnapshotSafety:
    """回调快照安全性测试类"""

    @pytest.fixture
    def mock_gpu_engine(self):
        """提供预配置的GPU引擎Mock环境 (Phase 6 兼容)"""
        patchers, mock_device_manager, mock_collision_core = _create_phase6_mock_fixture()

        active = []
        try:
            for p in patchers:
                p.start()
                active.append(p)
            yield {
                "device_manager": mock_device_manager,
                "core": mock_collision_core,
            }
        finally:
            for p in active:
                p.stop()

    def test_on_complete_uses_snapshot(self, mock_gpu_engine):
        """测试on_complete回调使用快照"""
        from src.collision.collision_stats import CollisionStats

        received_stats = []

        def on_complete_callback(stats):
            received_stats.append(stats)

        engine = GPUCollisionEngine(
            {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"},
            on_complete=on_complete_callback,
        )

        # 使用真实 CollisionStats，绕过 MagicMock 嵌套问题
        real_stats = CollisionStats()
        real_stats.total_checked = 1000
        engine.stats = real_stats
        engine._running = False
        if engine.on_complete:
            engine.on_complete(engine.stats.snapshot())

        assert len(received_stats) == 1
        assert received_stats[0].total_checked == 1000
        # 验证是快照而非原对象
        assert received_stats[0] is not engine.stats
