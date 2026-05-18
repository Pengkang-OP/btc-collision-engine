#!/usr/bin/env python3
"""GPU引擎重构 Phase 2 外观层单元测试

测试覆盖:
1. DeviceManagerAdapter: 设备管理器适配器
2. GPUKernelAdapter: 内核适配器
3. AsyncPipelineAdapter: 异步管道适配器
4. GPUEngineFacade: 外观层完整功能

所有测试使用 Mock，无需真实 GPU 硬件。
"""

import pytest
from unittest.mock import Mock, patch

pytestmark = pytest.mark.gpu

# ============================================================================
# 协议层数据对象测试
# ============================================================================


class TestProtocolsDataObjects:
    """测试协议层数据对象"""

    def test_gpu_device_creation(self):
        """测试 GPUDevice 创建与属性"""
        from src.collision.gpu.protocols import GPUDevice

        device = GPUDevice(
            device_id=0,
            vendor="nvidia",
            name="RTX 4090",
            memory_total=24 * 1024**3,
            device_obj=None,
        )
        assert device.device_id == 0
        assert device.vendor == "nvidia"
        assert device.name == "RTX 4090"
        assert device.memory_total == 24 * 1024**3

    def test_gpu_device_to_dict(self):
        """测试 GPUDevice.to_dict()"""
        from src.collision.gpu.protocols import GPUDevice

        device = GPUDevice(device_id=1, vendor="amd", name="RX 7900 XTX")
        d = device.to_dict()
        assert d["device_id"] == 1
        assert d["vendor"] == "amd"

    def test_gpu_context_creation(self):
        """测试 GPUContext 创建"""
        from src.collision.gpu.protocols import GPUContext, GPUDevice

        device = GPUDevice(device_id=0)
        ctx = GPUContext(context_obj="mock_ctx", device=device)
        assert ctx.context_obj == "mock_ctx"
        assert ctx.device.device_id == 0

    def test_gpu_kernel_creation(self):
        """测试 GPUKernel 创建"""
        from src.collision.gpu.protocols import GPUKernel

        kernel = GPUKernel(kernel_obj="mock_kernel", name="batch_check")
        assert kernel.kernel_obj == "mock_kernel"
        assert kernel.name == "batch_check"

    def test_collision_result_computed_fields(self):
        """测试 CollisionResult 自动计算字段"""
        from src.collision.gpu.protocols import CollisionResult

        result = CollisionResult(
            matches=[],
            execution_time_ms=100.0,
            batch_size=1_000_000,
        )
        assert result.keys_per_second == pytest.approx(10_000_000.0)
        assert result.timestamp > 0

    def test_collision_result_zero_time(self):
        """测试 execution_time_ms=0 时 keys_per_second 为 0"""
        from src.collision.gpu.protocols import CollisionResult

        result = CollisionResult(
            matches=[],
            execution_time_ms=0.0,
            batch_size=1_000_000,
        )
        assert result.keys_per_second == 0.0

    def test_gpu_execution_context_defaults(self):
        """测试 GPUExecutionContext 默认值"""
        from src.collision.gpu.protocols import GPUExecutionContext

        ctx = GPUExecutionContext()
        assert ctx.batch_size == 1_000_000
        assert ctx.vendor == "unknown"
        assert ctx.device is None


# ============================================================================
# DeviceManagerAdapter 测试
# ============================================================================


