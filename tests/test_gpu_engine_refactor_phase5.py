"""GPU引擎重构 Phase 5 测试套件 - 厂商优化实现

测试范围:
- IntelOptimizationStrategy (导入路径修复验证)
- NvidiaOptimizationStrategy (NvidiaGPUOptimizer 适配)
- AMDOptimizationStrategy (AmdGPUOptimizer 适配)
- DefaultOptimizationStrategy (默认回退)
- VendorOptimizationFactory (工厂创建与注册)
- _extract_device_info (设备信息提取)
- 模块导入与版本号

版本: v4.2.1
创建日期: 2026-04-30
"""

from unittest.mock import MagicMock, patch

import pytest

from src.collision.gpu.protocols import GPUDevice, GPUExecutionContext

pytestmark = pytest.mark.gpu

# ========== Fixtures ==========


@pytest.fixture
def mock_context():
    """创建 Mock GPUExecutionContext"""
    device = GPUDevice(
        device_id=0,
        vendor="unknown",
        name="Test GPU",
        memory_total=8 * 1024 * 1024 * 1024,  # 8GB
    )
    return GPUExecutionContext(
        device=device,
        batch_size=1_000_000,
        vendor="unknown",
        config={"gpu": {"batch_size": 1_000_000}},
        initialized_at=0,
    )


@pytest.fixture
def mock_context_nvidia():
    """NVIDIA GPU 上下文"""
    device = GPUDevice(
        device_id=0,
        vendor="nvidia",
        name="NVIDIA GeForce RTX 4090",
        memory_total=24 * 1024 * 1024 * 1024,  # 24GB
    )
    return GPUExecutionContext(
        device=device,
        batch_size=1_000_000,
        vendor="nvidia",
        config={"gpu": {"batch_size": 1_000_000}},
        initialized_at=0,
    )


@pytest.fixture
def mock_context_amd():
    """AMD GPU 上下文"""
    device = GPUDevice(
        device_id=0,
        vendor="amd",
        name="AMD Radeon RX 7900 XTX",
        memory_total=24 * 1024 * 1024 * 1024,  # 24GB
    )
    return GPUExecutionContext(
        device=device,
        batch_size=1_000_000,
        vendor="amd",
        config={"gpu": {"batch_size": 1_000_000}},
        initialized_at=0,
    )


@pytest.fixture
def mock_context_intel():
    """Intel GPU 上下文"""
    device = GPUDevice(
        device_id=0,
        vendor="intel",
        name="Intel Arc A770",
        memory_total=16 * 1024 * 1024 * 1024,  # 16GB
    )
    return GPUExecutionContext(
        device=device,
        batch_size=262144,
        vendor="intel",
        config={"gpu": {"batch_size": 262144}},
        initialized_at=0,
    )


# ========== Test: IntelOptimizationStrategy ==========


class TestIntelOptimizationStrategy:
    """测试 Intel 优化策略"""

    def test_strategy_creation(self):
        """策略创建"""
        from src.collision.gpu.vendor_strategy import IntelOptimizationStrategy

        strategy = IntelOptimizationStrategy()
        assert strategy is not None

    def test_apply_optimizations_empty_context(self):
        """空上下文时应安全返回"""
        from src.collision.gpu.vendor_strategy import IntelOptimizationStrategy

        strategy = IntelOptimizationStrategy()
        context = GPUExecutionContext()
        components = strategy.apply_optimizations(context)
        assert isinstance(components, dict)

    def test_get_monitoring_components(self):
        """获取监控组件列表"""
        from src.collision.gpu.vendor_strategy import IntelOptimizationStrategy

        strategy = IntelOptimizationStrategy()
        components = strategy.get_monitoring_components()
        assert "memory_monitor" in components
        assert "timeout_manager" in components


# ========== Test: NvidiaOptimizationStrategy ==========


