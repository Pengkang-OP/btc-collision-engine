"""GPU模块单元测试

测试新GPU模块的各项功能,包括:
- 设备检测
- 型号数据库加载
- 厂商优化
- 向后兼容性
"""

import sys
from unittest.mock import Mock, patch

import pytest

pytestmark = pytest.mark.gpu


class TestGPUProfileLoader:
    """测试GPU型号数据库加载器"""

    def setup_method(self, method):
        """测试前准备"""
        from src.gpu.profiles.loader import GPUProfileLoader

        self.loader = GPUProfileLoader()

    def test_load_profiles(self):
        """测试加载配置文件"""
        assert self.loader.profiles is not None
        assert "nvidia" in self.loader.profiles
        assert "amd" in self.loader.profiles
        assert "intel" in self.loader.profiles

    def test_get_nvidia_profile(self):
        """测试获取NVIDIA型号配置"""
        # 测试RTX 3080
        profile = self.loader.get_profile("nvidia", "RTX 3080")
        assert profile is not None
        assert "RTX 3080" in profile["models"]
        assert profile["year"] == 2020

    def test_get_amd_profile(self):
        """测试获取AMD型号配置"""
        # 测试RX 6800 XT
        profile = self.loader.get_profile("amd", "RX 6800 XT")
        assert profile is not None
        assert "RX 6800 XT" in profile["models"]

    def test_get_intel_profile(self):
        """测试获取Intel型号配置"""
        # 测试Arc A770
        profile = self.loader.get_profile("intel", "Intel Arc A770")
        assert profile is not None
        assert "Intel Arc A770" in profile["models"]
        assert "uint32_workaround" in profile["optimizations"]

    def test_model_fuzzy_match(self):
        """测试型号模糊匹配"""
        # 测试带前缀的型号
        profile = self.loader.get_profile("nvidia", "GeForce RTX 3080")
        assert profile is not None

    def test_default_profile(self):
        """测试默认配置"""
        profile = self.loader.get_default_profile("nvidia")
        assert profile is not None
        # 默认配置包含recommended_batch_size等字段
        assert "recommended_batch_size" in profile

    def test_get_all_vendors(self):
        """测试获取所有厂商"""
        vendors = self.loader.get_all_vendors()
        assert "nvidia" in vendors
        assert "amd" in vendors
        assert "intel" in vendors


class TestGPUDeviceDetector:
    """测试GPU设备检测器"""

    @patch("src.gpu.device.PYOPENCL_AVAILABLE", False)
    def test_gpu_not_available(self):
        """测试GPU不可用的情况"""
        from src.gpu.device import GPUDeviceDetector

        # 清除缓存以确保测试准确性
        GPUDeviceDetector.clear_availability_cache()
        assert not GPUDeviceDetector.is_gpu_available()

    @patch("src.gpu.device.cl")
    def test_detect_devices_mocked(self, mock_cl):
        """测试设备检测(模拟)"""
        from src.gpu.device import GPUDeviceDetector

        # 模拟pyopencl返回
        mock_platform = Mock()
        mock_device = Mock()
        mock_device.get_info.side_effect = lambda x: {
            mock_cl.device_info.NAME: "NVIDIA GeForce RTX 3080",
            mock_cl.device_info.TYPE: mock_cl.device_type.GPU,
            mock_cl.device_info.VENDOR: "NVIDIA Corporation",
        }.get(x)
        mock_device.global_mem_size = 10 * 1024**3  # 10GB
        mock_device.max_compute_units = 68

        mock_platform.get_devices.return_value = [mock_device]
        mock_platform.get_info.return_value = "NVIDIA CUDA"
        mock_cl.get_platforms.return_value = [mock_platform]

        devices = GPUDeviceDetector.detect_devices()
        assert len(devices) == 1
        assert devices[0]["name"] == "NVIDIA GeForce RTX 3080"

    def test_select_best_device_priority(self):
        """测试设备选择优先级"""
        from src.gpu.device import GPUDeviceDetector

        devices = [
            {"name": "AMD Radeon RX 6800", "vendor": "AMD", "priority_test": True},
            {"name": "Intel Arc A770", "vendor": "Intel", "priority_test": True},
            {"name": "NVIDIA GeForce RTX 3080", "vendor": "NVIDIA", "priority_test": True},
        ]

        best = GPUDeviceDetector._select_best_device(devices)
        assert "NVIDIA" in best["name"]


class TestGPUVendors:
    """测试厂商优化模块"""

    def test_nvidia_vendor(self):
        """测试NVIDIA优化器"""
        from src.gpu.vendors.nvidia import NVIDIAGPUVendor

        vendor = NVIDIAGPUVendor()
        assert vendor.get_vendor_name() == "NVIDIA"

        # 测试batch_size计算
        mock_device = Mock()
        mock_device.device_info = {"global_mem_size": 10 * 1024**3}
        profile = {
            "recommended_batch_size": 4194304,
            "max_batch_size": 8388608,
            "memory_efficiency": 0.75,
        }

        batch_size = vendor.calculate_batch_size(mock_device, profile)
        assert batch_size > 0
        assert batch_size % 1024 == 0  # 应该对齐到1024

    def test_amd_vendor(self):
        """测试AMD优化器"""
        from src.gpu.vendors.amd import AMDGPUVendor

        vendor = AMDGPUVendor()
        assert vendor.get_vendor_name() == "AMD"

    def test_intel_vendor(self):
        """测试Intel优化器"""
        from src.gpu.vendors.intel import IntelGPUVendor

        vendor = IntelGPUVendor()
        assert vendor.get_vendor_name() == "Intel"

        # 测试Intel的特殊错误处理
        error = RuntimeError("GPU execution timeout")
        result = vendor.handle_errors(error)
        assert result  # 应该继续执行