class TestDeviceManagerAdapter:
    """测试设备管理器适配器"""

    def test_adapter_creation(self):
        """测试适配器创建"""
        from src.collision.gpu.device_manager_adapter import DeviceManagerAdapter

        adapter = DeviceManagerAdapter(config={"gpu": {"async_execution": True}})
        assert adapter.config["gpu"]["async_execution"] is True

    def test_read_async_config_true(self):
        """测试异步配置读取 - 启用"""
        from src.collision.gpu.device_manager_adapter import DeviceManagerAdapter

        adapter = DeviceManagerAdapter(config={"gpu": {"async_execution": True}})
        assert adapter._read_async_config() is True

    def test_read_async_config_false(self):
        """测试异步配置读取 - 禁用"""
        from src.collision.gpu.device_manager_adapter import DeviceManagerAdapter

        adapter = DeviceManagerAdapter(config={"gpu": {"async_execution": False}})
        assert adapter._read_async_config() is False

    def test_read_async_config_default(self):
        """测试异步配置读取 - 默认启用"""
        from src.collision.gpu.device_manager_adapter import DeviceManagerAdapter

        adapter = DeviceManagerAdapter(config={})
        assert adapter._read_async_config() is True

    @patch("src.collision.gpu.device_manager_adapter.DeviceManagerAdapter.list_devices")
    def test_list_devices_returns_protocol_devices(self, mock_list):
        """测试 list_devices 返回协议层 GPUDevice"""
        from src.collision.gpu.device_manager_adapter import DeviceManagerAdapter
        from src.collision.gpu.protocols import GPUDevice

        mock_list.return_value = [
            GPUDevice(device_id=0, vendor="nvidia", name="RTX 4090"),
            GPUDevice(device_id=1, vendor="amd", name="RX 7900 XTX"),
        ]

        adapter = DeviceManagerAdapter()
        devices = adapter.list_devices()
        assert len(devices) == 2
        assert devices[0].vendor == "nvidia"
        assert devices[1].vendor == "amd"

    def test_get_native_device_none_before_init(self):
        """测试初始化前 get_native_device 返回 None"""
        from src.collision.gpu.device_manager_adapter import DeviceManagerAdapter

        adapter = DeviceManagerAdapter()
        assert adapter.get_native_device() is None
        assert adapter.get_native_context() is None

    def test_release_all_safe_when_nothing_initialized(self):
        """测试未初始化时 release_all 安全"""
        from src.collision.gpu.device_manager_adapter import DeviceManagerAdapter

        adapter = DeviceManagerAdapter()
        adapter.release_all()  # 不应抛出异常


# ============================================================================
# AsyncPipelineAdapter 测试
# ============================================================================


class TestAsyncPipelineAdapter:
    """测试异步管道适配器"""

    def test_adapter_creation(self):
        """测试适配器创建"""
        from src.collision.gpu.async_pipeline_adapter import AsyncPipelineAdapter

        adapter = AsyncPipelineAdapter(config={"queue_depth": 8})
        assert adapter.config["queue_depth"] == 8

    def test_is_ready_false_before_init(self):
        """测试初始化前 is_ready 返回 False"""
        from src.collision.gpu.async_pipeline_adapter import AsyncPipelineAdapter

        adapter = AsyncPipelineAdapter()
        assert adapter.is_ready() is False

    def test_run_batch_raises_before_init(self):
        """测试初始化前 run_batch 抛出异常"""
        from src.collision.gpu.async_pipeline_adapter import AsyncPipelineAdapter

        adapter = AsyncPipelineAdapter()
        with pytest.raises(RuntimeError, match="未初始化"):
            adapter.run_batch(seed=b"\x00" * 32, batch_size=1000)

    def test_cleanup_safe_when_not_initialized(self):
        """测试未初始化时 cleanup 安全"""
        from src.collision.gpu.async_pipeline_adapter import AsyncPipelineAdapter

        adapter = AsyncPipelineAdapter()
        adapter.cleanup()  # 不应抛出异常

    def test_flush_pending_returns_empty_before_init(self):
        """测试初始化前 flush_pending 返回空列表"""
        from src.collision.gpu.async_pipeline_adapter import AsyncPipelineAdapter

        adapter = AsyncPipelineAdapter()
        assert adapter.flush_pending() == []

    def test_get_stats_returns_not_initialized_before_init(self):
        """测试初始化前 get_stats 返回 not_initialized"""
        from src.collision.gpu.async_pipeline_adapter import AsyncPipelineAdapter

        adapter = AsyncPipelineAdapter()
        stats = adapter.get_stats()
        assert stats["status"] == "not_initialized"

    def test_is_ready_with_kernel(self):
        """测试有内核时 is_ready 返回 True"""
        from src.collision.gpu.async_pipeline_adapter import AsyncPipelineAdapter
        from src.collision.gpu.protocols import GPUKernel

        adapter = AsyncPipelineAdapter()
        # 模拟 pipeline 和 kernel 已初始化
        adapter._pipeline = Mock()
        adapter._kernel = GPUKernel(kernel_obj=Mock(), name="batch_check")
        assert adapter.is_ready() is True

    def test_is_ready_with_none_kernel_obj(self):
        """测试内核对象为 None 时 is_ready 返回 False"""
        from src.collision.gpu.async_pipeline_adapter import AsyncPipelineAdapter
        from src.collision.gpu.protocols import GPUKernel

        adapter = AsyncPipelineAdapter()
        adapter._pipeline = Mock()
        adapter._kernel = GPUKernel(kernel_obj=None, name="batch_check")
        assert adapter.is_ready() is False

    def test_prefetch_noop_before_init(self):
        """测试初始化前 prefetch_next_batch 安全"""
        from src.collision.gpu.async_pipeline_adapter import AsyncPipelineAdapter

        adapter = AsyncPipelineAdapter()
        # 不应抛出异常
        adapter.prefetch_next_batch(seed=b"\x00" * 32, num_keys=1000)

    def test_prefetch_delegates_to_pipeline(self):
        """测试预取委托给底层管道"""
        from src.collision.gpu.async_pipeline_adapter import AsyncPipelineAdapter

        adapter = AsyncPipelineAdapter()
        mock_pipeline = Mock()
        adapter._pipeline = mock_pipeline

        seed = b"\x01" * 32
        adapter.prefetch_next_batch(seed=seed, num_keys=1000)
        mock_pipeline.prefetch_next_batch.assert_called_once_with(seed, 1000)

    def test_flush_pending_delegates_to_pipeline(self):
        """测试 flush_pending 委托给底层管道"""
        from src.collision.gpu.async_pipeline_adapter import AsyncPipelineAdapter

        adapter = AsyncPipelineAdapter()
        mock_pipeline = Mock()
        expected = [(b"\x01" * 32, [{"key_index": 0}])]
        mock_pipeline.flush_pending.return_value = expected
        adapter._pipeline = mock_pipeline

        result = adapter.flush_pending()
        assert result == expected