class TestNvidiaOptimizationStrategy:
    """测试 NVIDIA 优化策略"""

    def test_strategy_creation(self):
        """策略创建"""
        from src.collision.gpu.vendor_strategy import NvidiaOptimizationStrategy

        strategy = NvidiaOptimizationStrategy()
        assert strategy is not None

    def test_apply_optimizations_with_nvidia_context(self, mock_context_nvidia):
        """NVIDIA 上下文应用优化 (Mock NvidiaGPUOptimizer)"""
        from src.collision.gpu.vendor_strategy import NvidiaOptimizationStrategy

        mock_optimizer = MagicMock()
        mock_optimizer.apply_optimizations.return_value = {
            "arch_name": "Ada",
            "recommended_memory_ratio": 0.75,
            "recommended_async_transfer": True,
        }

        strategy = NvidiaOptimizationStrategy()
        with patch(
            "src.gpu.nvidia_optimizer.NvidiaGPUOptimizer",
            return_value=mock_optimizer,
        ):
            components = strategy.apply_optimizations(mock_context_nvidia)

        assert "nvidia_optimizer" in components
        assert "optimization_result" in components
        assert components["optimization_result"]["arch_name"] == "Ada"
        assert components["optimization_result"]["recommended_memory_ratio"] == 0.75

    def test_apply_optimizations_with_empty_context(self):
        """空上下文安全返回"""
        from src.collision.gpu.vendor_strategy import NvidiaOptimizationStrategy

        strategy = NvidiaOptimizationStrategy()
        context = GPUExecutionContext()
        components = strategy.apply_optimizations(context)
        assert isinstance(components, dict)

    def test_apply_optimizations_handles_import_error(self, mock_context_nvidia):
        """导入失败时安全处理"""
        from src.collision.gpu.vendor_strategy import NvidiaOptimizationStrategy

        strategy = NvidiaOptimizationStrategy()
        with patch(
            "src.gpu.nvidia_optimizer.NvidiaGPUOptimizer",
            side_effect=ImportError("No NVIDIA GPU found"),
        ):
            components = strategy.apply_optimizations(mock_context_nvidia)

        assert isinstance(components, dict)
        # 应该为空，因为导入失败
        assert "nvidia_optimizer" not in components

    def test_get_monitoring_components(self):
        """获取 NVIDIA 监控组件"""
        from src.collision.gpu.vendor_strategy import NvidiaOptimizationStrategy

        strategy = NvidiaOptimizationStrategy()
        components = strategy.get_monitoring_components()
        assert "driver_detector" in components
        assert "arch_detector" in components
        assert "memory_optimizer" in components

    def test_extract_device_info(self, mock_context_nvidia):
        """设备信息提取"""
        from src.collision.gpu.vendor_strategy import NvidiaOptimizationStrategy

        strategy = NvidiaOptimizationStrategy()
        info = strategy._extract_device_info(mock_context_nvidia)
        assert info["name"] == "NVIDIA GeForce RTX 4090"
        assert info["vendor"] == "nvidia"
        assert info["global_mem_size"] > 0

    def test_extract_device_info_empty_context(self):
        """空上下文时设备信息提取"""
        from src.collision.gpu.vendor_strategy import NvidiaOptimizationStrategy

        strategy = NvidiaOptimizationStrategy()
        context = GPUExecutionContext()
        info = strategy._extract_device_info(context)
        assert isinstance(info, dict)
        assert len(info) == 0


# ========== Test: AMDOptimizationStrategy ==========


