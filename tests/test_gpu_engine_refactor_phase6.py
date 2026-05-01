"""GPU引擎重构 Phase 6 测试套件 - 集成与兼容性

测试范围:
1. TestEngineIntegration: 构造函数参数完整性, 组件创建
2. TestBackwardCompatibility: shim 重导出, 公共 API 存在性
3. TestComponentDelegation: 委托到 Facade/Core/Monitoring
4. TestSearchModeAccess: 搜索模式属性代理
5. TestModuleImports: 版本号, 常量导出, shim 等价性
6. TestLifecycle: start/stop 完整生命周期

版本: v1.0
创建日期: 2026-04-30
"""

import pytest
import threading
from unittest.mock import Mock, patch, MagicMock, PropertyMock

from src.collision.gpu.protocols import GPUDevice

# ========== Fixtures ==========


@pytest.fixture
def mock_targets():
    """创建测试目标地址集合"""
    return {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "1CounterpartyXXXXXXXXXXXXXXXUWLpVr"}


@pytest.fixture
def mock_device():
    """创建 Mock GPU 设备"""
    device = GPUDevice(
        device_id=0,
        vendor="nvidia",
        name="NVIDIA GeForce RTX 4090",
        memory_total=24 * 1024 * 1024 * 1024,
    )
    return device


@pytest.fixture
def mock_engine_patches(mock_targets):
    """创建 GPU 引擎所需的最小 Mock 集合"""
    mock_device_manager = MagicMock()
    mock_device = MagicMock()
    mock_device.name = "Mock GPU"
    mock_device.vendor = "nvidia"
    mock_device_manager.device = mock_device
    mock_device_manager.context = MagicMock()
    mock_device_manager.kernel = MagicMock()
    mock_device_manager.async_executor = MagicMock()
    mock_device_manager.memory_pool = MagicMock()

    mock_collision_core = MagicMock()
    mock_collision_stats = MagicMock()
    mock_collision_stats.matches = []
    mock_collision_stats.total_checked = 0
    mock_collision_core.stats = mock_collision_stats
    mock_collision_core.checkpoint = MagicMock()
    mock_collision_core.dedup_filter = MagicMock()

    patches = [
        patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", True),
        patch("src.collision.gpu.engine.GPUDeviceManager", return_value=mock_device_manager),
        patch("src.collision.gpu.engine.CollisionCore", return_value=mock_collision_core),
        patch("src.collision.gpu.engine.SearchModeCoordinator"),
        patch("src.collision.gpu.engine.GPUEngineMonitor"),
        patch(
            "src.collision.gpu.engine.VendorOptimizationFactory.create", return_value=MagicMock()
        ),
        patch("src.collision.gpu.engine.GPUDeviceDetector"),
        patch("src.collision.gpu.engine.GPUMemoryCalculator"),
    ]
    return patches, mock_device_manager, mock_collision_core


# ========== TestEngineIntegration ==========


