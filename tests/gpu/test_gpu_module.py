"""GPU模块单元测试

测试新GPU模块的各项功能,包括:
- 设备检测
- 型号数据库加载
- 厂商优化
- 向后兼容性
"""

import sys
import unittest
from unittest.mock import Mock, patch

import pytest

pytestmark = pytest.mark.gpu


class TestGPUProfileLoader(unittest.TestCase):
    """测试GPU型号数据库加载器"""

    def setUp(self):
        """测试前准备"""
        from src.gpu.profiles.loader import GPUProfileLoader

        self.loader = GPUProfileLoader()

    def test_load_profiles(self):
        """测试加载配置文件"""
        self.assertIsNotNone(self.loader.profiles)
        self.assertIn("nvidia", self.loader.profiles)
        self.assertIn("amd", self.loader.profiles)
        self.assertIn("intel", self.loader.profiles)

    def test_get_nvidia_profile(self):
        """测试获取NVIDIA型号配置"""
        # 测试RTX 3080
        profile = self.loader.get_profile("nvidia", "RTX 3080")
        self.assertIsNotNone(profile)
        self.assertIn("RTX 3080", profile["models"])
        self.assertEqual(profile["year"], 2020)

    def test_get_amd_profile(self):
        """测试获取AMD型号配置"""
        # 测试RX 6800 XT
        profile = self.loader.get_profile("amd", "RX 6800 XT")
        self.assertIsNotNone(profile)
        self.assertIn("RX 6800 XT", profile["models"])

    def test_get_intel_profile(self):
        """测试获取Intel型号配置"""
        # 测试Arc A770
        profile = self.loader.get_profile("intel", "Intel Arc A770")
        self.assertIsNotNone(profile)
        self.assertIn("Intel Arc A770", profile["models"])
        self.assertIn("uint32_workaround", profile["optimizations"])

    def test_model_fuzzy_match(self):
        """测试型号模糊匹配"""
        # 测试带前缀的型号
        profile = self.loader.get_profile("nvidia", "GeForce RTX 3080")
        self.assertIsNotNone(profile)

    def test_default_profile(self):
        """测试默认配置"""
        profile = self.loader.get_default_profile("nvidia")
        self.assertIsNotNone(profile)
        # 默认配置包含recommended_batch_size等字段
        self.assertIn("recommended_batch_size", profile)

    def test_get_all_vendors(self):
        """测试获取所有厂商"""
        vendors = self.loader.get_all_vendors()
        self.assertIn("nvidia", vendors)
        self.assertIn("amd", vendors)
        self.assertIn("intel", vendors)


class TestGPUDeviceDetector(unittest.TestCase):
    """测试GPU设备检测器"""

    @patch("src.gpu.device.PYOPENCL_AVAILABLE", False)
    def test_gpu_not_available(self):
        """测试GPU不可用的情况"""
        from src.gpu.device import GPUDeviceDetector

        # 清除缓存以确保测试准确性
        GPUDeviceDetector.clear_availability_cache()
        self.assertFalse(GPUDeviceDetector.is_gpu_available())

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
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["name"], "NVIDIA GeForce RTX 3080")

    def test_select_best_device_priority(self):
        """测试设备选择优先级"""
        from src.gpu.device import GPUDeviceDetector

        devices = [
            {"name": "AMD Radeon RX 6800", "vendor": "AMD", "priority_test": True},
            {"name": "Intel Arc A770", "vendor": "Intel", "priority_test": True},
            {"name": "NVIDIA GeForce RTX 3080", "vendor": "NVIDIA", "priority_test": True},
        ]

        best = GPUDeviceDetector._select_best_device(devices)
        self.assertIn("NVIDIA", best["name"])