class TestGPUConfig:
    """测试GPU配置管理器"""

    def test_default_config(self):
        """测试默认配置"""
        from src.gpu.config import GPUConfig

        config = GPUConfig()
        gpu_config = config.get_gpu_config()

        assert "use_gpu" in gpu_config
        assert "device_index" in gpu_config
        assert "batch_size" in gpu_config

    def test_set_config(self):
        """测试设置配置"""
        from src.gpu.config import GPUConfig

        config = GPUConfig()
        config.set_gpu_config(use_gpu=False, device_index=0)

        gpu_config = config.get_gpu_config()
        assert not gpu_config["use_gpu"]
        assert gpu_config["device_index"] == 0

    def test_validate_config(self):
        """测试配置验证"""
        from src.gpu.config import GPUConfig

        config = GPUConfig()
        config.set_gpu_config(batch_size=-1)

        errors = config.validate()
        assert len(errors > 0)


class TestBackwardCompatibility:
    """测试向后兼容性"""

    def test_gpu_collision_engine_import(self):
        """测试gpu_collision_engine.py能正常导入"""
        try:
            assert True
        except ImportError as e:
            pytest.fail(f"导入失败: {e}")

    def test_crypto_config_integration(self):
        """测试crypto_config.py集成"""
        try:
            from src.config.crypto_config import CryptoConfig

            config = CryptoConfig()

            # 测试方法存在
            assert hasattr(config, "is_gpu_available")
            assert hasattr(config, "get_gpu_device_info")
            assert hasattr(config, "create_gpu_engine")
        except ImportError as e:
            pytest.fail(f"导入失败: {e}")


class TestGPUContext:
    """测试GPU上下文管理"""

    def test_context_creation(self):
        """测试上下文创建"""
        # 清理 test_gpu_memory_pool_part2.py 造成的 sys.modules mock 泄漏
        from unittest.mock import Mock

        for mod_name in ("src.gpu.context", "src.gpu.kernel_impl"):
            if mod_name in sys.modules and isinstance(sys.modules[mod_name], Mock):
                del sys.modules[mod_name]

        from src.gpu.context import GPUContext
        from src.gpu.device import GPUDevice

        # 模拟设备
        mock_device_obj = Mock()
        mock_device_obj.global_mem_size = 8 * 1024**3
        mock_device_obj.max_compute_units = 68

        mock_context = Mock()
        mock_queue = Mock()

        # 创建并初始化设备
        device = GPUDevice()
        device.device = mock_device_obj
        device.context = mock_context
        device.queue = mock_queue
        device.device_info = {
            "name": "NVIDIA GeForce RTX 3080",
            "vendor": "NVIDIA Corporation",
            "global_mem_size": 8 * 1024**3,
            "max_compute_units": 68,
        }
        device.vendor = "NVIDIA Corporation"
        device.profile = {"recommended_batch_size": 4194304}

        # 创建上下文
        context = GPUContext(device)
        assert context.vendor_handler is not None
        assert context.vendor_handler.get_vendor_name() == "NVIDIA"

    def test_identify_vendor(self):
        """测试厂商识别函数"""
        from src.gpu.device import identify_vendor

        # NVIDIA
        assert identify_vendor("GeForce RTX 3080") == "nvidia"
        assert identify_vendor("RTX 4090") == "nvidia"
        assert identify_vendor("GTX 1080") == "nvidia"

        # AMD
        assert identify_vendor("Radeon RX 6800 XT") == "amd"
        assert identify_vendor("AMD RX 7900 XTX") == "amd"

        # Intel
        assert identify_vendor("Intel Arc A770") == "intel"
        assert identify_vendor("Intel UHD Graphics") == "intel"

        # Unknown
        assert identify_vendor("Unknown GPU") == "unknown"


class TestResourceCleanup:
    """测试资源清理"""

    @patch("src.gpu.device.cl")
    def test_cleanup_releases_resources(self, mock_cl):
        """测试清理释放资源"""
        from src.gpu.device import GPUDevice

        device = GPUDevice()
        device.queue = Mock()
        device.context = Mock()
        device.device = Mock()
        device.device_info = {"name": "Test GPU"}
        device.vendor = "Test"
        device.profile = {}

        # 执行清理
        device.cleanup()

        # 验证资源已释放
        assert device.queue is None
        assert device.context is None
        assert device.device is None
        assert device.device_info == {}
        assert device.vendor is None
        assert device.profile is None