class TestAMDOptimizationStrategy:
    """测试 AMD 优化策略"""

    def test_strategy_creation(self):
        """策略创建"""
        from src.collision.gpu.vendor_strategy import AMDOptimizationStrategy

        strategy = AMDOptimizationStrategy()
        assert strategy is not None

    def test_apply_optimizations_with_amd_context(self, mock_context_amd):
        """AMD 上下文应用优化 (Mock AmdGPUOptimizer)"""
        from src.collision.gpu.vendor_strategy import AMDOptimizationStrategy

        mock_optimizer = MagicMock()
        mock_optimizer.apply_optimizations.return_value = {
            "arch_name": "RDNA3",
            "recommended_memory_ratio": 0.70,
            "recommended_wavefront_size": 32,
        }

        strategy = AMDOptimizationStrategy()
        with patch(
            "src.gpu.amd_optimizer.AmdGPUOptimizer",
            return_value=mock_optimizer,
        ):
            components = strategy.apply_optimizations(mock_context_amd)

        assert "amd_optimizer" in components
        assert "optimization_result" in components
        assert components["optimization_result"]["arch_name"] == "RDNA3"
        assert components["optimization_result"]["recommended_wavefront_size"] == 32

    def test_apply_optimizations_with_empty_context(self):
        """空上下文安全返回"""
        from src.collision.gpu.vendor_strategy import AMDOptimizationStrategy

        strategy = AMDOptimizationStrategy()
        context = GPUExecutionContext()
        components = strategy.apply_optimizations(context)
        assert isinstance(components, dict)

    def test_apply_optimizations_handles_import_error(self, mock_context_amd):
        """导入失败时安全处理"""
        from src.collision.gpu.vendor_strategy import AMDOptimizationStrategy

        strategy = AMDOptimizationStrategy()
        with patch(
            "src.gpu.amd_optimizer.AmdGPUOptimizer",
            side_effect=ImportError("No AMD GPU found"),
        ):
            components = strategy.apply_optimizations(mock_context_amd)

        assert isinstance(components, dict)
        assert "amd_optimizer" not in components

    def test_get_monitoring_components(self):
        """获取 AMD 监控组件"""
        from src.collision.gpu.vendor_strategy import AMDOptimizationStrategy

        strategy = AMDOptimizationStrategy()
        components = strategy.get_monitoring_components()
        assert "driver_detector" in components
        assert "arch_detector" in components
        assert "wavefront_validator" in components
        assert "memory_optimizer" in components

    def test_extract_device_info(self, mock_context_amd):
        """设备信息提取"""
        from src.collision.gpu.vendor_strategy import AMDOptimizationStrategy

        strategy = AMDOptimizationStrategy()
        info = strategy._extract_device_info(mock_context_amd)
        assert info["name"] == "AMD Radeon RX 7900 XTX"
        assert info["vendor"] == "amd"
        assert info["global_mem_size"] > 0

    def test_extract_device_info_empty_context(self):
        """空上下文时设备信息提取"""
        from src.collision.gpu.vendor_strategy import AMDOptimizationStrategy

        strategy = AMDOptimizationStrategy()
        context = GPUExecutionContext()
        info = strategy._extract_device_info(context)
        assert isinstance(info, dict)
        assert len(info) == 0


# ========== Test: DefaultOptimizationStrategy ==========


class TestDefaultOptimizationStrategy:
    """测试默认优化策略"""

    def test_strategy_creation(self):
        """策略创建"""
        from src.collision.gpu.vendor_strategy import DefaultOptimizationStrategy

        strategy = DefaultOptimizationStrategy()
        assert strategy is not None

    def test_apply_optimizations_returns_empty(self, mock_context):
        """默认策略返回空字典"""
        from src.collision.gpu.vendor_strategy import DefaultOptimizationStrategy

        strategy = DefaultOptimizationStrategy()
        components = strategy.apply_optimizations(mock_context)
        assert components == {}

    def test_get_monitoring_components_empty(self):
        """默认策略无监控组件"""
        from src.collision.gpu.vendor_strategy import DefaultOptimizationStrategy

        strategy = DefaultOptimizationStrategy()
        components = strategy.get_monitoring_components()
        assert components == {}


# ========== Test: VendorOptimizationFactory ==========