# ============================================================================
# GPUKernelAdapter 测试
# ============================================================================


class TestGPUKernelAdapter:
    """测试GPU内核适配器"""

    def test_adapter_creation(self):
        """测试适配器创建"""
        from src.collision.gpu.kernel_adapter import GPUKernelAdapter

        adapter = GPUKernelAdapter(config={"batch_size": 2_000_000})
        assert adapter.config["batch_size"] == 2_000_000

    def test_execute_batch_raises_without_kernel(self):
        """测试无内核时 execute_batch 抛出异常"""
        from src.collision.gpu.kernel_adapter import GPUKernelAdapter
        from src.collision.gpu.protocols import GPUKernel

        adapter = GPUKernelAdapter()
        with pytest.raises(RuntimeError, match="未初始化"):
            adapter.execute_batch(
                kernel=GPUKernel(kernel_obj=None),
                seed=b"\x00" * 32,
                batch_size=1000,
            )

    def test_convert_matches(self):
        """测试匹配结果格式转换"""
        from src.collision.gpu.kernel_adapter import GPUKernelAdapter

        adapter = GPUKernelAdapter()
        raw = [
            {
                "address": "1A1z...",
                "private_key": "abc",
                "public_key": "xyz",
                "hash160": "deadbeef",
                "index": 42,
                "seed": "seed1",
            },
        ]
        matches = adapter._convert_matches(raw)
        assert len(matches) == 1
        assert matches[0]["address"] == "1A1z..."
        assert matches[0]["index"] == 42

    def test_convert_matches_empty(self):
        """测试空匹配结果转换"""
        from src.collision.gpu.kernel_adapter import GPUKernelAdapter

        adapter = GPUKernelAdapter()
        matches = adapter._convert_matches([])
        assert matches == []


# ============================================================================
# 模块导入测试
# ============================================================================


class TestModuleImports:
    """测试模块导入完整性"""

    def test_import_collision_gpu_module(self):
        """测试 collision.gpu 模块导入"""
        from src.collision import gpu

        assert hasattr(gpu, "GPUEngineFacade")
        assert hasattr(gpu, "CollisionCore")
        assert hasattr(gpu, "PerformanceMonitoringPipeline")
        assert hasattr(gpu, "VendorOptimizationFactory")

    def test_import_phase2_adapters(self):
        """测试 Phase 2 适配器导入"""
        from src.collision.gpu import (
            DeviceManagerAdapter,
            GPUKernelAdapter,
            AsyncPipelineAdapter,
        )

        assert DeviceManagerAdapter is not None
        assert GPUKernelAdapter is not None
        assert AsyncPipelineAdapter is not None

    def test_import_factory_functions(self):
        """测试工厂函数导入"""
        from src.collision.gpu import (
            get_gpu_engine_facade,
            get_device_manager_adapter,
            get_kernel_adapter,
            get_async_pipeline_adapter,
        )

        assert callable(get_gpu_engine_facade)
        assert callable(get_device_manager_adapter)
        assert callable(get_kernel_adapter)
        assert callable(get_async_pipeline_adapter)

    def test_module_version(self):
        """测试模块版本号"""
        from src.collision import gpu

        assert gpu.__version__ == "4.4.0"

    def test_all_exports(self):
        """测试 __all__ 导出列表"""
        from src.collision.gpu import __all__

        expected = [
            "GPUEngineFacade",
            "PerformanceMonitoringPipeline",
            "CollisionCore",
            "VendorOptimizationFactory",
            "DeviceManagerAdapter",
            "GPUKernelAdapter",
            "AsyncPipelineAdapter",
        ]
        for name in expected:
            assert name in __all__, f"{name} 不在 __all__ 中"