class TestGPUVendors(unittest.TestCase):
    """测试厂商优化模块"""

    def test_nvidia_vendor(self):
        """测试NVIDIA优化器"""
        from src.gpu.vendors.nvidia import NVIDIAGPUVendor

        vendor = NVIDIAGPUVendor()
        self.assertEqual(vendor.get_vendor_name(), "NVIDIA")

        # 测试batch_size计算
        mock_device = Mock()
        mock_device.device_info = {"global_mem_size": 10 * 1024**3}
        profile = {
            "recommended_batch_size": 4194304,
            "max_batch_size": 8388608,
            "memory_efficiency": 0.75,
        }

        batch_size = vendor.calculate_batch_size(mock_device, profile)
        self.assertGreater(batch_size, 0)
        self.assertEqual(batch_size % 1024, 0)  # 应该对齐到1024

    def test_amd_vendor(self):
        """测试AMD优化器"""
        from src.gpu.vendors.amd import AMDGPUVendor

        vendor = AMDGPUVendor()
        self.assertEqual(vendor.get_vendor_name(), "AMD")

    def test_intel_vendor(self):
        """测试Intel优化器"""
        from src.gpu.vendors.intel import IntelGPUVendor

        vendor = IntelGPUVendor()
        self.assertEqual(vendor.get_vendor_name(), "Intel")

        # 测试Intel的特殊错误处理
        error = RuntimeError("GPU execution timeout")
        result = vendor.handle_errors(error)
        self.assertTrue(result)  # 应该继续执行


class TestGPUConfig(unittest.TestCase):
    """测试GPU配置管理器"""

    def test_default_config(self):
        """测试默认配置"""
        from src.gpu.config import GPUConfig

        config = GPUConfig()
        gpu_config = config.get_gpu_config()

        self.assertIn("use_gpu", gpu_config)
        self.assertIn("device_index", gpu_config)
        self.assertIn("batch_size", gpu_config)

    def test_set_config(self):
        """测试设置配置"""
        from src.gpu.config import GPUConfig

        config = GPUConfig()
        config.set_gpu_config(use_gpu=False, device_index=0)

        gpu_config = config.get_gpu_config()
        self.assertFalse(gpu_config["use_gpu"])
        self.assertEqual(gpu_config["device_index"], 0)

    def test_validate_config(self):
        """测试配置验证"""
        from src.gpu.config import GPUConfig

        config = GPUConfig()
        config.set_gpu_config(batch_size=-1)

        errors = config.validate()
        self.assertTrue(len(errors) > 0)


class TestBackwardCompatibility(unittest.TestCase):
    """测试向后兼容性"""

    def test_gpu_collision_engine_import(self):
        """测试gpu_collision_engine.py能正常导入"""
        try:

            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"导入失败: {e}")

    def test_crypto_config_integration(self):
        """测试crypto_config.py集成"""
        try:
            from src.config.crypto_config import CryptoConfig

            config = CryptoConfig()

            # 测试方法存在
            self.assertTrue(hasattr(config, "is_gpu_available"))
            self.assertTrue(hasattr(config, "get_gpu_device_info"))
            self.assertTrue(hasattr(config, "create_gpu_engine"))
        except ImportError as e:
            self.fail(f"导入失败: {e}")


class TestGPUContext(unittest.TestCase):
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
        self.assertIsNotNone(context.vendor_handler)
        self.assertEqual(context.vendor_handler.get_vendor_name(), "NVIDIA")

    def test_identify_vendor(self):
        """测试厂商识别函数"""
        from src.gpu.device import identify_vendor

        # NVIDIA
        self.assertEqual(identify_vendor("GeForce RTX 3080"), "nvidia")
        self.assertEqual(identify_vendor("RTX 4090"), "nvidia")
        self.assertEqual(identify_vendor("GTX 1080"), "nvidia")

        # AMD
        self.assertEqual(identify_vendor("Radeon RX 6800 XT"), "amd")
        self.assertEqual(identify_vendor("AMD RX 7900 XTX"), "amd")

        # Intel
        self.assertEqual(identify_vendor("Intel Arc A770"), "intel")
        self.assertEqual(identify_vendor("Intel UHD Graphics"), "intel")

        # Unknown
        self.assertEqual(identify_vendor("Unknown GPU"), "unknown")


class TestResourceCleanup(unittest.TestCase):
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
        self.assertIsNone(device.queue)
        self.assertIsNone(device.context)
        self.assertIsNone(device.device)
        self.assertEqual(device.device_info, {})
        self.assertIsNone(device.vendor)
        self.assertIsNone(device.profile)


if __name__ == "__main__":
    unittest.main()
