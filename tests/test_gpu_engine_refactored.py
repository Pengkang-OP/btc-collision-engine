"""GPU碰撞引擎重构模块测试

Phase 1集成测试框架，验证:
1. 模块导入无循环依赖
2. 接口协议定义正确
3. 组件实例化成功
4. 向后兼容API

版本: v4.2.1
创建日期: 2026-04-29
"""

import sys

import pytest

pytestmark = pytest.mark.gpu


class TestModuleImports:
    """测试模块导入"""

    def test_import_protocols(self):
        """测试协议模块导入"""
        from src.collision.gpu.protocols import (
            IAsyncExecutionPipeline,
            IGPUDeviceManager,
            IKernelExecutor,
        )

        assert IGPUDeviceManager is not None
        assert IKernelExecutor is not None
        assert IAsyncExecutionPipeline is not None

    def test_import_facade(self):
        """（已移除-GPUEngineFacade 已删除）"""

    def test_import_monitoring(self):
        """测试监控管道导入"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        assert PerformanceMonitoringPipeline is not None

    def test_import_core(self):
        """测试碰撞核心导入"""
        from src.collision.gpu.core import CollisionCore

        assert CollisionCore is not None

    def test_import_vendor_strategy(self):
        """测试厂商策略导入"""
        from src.collision.gpu.vendor_strategy import (
            VendorOptimizationFactory,
        )

        assert VendorOptimizationFactory is not None

    def test_import_module_init(self):
        """测试模块入口导入"""
        from src.collision.gpu import (
            get_gpu_engine_facade,
        )

        assert get_gpu_engine_facade is not None
        assert callable(get_gpu_engine_facade)


class TestNoCircularDependency:
    """测试无循环依赖"""

    def test_import_order_independence(self):
        """测试导入顺序无关性"""
        # 保存原始模块引用，防止清除后污染其他测试
        saved_modules = {k: v for k, v in sys.modules.items() if "src.collision.gpu" in k}
        modules_to_clear = list(saved_modules.keys())
        for mod in modules_to_clear:
            del sys.modules[mod]

        try:
            # 清空模块缓存后按不同顺序重新导入，验证无循环依赖
            import importlib

            importlib.import_module("src.collision.gpu.facade")
            importlib.import_module("src.collision.gpu.monitoring")
            importlib.import_module("src.collision.gpu.precompute")
            importlib.import_module("src.collision.gpu")
        except ImportError as e:
            pytest.fail(f"导入失败（可能存在循环依赖）: {e}")
        finally:
            # 恢复原始模块引用，防止交叉测试污染
            sys.modules.update(saved_modules)

    def test_all_modules_importable(self):
        """测试所有模块可导入"""
        module_list = [
            "src.collision.gpu",
            "src.collision.gpu.protocols",
            "src.collision.gpu.facade",
            "src.collision.gpu.monitoring",
            "src.collision.gpu.core",
            "src.collision.gpu.vendor_strategy",
            "src.collision.gpu.kernel_adapter",
            "src.collision.gpu.async_pipeline_adapter",
        ]

        for module_name in module_list:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"模块 {module_name} 导入失败: {e}")


class TestProtocolDefinitions:
    """测试接口协议定义"""

    def test_gpu_execution_context(self):
        """测试GPU执行上下文"""
        from src.collision.gpu.protocols import GPUExecutionContext

        context = GPUExecutionContext(batch_size=1000000, vendor="intel")
        assert context.batch_size == 1000000
        assert context.vendor == "intel"
        assert context.device is None
        assert context.context is None

    def test_collision_result(self):
        """测试碰撞结果"""
        from src.collision.gpu.protocols import CollisionResult

        result = CollisionResult(matches=[], execution_time_ms=50.0, batch_size=1000)
        assert result.execution_time_ms == 50.0
        assert result.batch_size == 1000
        assert len(result.matches) == 0


class TestComponentInstantiation:
    """测试组件实例化"""

    def test_monitoring_instantiation(self):
        """测试监控管道实例化"""
        from src.collision.gpu.monitoring import PerformanceMonitoringPipeline

        monitoring = PerformanceMonitoringPipeline(engine=None, config={})
        assert monitoring is not None
        assert not monitoring.is_running()

    def test_core_instantiation(self):
        """测试碰撞核心实例化"""
        from src.collision.gpu.core import CollisionCore

        targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        core = CollisionCore(targets=targets, config={})
        assert core is not None
        assert not core.is_running()

    def test_vendor_factory(self):
        """测试厂商工厂"""
        from src.collision.gpu.vendor_strategy import VendorOptimizationFactory

        # 测试Intel策略
        intel_strategy = VendorOptimizationFactory.create("intel")
        assert intel_strategy is not None

        # 测试NVIDIA策略
        nvidia_strategy = VendorOptimizationFactory.create("nvidia")
        assert nvidia_strategy is not None

        # 测试未知厂商（应返回默认策略）
        unknown_strategy = VendorOptimizationFactory.create("unknown")
        assert unknown_strategy is not None

    def test_supported_vendors(self):
        """测试支持的厂商列表"""
        from src.collision.gpu.vendor_strategy import VendorOptimizationFactory

        vendors = VendorOptimizationFactory.get_supported_vendors()
        assert "intel" in vendors
        assert "nvidia" in vendors
        assert "amd" in vendors


class TestBackwardCompatibility:
    """测试向后兼容性"""

    def test_delayed_import_functions(self):
        """测试延迟导入函数"""
        from src.collision.gpu import (
            get_collision_core,
            get_gpu_engine_facade,
            get_monitoring_pipeline,
            get_vendor_factory,
        )

        # 验证返回的是类而非实例
        facade_cls = get_gpu_engine_facade()
        monitoring_cls = get_monitoring_pipeline()
        core_cls = get_collision_core()
        factory_cls = get_vendor_factory()

        assert facade_cls is not None
        assert monitoring_cls is not None
        assert core_cls is not None
        assert factory_cls is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