class TestEngineIntegration:
    """测试引擎构造函数参数完整性"""

    def test_constructor_all_17_params(self, mock_targets, mock_engine_patches, tmp_path):
        """测试构造函数接受全部 17 个参数"""
        patches, _, _ = mock_engine_patches

        active_patches = []
        for p in patches:
            p.start()
            active_patches.append(p)

        try:
            from src.collision.gpu.engine import GPUCollisionEngine

            engine = GPUCollisionEngine(
                targets=mock_targets,
                device_index=0,
                batch_size=1_000_000,
                on_progress=None,
                on_match=None,
                on_complete=None,
                checkpoint_enabled=True,
                dedup_enabled=True,
                dedup_max_size=500_000,
                checkpoint_interval=60,
                data_logging_enabled=False,
                data_logging_interval=10,
                use_enhanced_monitoring=False,
                use_gpu_memory_pool=False,
                gpu_pool_max_buffers=50,
                gpu_pool_max_memory_mb=256,
                use_async_logging=False,
                async_log_file=str(tmp_path / "test.log"),
                async_log_max_bytes=5 * 1024 * 1024,
                async_log_backup_count=3,
                check_uncompressed=False,
            )

            assert engine is not None
            assert engine.targets == mock_targets
            assert engine.device_index == 0
        finally:
            for p in active_patches:
                p.stop()

    def test_constructor_pyopencl_unavailable(self, mock_targets):
        """测试 pyopencl 不可用时抛出 RuntimeError"""
        with patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", False):
            from src.collision.gpu.engine import GPUCollisionEngine

            with pytest.raises(RuntimeError, match="pyopencl"):
                GPUCollisionEngine(targets=mock_targets)

    def test_constructor_creates_core(self, mock_targets, mock_engine_patches):
        """测试构造函数创建 CollisionCore"""
        patches, _, mock_core = mock_engine_patches

        # 需要收集所有 patcher

        active_patches = []
        for p in patches:
            p.start()
            active_patches.append(p)

        try:
            from src.collision.gpu.engine import GPUCollisionEngine, CollisionCore

            engine = GPUCollisionEngine(targets=mock_targets, data_logging_enabled=False)
            CollisionCore.assert_called_once()
        finally:
            for p in active_patches:
                p.stop()

    def test_constructor_exposes_core_attributes(self, mock_targets, mock_engine_patches):
        """测试构造函数暴露 CollisionCore 属性"""
        patches, device_mgr, mock_core = mock_engine_patches

        active_patches = []
        for p in patches:
            p.start()
            active_patches.append(p)

        try:
            from src.collision.gpu.engine import GPUCollisionEngine

            engine = GPUCollisionEngine(targets=mock_targets, data_logging_enabled=False)
            assert hasattr(engine, "stats")
            assert hasattr(engine, "checkpoint_mgr")
            assert hasattr(engine, "dedup_filter")
        finally:
            for p in active_patches:
                p.stop()

    def test_constructor_exposes_gpu_attributes(self, mock_targets, mock_engine_patches):
        """测试构造函数暴露 GPU 设备属性"""
        patches, device_mgr, mock_core = mock_engine_patches

        active_patches = []
        for p in patches:
            p.start()
            active_patches.append(p)

        try:
            from src.collision.gpu.engine import GPUCollisionEngine

            engine = GPUCollisionEngine(targets=mock_targets, data_logging_enabled=False)
            assert hasattr(engine, "_gpu_device")
            assert hasattr(engine, "_gpu_kernel")
            assert hasattr(engine, "_async_executor")
            assert hasattr(engine, "_gpu_context")
            assert hasattr(engine, "_gpu_memory_pool")
        finally:
            for p in active_patches:
                p.stop()


# ========== TestBackwardCompatibility ==========