class TestVendorOptimizationFactory:
    """测试厂商优化策略工厂"""

    def test_create_intel_strategy(self):
        """创建 Intel 策略"""
        from src.collision.gpu.vendor_strategy import (
            IntelOptimizationStrategy,
            VendorOptimizationFactory,
        )

        strategy = VendorOptimizationFactory.create("intel")
        assert isinstance(strategy, IntelOptimizationStrategy)

    def test_create_nvidia_strategy(self):
        """创建 NVIDIA 策略"""
        from src.collision.gpu.vendor_strategy import (
            NvidiaOptimizationStrategy,
            VendorOptimizationFactory,
        )

        strategy = VendorOptimizationFactory.create("nvidia")
        assert isinstance(strategy, NvidiaOptimizationStrategy)

    def test_create_amd_strategy(self):
        """创建 AMD 策略"""
        from src.collision.gpu.vendor_strategy import (
            AMDOptimizationStrategy,
            VendorOptimizationFactory,
        )

        strategy = VendorOptimizationFactory.create("amd")
        assert isinstance(strategy, AMDOptimizationStrategy)

    def test_create_case_insensitive(self):
        """厂商名大小写不敏感"""
        from src.collision.gpu.vendor_strategy import (
            NvidiaOptimizationStrategy,
            VendorOptimizationFactory,
        )

        strategy = VendorOptimizationFactory.create("NVIDIA")
        assert isinstance(strategy, NvidiaOptimizationStrategy)

    def test_create_unknown_vendor_returns_default(self):
        """未知厂商返回默认策略"""
        from src.collision.gpu.vendor_strategy import (
            DefaultOptimizationStrategy,
            VendorOptimizationFactory,
        )

        strategy = VendorOptimizationFactory.create("unknown_vendor")
        assert isinstance(strategy, DefaultOptimizationStrategy)

    def test_create_empty_vendor_returns_default(self):
        """空厂商名返回默认策略"""
        from src.collision.gpu.vendor_strategy import (
            DefaultOptimizationStrategy,
            VendorOptimizationFactory,
        )

        strategy = VendorOptimizationFactory.create("")
        assert isinstance(strategy, DefaultOptimizationStrategy)

    def test_get_supported_vendors(self):
        """获取支持的厂商列表"""
        from src.collision.gpu.vendor_strategy import VendorOptimizationFactory

        vendors = VendorOptimizationFactory.get_supported_vendors()
        assert "intel" in vendors
        assert "nvidia" in vendors
        assert "amd" in vendors

    def test_register_new_vendor(self):
        """注册新厂商策略"""
        from src.collision.gpu.vendor_strategy import VendorOptimizationFactory

        class MockStrategy:
            def apply_optimizations(self, context):
                return {}

            def get_monitoring_components(self):
                return {}

        VendorOptimizationFactory.register("testvendor", MockStrategy)
        vendors = VendorOptimizationFactory.get_supported_vendors()
        assert "testvendor" in vendors

        strategy = VendorOptimizationFactory.create("testvendor")
        assert isinstance(strategy, MockStrategy)

        # 清理：移除测试厂商
        VendorOptimizationFactory._strategies.pop("testvendor", None)

    def test_create_strategy_applies_optimizations(self, mock_context_nvidia):
        """通过工厂创建的策略可正常工作"""
        from src.collision.gpu.vendor_strategy import VendorOptimizationFactory

        mock_optimizer = MagicMock()
        mock_optimizer.apply_optimizations.return_value = {"arch_name": "Test"}

        with patch(
            "src.gpu.nvidia_optimizer.NvidiaGPUOptimizer",
            return_value=mock_optimizer,
        ):
            strategy = VendorOptimizationFactory.create("nvidia")
            components = strategy.apply_optimizations(mock_context_nvidia)

        assert "nvidia_optimizer" in components


# ========== Test: 模块导入与版本 ==========


class TestModuleImports:
    """测试模块导入和版本"""

    def test_import_all_strategies(self):
        """验证所有策略可导入"""
        from src.collision.gpu.vendor_strategy import (
            AMDOptimizationStrategy,
            DefaultOptimizationStrategy,
            IntelOptimizationStrategy,
            NvidiaOptimizationStrategy,
            VendorOptimizationFactory,
        )

        assert IntelOptimizationStrategy is not None
        assert NvidiaOptimizationStrategy is not None
        assert AMDOptimizationStrategy is not None
        assert DefaultOptimizationStrategy is not None
        assert VendorOptimizationFactory is not None

    def test_import_from_gpu_package(self):
        """从 gpu 包导入"""
        from src.collision.gpu import VendorOptimizationFactory

        assert VendorOptimizationFactory is not None

    def test_module_version(self):
        """测试模块版本号 v4.2.1"""
        from src.collision import gpu

        assert gpu.__version__ == "4.4.0"

    def test_vendor_factory_in_all(self):
        """验证 VendorOptimizationFactory 在 __all__ 中"""
        from src.collision.gpu import __all__ as gpu_all

        assert "VendorOptimizationFactory" in gpu_all

    def test_no_phase5_todos_in_vendor_strategy(self):
        """验证 vendor_strategy.py 中无 Phase 5 TODO"""
        import os

        file_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "src",
            "collision",
            "gpu",
            "vendor_strategy.py",
        )
        file_path = os.path.abspath(file_path)
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        assert "# TODO: Phase 5" not in content, "vendor_strategy.py 中还有未处理的 Phase 5 TODO"
        assert (
            "# TODO: Phase 5实现" not in content
        ), "vendor_strategy.py 中还有未处理的 Phase 5实现 TODO"