# ============================================================================
# 适配器协议符合性测试
# ============================================================================


class TestProtocolConformance:
    """测试适配器是否符合协议"""

    def test_device_manager_adapter_has_protocol_methods(self):
        """测试 DeviceManagerAdapter 实现了 IGPUDeviceManager 协议方法"""
        from src.collision.gpu.device_manager_adapter import DeviceManagerAdapter

        adapter = DeviceManagerAdapter()
        assert callable(getattr(adapter, "list_devices", None))
        assert callable(getattr(adapter, "select_device", None))
        assert callable(getattr(adapter, "create_context", None))
        assert callable(getattr(adapter, "release_all", None))

    def test_async_pipeline_adapter_has_protocol_methods(self):
        """测试 AsyncPipelineAdapter 实现了 IAsyncExecutionPipeline 协议方法"""
        from src.collision.gpu.async_pipeline_adapter import AsyncPipelineAdapter

        adapter = AsyncPipelineAdapter()
        assert callable(getattr(adapter, "initialize", None))
        assert callable(getattr(adapter, "is_ready", None))
        assert callable(getattr(adapter, "run_batch", None))
        assert callable(getattr(adapter, "cleanup", None))

    def test_kernel_adapter_has_protocol_methods(self):
        """测试 GPUKernelAdapter 实现了 IKernelExecutor 协议方法"""
        from src.collision.gpu.kernel_adapter import GPUKernelAdapter

        adapter = GPUKernelAdapter()
        assert callable(getattr(adapter, "compile_kernel", None))
        assert callable(getattr(adapter, "execute_batch", None))


# ============================================================================
# GPUEngineFacade 上下文管理器测试
# ============================================================================


class TestGPUEngineFacadeContextManager:
    """测试 GPUEngineFacade 上下文管理器"""

    def test_context_manager_enter_exit(self):
        """测试上下文管理器自动清理"""
        from src.collision.gpu.facade import GPUEngineFacade

        with patch.object(GPUEngineFacade, "cleanup") as mock_cleanup:
            with GPUEngineFacade(config={}) as facade:
                assert isinstance(facade, GPUEngineFacade)
                assert facade._initialized is False
            mock_cleanup.assert_called_once()

    def test_context_manager_cleanup_on_exception(self):
        """测试异常时上下文管理器仍执行清理"""
        from src.collision.gpu.facade import GPUEngineFacade

        cleanup_called = []

        class TestFacade(GPUEngineFacade):
            def cleanup(self):
                cleanup_called.append(True)
                super().cleanup()

        try:
            with TestFacade(config={}):
                raise ValueError("测试异常")
        except ValueError:
            pass

        assert len(cleanup_called) == 1

    def test_context_manager_enter_returns_self(self):
        """测试 __enter__ 返回自身"""
        from src.collision.gpu.facade import GPUEngineFacade

        facade = GPUEngineFacade()
        assert facade.__enter__() is facade


# ============================================================================
# GPUEngineFacade 线程安全测试
# ============================================================================


class TestGPUEngineFacadeThreadSafety:
    """测试 GPUEngineFacade 线程安全性"""

    def test_cleanup_is_thread_safe(self):
        """测试 cleanup 方法使用了锁保护"""
        from src.collision.gpu.facade import GPUEngineFacade

        facade = GPUEngineFacade()
        assert hasattr(facade, "_lock")

        import threading

        results = []
        errors = []

        def do_cleanup():
            try:
                facade.cleanup()
                results.append(True)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_cleanup) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)

        assert len(errors) == 0
        assert len(results) == 5

    def test_lock_not_rlock(self):
        """测试 _lock 为标准不可重入锁"""
        from src.collision.gpu.facade import GPUEngineFacade

        facade = GPUEngineFacade()
        lock = facade._lock
        assert lock is not None
        acquired = lock.acquire(blocking=False)
        assert acquired is True
        reacquired = lock.acquire(blocking=False)
        assert reacquired is False
        lock.release()