class TestBackwardCompatibility:
    """测试向后兼容性: shim 重导出, API 存在性"""

    def test_shim_imports_gpucollisionengine(self):
        """测试从 shim 导入 GPUCollisionEngine"""
        from src.collision.gpu_collision_engine import GPUCollisionEngine

        assert GPUCollisionEngine is not None

    def test_new_engine_imports_gpucollisionengine(self):
        """测试从新位置导入 GPUCollisionEngine"""
        from src.collision.gpu.engine import GPUCollisionEngine

        assert GPUCollisionEngine is not None

    def test_shim_and_new_are_same_class(self):
        """测试 shim 和新引擎导出的是同一个类"""
        from src.collision.gpu_collision_engine import GPUCollisionEngine as ShimEngine
        from src.collision.gpu.engine import GPUCollisionEngine as NewEngine

        assert ShimEngine is NewEngine

    def test_shim_re_exports_constants(self):
        """测试 shim 重导出所有常量"""
        from src.collision.gpu_collision_engine import (
            GPU_MAX_BATCH_SIZE,
            UINT32_MAX,
            INITIAL_BATCH_SIZE,
            ASYNC_KEY_GEN_TIMEOUT,
            BATCH_LOG_FREQUENCY,
            INITIAL_BATCHES_LOG,
            THREAD_JOIN_TIMEOUT,
            MONITOR_THREAD_JOIN_TIMEOUT,
            EXCEPTION_RECOVERY_DELAY,
        )

        assert GPU_MAX_BATCH_SIZE == 0xFFFFFFFF
        assert UINT32_MAX == 0xFFFFFFFF
        assert INITIAL_BATCH_SIZE == 1_000_000
        assert ASYNC_KEY_GEN_TIMEOUT == 30.0
        assert BATCH_LOG_FREQUENCY == 100
        assert INITIAL_BATCHES_LOG == 3
        assert THREAD_JOIN_TIMEOUT == 5.0
        assert MONITOR_THREAD_JOIN_TIMEOUT == 1.0
        assert EXCEPTION_RECOVERY_DELAY == 0.1

    def test_shim_re_exports_functions(self):
        """测试 shim 重导出工具函数"""
        from src.collision.gpu_collision_engine import (
            _seed_bytes_to_u32_be_array,
            _get_gpu_monitor,
        )

        assert callable(_seed_bytes_to_u32_be_array)
        assert callable(_get_gpu_monitor)

    def test_shim_re_exports_module_attrs(self):
        """测试 shim 保留模块级属性（向后兼容 Monkey-patch）"""
        from src.collision import gpu_collision_engine

        assert hasattr(gpu_collision_engine, "GPUDevice")
        assert hasattr(gpu_collision_engine, "GPUContext")
        assert hasattr(gpu_collision_engine, "GPUKernel")
        assert hasattr(gpu_collision_engine, "GPUDeviceDetector")
        assert hasattr(gpu_collision_engine, "AsyncGPUExecutor")
        assert hasattr(gpu_collision_engine, "GPUProfileLoader")

    def test_shim_monkey_patch_works(self):
        """测试 Monkey-patch shim 模块属性仍然有效"""
        from src.collision import gpu_collision_engine

        original = gpu_collision_engine.PYOPENCL_AVAILABLE
        try:
            gpu_collision_engine.PYOPENCL_AVAILABLE = not original
            assert gpu_collision_engine.PYOPENCL_AVAILABLE == (not original)
        finally:
            gpu_collision_engine.PYOPENCL_AVAILABLE = original

    def test_public_api_methods_exist(self, mock_targets, mock_engine_patches):
        """测试所有公共 API 方法存在"""
        patches, _, _ = mock_engine_patches

        active_patches = []
        for p in patches:
            p.start()
            active_patches.append(p)

        try:
            from src.collision.gpu.engine import GPUCollisionEngine

            engine = GPUCollisionEngine(targets=mock_targets, data_logging_enabled=False)

            # 核心方法
            assert callable(engine.start)
            assert callable(engine.stop)
            assert callable(engine.is_running)
            assert callable(engine.get_stats)
            assert callable(engine.get_device_info)

            # 便捷方法 (P2)
            assert callable(engine.run_benchmark)
            assert callable(engine.start_auto_tuning)
            assert callable(engine.generate_performance_report)

            # 上下文管理器方法
            assert hasattr(engine, "__enter__")
            assert hasattr(engine, "__exit__")
        finally:
            for p in active_patches:
                p.stop()

    def test_batch_size_property(self, mock_targets, mock_engine_patches):
        """测试 batch_size 属性线程安全"""
        patches, _, _ = mock_engine_patches

        active_patches = []
        for p in patches:
            p.start()
            active_patches.append(p)

        try:
            from src.collision.gpu.engine import GPUCollisionEngine

            engine = GPUCollisionEngine(
                targets=mock_targets, batch_size=1_000_000, data_logging_enabled=False
            )
            assert engine.batch_size == 1_000_000

            # 设置新值
            engine.batch_size = 2_000_000
            assert engine.batch_size == 2_000_000

            # 超出 UINT32_MAX 应抛出异常
            with pytest.raises(ValueError, match="UINT32_MAX"):
                engine.batch_size = 0xFFFFFFFF
        finally:
            for p in active_patches:
                p.stop()

    def test_static_method_is_gpu_available(self):
        """测试静态方法 is_gpu_available"""
        from src.collision.gpu.engine import GPUCollisionEngine

        # 应该返回 bool（不抛异常）
        result = GPUCollisionEngine.is_gpu_available()
        assert isinstance(result, bool)


