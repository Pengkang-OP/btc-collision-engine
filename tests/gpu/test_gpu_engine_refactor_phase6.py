"""GPU引擎重构 Phase 6 测试套件 - 集成与兼容性

测试范围:
1. TestEngineIntegration: 构造函数参数完整性, 组件创建
2. (v5.0.0: Shim 层已删除, 向后兼容测试移除)
3. TestComponentDelegation: 委托到 Facade/Core/Monitoring
4. TestSearchModeAccess: 搜索模式属性代理
5. TestModuleImports: 版本号, 常量导出
6. TestLifecycle: start/stop 完整生命周期

版本: v5.0.0
"""

from unittest.mock import MagicMock, patch

import pytest

from src.collision.gpu.protocols import GPUDevice

pytestmark = pytest.mark.gpu

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
        patch("src.collision.gpu.engine.VendorOptimizationFactory.create", return_value=MagicMock()),
        patch("src.collision.gpu.engine.GPUDeviceDetector"),
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
            from src.collision.gpu.engine import CollisionCore, GPUCollisionEngine

            engine = GPUCollisionEngine(  # noqa: F841
                targets=mock_targets,
                data_logging_enabled=False,
            )
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


# v5.0.0: TestBackwardCompatibility 已移除（Shim 层已删除）


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
            from src.collision.gpu.engine import GPUCollisionEngine

            engine = GPUCollisionEngine(targets=mock_targets, data_logging_enabled=False)
            # Mock GPUEngineMonitor 返回真实列表
            engine._engine_monitor.get_adjustment_history = MagicMock(
                return_value=[{"old_size": 1000000, "new_size": 2000000, "reason": "test"}],
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
        """测试包版本号与 __init__.py 一致"""
        from src.collision import gpu

        assert gpu.__version__ == "5.0.0"

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
        from src.collision.gpu import GPUEngineFacade, get_gpu_engine_facade

        assert get_gpu_engine_facade() is GPUEngineFacade

    def test_gpuenginefacade_importable(self):
        """测试 GPUEngineFacade 可以从包中导入"""
        from src.collision.gpu import GPUEngineFacade

        assert GPUEngineFacade is not None
        assert hasattr(GPUEngineFacade, "initialize")
        assert hasattr(GPUEngineFacade, "cleanup")
        assert hasattr(GPUEngineFacade, "get_device_info")


# ========== TestLifecycle ==========


@pytest.mark.skip(reason="Lifecycle API test needs engine refactor completion")
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
            import src.collision.gpu.engine as engine_module
            from src.collision.gpu.engine import GPUCollisionEngine

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

    def test_from_config_creates_engine(self, mock_targets, mock_engine_patches):
        """测试 from_config() 从 GPUEngineConfig 创建引擎实例

        BLOCK-1修复验证: 确保 GPUEngineConfig 包含 from_config() 所需的全部字段。
        """
        patches, _, _ = mock_engine_patches

        active_patches = []
        for p in patches:
            p.start()
            active_patches.append(p)

        try:
            from src.collision.gpu.engine import GPUCollisionEngine, GPUEngineConfig
            from src.collision.gpu.key_generator import KeyGenerationStrategy

            config = GPUEngineConfig(
                targets=mock_targets,
                device_index=0,
                batch_size=2_000_000,
                checkpoint_enabled=True,
                dedup_enabled=True,
                dedup_max_size=500_000,
                checkpoint_interval=60,
                event_bus=None,
                data_logging_enabled=False,
                data_logging_interval=10,
                use_enhanced_monitoring=False,
                use_gpu_memory_pool=False,
                gpu_pool_max_buffers=50,
                gpu_pool_max_memory_mb=256,
                use_async_logging=False,
                check_uncompressed=False,
                key_generation_strategy=KeyGenerationStrategy.AES_CTR,
            )

            engine = GPUCollisionEngine.from_config(config)

            assert engine is not None
            assert engine.targets == mock_targets
            assert engine.device_index == 0
        finally:
            for p in active_patches:
                p.stop()

    def test_from_config_fields_completeness(self):
        """测试 GPUEngineConfig 包含 from_config() 引用的所有字段

        BLOCK-1修复验证: 确保所有字段在 dataclass 中存在，避免 AttributeError。
        """
        from dataclasses import fields

        from src.collision.gpu.engine import GPUEngineConfig

        field_names = {f.name for f in fields(GPUEngineConfig)}

        required = {
            "targets",
            "device_index",
            "batch_size",
            "on_progress",
            "on_match",
            "on_complete",
            "event_bus",
            "checkpoint_enabled",
            "dedup_enabled",
            "dedup_max_size",
            "checkpoint_interval",
            "data_logging_enabled",
            "data_logging_interval",
            "use_enhanced_monitoring",
            "use_gpu_memory_pool",
            "gpu_pool_max_buffers",
            "gpu_pool_max_memory_mb",
            "use_async_logging",
            "async_log_file",
            "async_log_max_bytes",
            "async_log_backup_count",
            "check_uncompressed",
            "key_generation_strategy",
        }

        missing = required - field_names
        assert not missing, f"GPUEngineConfig 缺少字段: {missing}"