# ========== Test: 集成测试 ==========


class TestVendorStrategyIntegration:
    """厂商优化策略集成测试"""

    def test_factory_to_strategy_flow(self, mock_context_nvidia):
        """完整工厂→策略→优化流程 (NVIDIA)"""
        from src.collision.gpu.vendor_strategy import VendorOptimizationFactory

        mock_optimizer = MagicMock()
        mock_optimizer.apply_optimizations.return_value = {
            "arch_name": "Ada",
            "recommended_memory_ratio": 0.75,
            "recommended_async_transfer": True,
            "fast_math_disabled": True,
        }

        with patch(
            "src.gpu.nvidia_optimizer.NvidiaGPUOptimizer",
            return_value=mock_optimizer,
        ):
            strategy = VendorOptimizationFactory.create("nvidia")
            components = strategy.apply_optimizations(mock_context_nvidia)
            monitoring = strategy.get_monitoring_components()

        assert len(components) > 0
        assert len(monitoring) > 0

    def test_factory_to_strategy_flow_amd(self, mock_context_amd):
        """完整工厂→策略→优化流程 (AMD)"""
        from src.collision.gpu.vendor_strategy import VendorOptimizationFactory

        mock_optimizer = MagicMock()
        mock_optimizer.apply_optimizations.return_value = {
            "arch_name": "RDNA3",
            "recommended_memory_ratio": 0.70,
            "recommended_wavefront_size": 32,
            "fast_math_disabled": True,
        }

        with patch(
            "src.gpu.amd_optimizer.AmdGPUOptimizer",
            return_value=mock_optimizer,
        ):
            strategy = VendorOptimizationFactory.create("amd")
            components = strategy.apply_optimizations(mock_context_amd)
            monitoring = strategy.get_monitoring_components()

        assert len(components) > 0
        assert len(monitoring) > 0

    def test_all_vendors_have_optimization(self):
        """所有注册厂商的策略都实现了 apply_optimizations"""
        from src.collision.gpu.vendor_strategy import VendorOptimizationFactory

        for vendor in VendorOptimizationFactory.get_supported_vendors():
            strategy = VendorOptimizationFactory.create(vendor)
            assert hasattr(strategy, "apply_optimizations")
            assert callable(strategy.apply_optimizations)

    def test_all_vendors_have_monitoring_components(self):
        """所有注册厂商的策略都实现了 get_monitoring_components"""
        from src.collision.gpu.vendor_strategy import VendorOptimizationFactory

        for vendor in VendorOptimizationFactory.get_supported_vendors():
            strategy = VendorOptimizationFactory.create(vendor)
            assert hasattr(strategy, "get_monitoring_components")
            assert callable(strategy.get_monitoring_components)

    def test_default_fallback_for_all_vendors(self):
        """未知厂商回退到默认策略"""
        from src.collision.gpu.vendor_strategy import (
            DefaultOptimizationStrategy,
            VendorOptimizationFactory,
        )

        unknown_vendors = ["apple", "qualcomm", "arm", "huawei"]
        for vendor in unknown_vendors:
            strategy = VendorOptimizationFactory.create(vendor)
            assert isinstance(strategy, DefaultOptimizationStrategy)


# ========== 运行配置 ==========

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