# ========== TestComponentDelegation ==========


class TestComponentDelegation:
    """测试组件委托: 验证委托到 Facade/Core/Monitoring"""

    def test_get_device_info_delegation(self, mock_targets, mock_engine_patches):
        """测试 get_device_info 委托"""
        patches, device_mgr, _ = mock_engine_patches

        active_patches = []
        for p in patches:
            p.start()
            active_patches.append(p)

        try:
            from src.collision.gpu.engine import GPUCollisionEngine

            engine = GPUCollisionEngine(targets=mock_targets, data_logging_enabled=False)
            info = engine.get_device_info()
            assert info["type"] == "GPU"
        finally:
            for p in active_patches:
                p.stop()

    def test_get_stats_delegation(self, mock_targets, mock_engine_patches):
        """测试 get_stats 委托到 CollisionCore"""
        patches, _, _ = mock_engine_patches

        active_patches = []
        for p in patches:
            p.start()
            active_patches.append(p)

        try:
            from src.collision.gpu.engine import GPUCollisionEngine

            engine = GPUCollisionEngine(targets=mock_targets, data_logging_enabled=False)
            stats = engine.get_stats()
            assert stats is not None
        finally:
            for p in active_patches:
                p.stop()

    def test_get_adjustment_history_delegation(self, mock_targets, mock_engine_patches):
        """测试 get_adjustment_history 委托到 GPUEngineMonitor"""
        patches, _, _ = mock_engine_patches

        active_patches = []
        for p in patches:
            p.start()
            active_patches.append(p)

        try:
            from src.collision.gpu.engine import GPUCollisionEngine, GPUEngineMonitor

            engine = GPUCollisionEngine(targets=mock_targets, data_logging_enabled=False)
            # Mock GPUEngineMonitor 返回真实列表
            engine._engine_monitor.get_adjustment_history = MagicMock(
                return_value=[{"old_size": 1000000, "new_size": 2000000, "reason": "test"}]
            )
            history = engine.get_adjustment_history(limit=5)
            assert isinstance(history, list)
            assert len(history) == 1
        finally:
            for p in active_patches:
                p.stop()

    def test_vendor_detection(self, mock_targets, mock_engine_patches):
        """测试厂商检测逻辑"""
        patches, device_mgr, _ = mock_engine_patches

        active_patches = []
        for p in patches:
            p.start()
            active_patches.append(p)

        try:
            from src.collision.gpu.engine import GPUCollisionEngine

            engine = GPUCollisionEngine(targets=mock_targets, data_logging_enabled=False)
            # 设备 mock 为 nvidia
            vendor = engine._detect_vendor_from_device()
            assert vendor == "nvidia"
        finally:
            for p in active_patches:
                p.stop()


# ========== TestSearchModeAccess ==========


class TestSearchModeAccess:
    """测试搜索模式属性代理"""

    def test_search_mode_attributes_delegation(self, mock_targets, mock_engine_patches):
        """测试搜索模式方法委托"""
        patches, _, _ = mock_engine_patches

        active_patches = []
        for p in patches:
            p.start()
            active_patches.append(p)

        try:
            from src.collision.gpu.engine import GPUCollisionEngine

            engine = GPUCollisionEngine(targets=mock_targets, data_logging_enabled=False)

            # 搜索模式方法应存在
            assert callable(engine._random_search)
            assert callable(engine._start_range_scan)
            assert callable(engine._start_brute_force)
            assert callable(engine._range_scan)
            assert callable(engine._brute_force)
            assert callable(engine._execute_batch_loop)
        finally:
            for p in active_patches:
                p.stop()


# ========== TestModuleImports ==========


class TestModuleImports:
    """测试模块导入完整性"""

    def test_package_version(self):
        """测试包版本号为 6.0.0"""
        from src.collision import gpu

        assert gpu.__version__ == "6.0.0"

    def test_package_all_exports(self):
        """测试 __all__ 包含新组件"""
        from src.collision.gpu import __all__

        required = [
            "GPUEngineFacade",
            "PerformanceMonitoringPipeline",
            "CollisionCore",
            "VendorOptimizationFactory",
            "DeviceManagerAdapter",
            "GPUKernelAdapter",
            "AsyncPipelineAdapter",
            "DataLoggerAdapter",
            "get_gpu_engine_facade",
        ]
        for name in required:
            assert name in __all__, f"{name} 不在 __all__ 中"

    def test_factory_function_returns_class(self):
        """测试工厂函数返回正确的类"""
        from src.collision.gpu import get_gpu_engine_facade, GPUEngineFacade

        assert get_gpu_engine_facade() is GPUEngineFacade

    def test_constants_consistency(self):
        """测试 engine.py 和 shim 中的常量一致性"""
        from src.collision.gpu_collision_engine import GPU_MAX_BATCH_SIZE as shim_const
        from src.collision.gpu.engine import GPU_MAX_BATCH_SIZE as new_const

        assert shim_const == new_const

    def test_utility_functions_consistency(self):
        """测试 engine.py 和 shim 中的工具函数一致性"""
        from src.collision.gpu_collision_engine import _seed_bytes_to_u32_be_array as shim_fn
        from src.collision.gpu.engine import _seed_bytes_to_u32_be_array as new_fn

        assert shim_fn is new_fn

    def test_gpuenginefacade_importable(self):
        """测试 GPUEngineFacade 可以从包中导入"""
        from src.collision.gpu import GPUEngineFacade

        assert GPUEngineFacade is not None
        assert hasattr(GPUEngineFacade, "initialize")
        assert hasattr(GPUEngineFacade, "cleanup")
        assert hasattr(GPUEngineFacade, "get_device_info")


# ========== TestLifecycle ==========


class TestLifecycle:
    """测试引擎生命周期"""

    def test_context_manager(self, mock_targets, mock_engine_patches):
        """测试上下文管理器"""
        patches, _, _ = mock_engine_patches

        active_patches = []
        for p in patches:
            p.start()
            active_patches.append(p)

        try:
            from src.collision.gpu.engine import GPUCollisionEngine

            with GPUCollisionEngine(targets=mock_targets, data_logging_enabled=False) as engine:
                assert engine is not None
            # 退出上下文后，stop 应该被调用
        finally:
            for p in active_patches:
                p.stop()

    def test_start_stop_cycle(self, mock_targets, mock_engine_patches):
        """测试 start/stop 完整生命周期"""
        patches, _, _ = mock_engine_patches

        active_patches = []
        for p in patches:
            p.start()
            active_patches.append(p)

        try:
            from src.collision.gpu.engine import GPUCollisionEngine
            import src.collision.gpu.engine as engine_module

            # Mock SearchModeCoordinator to not actually start threads
            with patch.object(engine_module, "SearchModeCoordinator") as mock_coord:
                mock_coord_instance = MagicMock()
                mock_coord.return_value = mock_coord_instance

                engine = GPUCollisionEngine(targets=mock_targets, data_logging_enabled=False)
                assert engine.is_running() is False

                engine.start(mode="random")
                # SearchModeCoordinator.start should have been called
                mock_coord_instance.start.assert_called_once()

                engine.stop()
                mock_coord_instance.stop.assert_called_once()
        finally:
            for p in active_patches:
                p.stop()

    def test_del_calls_stop(self, mock_targets, mock_engine_patches):
        """测试 __del__ 调用 stop"""
        patches, _, _ = mock_engine_patches

        active_patches = []
        for p in patches:
            p.start()
            active_patches.append(p)

        try:
            from src.collision.gpu.engine import GPUCollisionEngine

            engine = GPUCollisionEngine(targets=mock_targets, data_logging_enabled=False)
            # __del__ 不应抛出异常
            engine.__del__()
        finally:
            for p in active_patches:
                p.stop()
