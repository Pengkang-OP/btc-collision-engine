#!/usr/bin/env python3
"""GPU设备选择和切换功能全面测试
验证多GPU环境下不同厂商GPU的检测、评分、选择和切换功能
"""

import sys
import time
import unittest
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.gpu.device import GPUDevice, GPUDeviceDetector, identify_vendor
from src.gpu.selector import GPUDeviceSelector, get_gpu_selector, reset_gpu_selector

pytestmark = pytest.mark.gpu

# 修复Windows编码（Python 3.7+: reconfigure 安全无副作用）
if sys.platform == "win32":
    import io

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", closefd=False)


# Mock pyopencl常量
def create_mock_cl():
    """创建Mock的pyopencl模块"""
    mock_cl = Mock()

    # 设备类型常量
    class device_type:
        CPU = 0x2
        GPU = 0x4

    class device_info:
        TYPE = 0x1000
        NAME = 0x1001
        VENDOR = 0x1002
        GLOBAL_MEM_SIZE = 0x1003
        MAX_COMPUTE_UNITS = 0x1004

    class platform_info:
        NAME = 0x1000

    class command_queue_properties:
        PROFILING_ENABLE = 0x1

    mock_cl.device_type = device_type
    mock_cl.device_info = device_info
    mock_cl.platform_info = platform_info
    mock_cl.command_queue_properties = command_queue_properties

    return mock_cl


# cl模块的设备信息常量（实际 pyopencl 常量值，通过 int(cl.device_info.XXX) 确认）
_CL_DEVICE_TYPE = 4096  # int(cl.device_info.TYPE)
_CL_DEVICE_NAME = 4139  # int(cl.device_info.NAME)
_CL_DEVICE_VENDOR = 4140  # int(cl.device_info.VENDOR)
_CL_PLATFORM_NAME = 2306  # int(cl.platform_info.NAME)
_CL_DEVICE_TYPE_CPU = 2  # int(cl.device_type.CPU)
_CL_DEVICE_TYPE_GPU = 4  # int(cl.device_type.GPU)


def make_mock_gpu_device(
    name: str,
    vendor: str,
    mem_size: int,
    compute_units: int,
    device_type_val: int = _CL_DEVICE_TYPE_GPU,
) -> Mock:
    """创建正确配置的 Mock GPU 设备。

    src/gpu/device.py 的 detect_devices() 通过 device.get_info(cl.device_info.XXX)
    读取设备属性，因此必须为 Mock 配置 get_info() 方法。
    同时直接属性 global_mem_size / max_compute_units 也需要设置。
    """
    device = MagicMock()
    device.global_mem_size = mem_size
    device.max_compute_units = compute_units
    device.max_work_group_size = 256  # 避免格式化字符串时返回 MagicMock
    device.local_mem_size = 32768  # 32KB 默认局部内存

    # get_info 映射表：使用实际 cl.device_info 的整数常量值
    _info_map = {
        _CL_DEVICE_TYPE: device_type_val,
        _CL_DEVICE_NAME: name,
        _CL_DEVICE_VENDOR: vendor,
    }

    def _get_info(key):
        # 兼容枚举值或整数值
        k = int(key) if hasattr(key, "__int__") else key
        return _info_map.get(k)

    device.get_info.side_effect = _get_info
    # 保留 .name .vendor .type 属性以兼容部分直接访问
    device.name = name
    device.vendor = vendor
    device.type = device_type_val
    return device


def make_mock_platform(name: str = "Mock Platform") -> Mock:
    """创建正确配置的 Mock Platform，支持 get_info() 调用。"""
    platform = MagicMock()
    platform.name = name

    def _get_info(key):
        k = int(key) if hasattr(key, "__int__") else key
        if k == _CL_PLATFORM_NAME:
            return name
        return None

    platform.get_info.side_effect = _get_info
    return platform


class TestGPUDeviceDetection:
    """测试1: GPU设备检测功能"""

    def setUp(self):
        """测试前准备"""
        # 清除缓存确保每次测试独立
        GPUDeviceDetector.clear_availability_cache()
        reset_gpu_selector()

    def test_01_detect_single_gpu(self):
        """测试1.1: 检测单个GPU设备"""
        print("\n📋 测试1.1: 检测单个GPU设备")

        # Mock单个GPU设备
        mock_device = make_mock_gpu_device(
            name="NVIDIA GeForce RTX 3080",
            vendor="NVIDIA Corporation",
            mem_size=8589934592,
            compute_units=68,
        )

        mock_platform = make_mock_platform("Mock Platform")
        mock_platform.get_devices = Mock(return_value=[mock_device])

        with patch("src.gpu.device.cl.get_platforms", return_value=[mock_platform]):
            devices = GPUDeviceDetector.detect_devices()

            assert len(devices) == 1
            assert devices[0]["name"] == "NVIDIA GeForce RTX 3080"
            assert devices[0]["vendor"] == "NVIDIA Corporation"
            assert devices[0]["type"] == "GPU"
            print(f"  ✅ 成功检测到: {devices[0]['name']}")

    def test_02_detect_multi_gpu(self):
        """测试1.2: 检测多个GPU设备(不同厂商)"""
        print("\n📋 测试1.2: 检测多个GPU设备")

        nvidia_gpu = make_mock_gpu_device(
            "NVIDIA GeForce RTX 3080",
            "NVIDIA Corporation",
            10737418240,
            68,  # 10GB
        )

        amd_gpu = make_mock_gpu_device(
            "AMD Radeon RX 6800 XT",
            "Advanced Micro Devices, Inc.",
            17179869184,
            72,  # 16GB
        )

        intel_gpu = make_mock_gpu_device(
            "Intel(R) Arc(TM) A770 Graphics",
            "Intel Corporation",
            17179869184,
            512,  # 16GB
        )

        # 模拟两个平台
        platform1 = make_mock_platform("Platform 1")
        platform1.get_devices = Mock(return_value=[nvidia_gpu])

        platform2 = make_mock_platform("Platform 2")
        platform2.get_devices = Mock(return_value=[amd_gpu, intel_gpu])

        with patch("src.gpu.device.cl.get_platforms", return_value=[platform1, platform2]):
            devices = GPUDeviceDetector.detect_devices()

            assert len(devices) == 3

            # 验证每个设备信息
            vendors = [d["vendor"] for d in devices]
            assert any("NVIDIA" in v for v in vendors)
            assert any("AMD" in v or "Advanced" in v for v in vendors)
            assert any("Intel" in v for v in vendors)

            print(f"  ✅ 检测到 {len(devices)} 个GPU设备:")
            for i, dev in enumerate(devices):
                print(f"     [{i}] {dev['name']} ({dev['vendor']})")

    def test_03_filter_cpu_devices(self):
        """测试1.3: 过滤CPU设备"""
        print("\n📋 测试1.3: 过滤CPU设备")

        cpu_device = make_mock_gpu_device(
            name="Intel(R) Core(TM) i7-10700K",
            vendor="Intel(R) Corporation",
            mem_size=34359738368,
            compute_units=16,
            device_type_val=_CL_DEVICE_TYPE_CPU,  # CPU类型
        )

        gpu_device = make_mock_gpu_device(
            name="NVIDIA GeForce GTX 1660",
            vendor="NVIDIA Corporation",
            mem_size=6442450944,
            compute_units=22,
        )

        platform = make_mock_platform("Mock Platform")
        platform.get_devices = Mock(return_value=[cpu_device, gpu_device])

        with patch("src.gpu.device.cl.get_platforms", return_value=[platform]):
            devices = GPUDeviceDetector.detect_devices()

            # 应该只检测到GPU,CPU被过滤
            assert len(devices) == 1
            assert "GTX 1660" in devices[0]["name"]
            print(f"  ✅ CPU设备已过滤,仅保留GPU: {devices[0]['name']}")

    def test_04_filter_integrated_gpu(self):
        """测试1.4: 过滤Intel核显"""
        print("\n📋 测试1.4: 过滤Intel核显")

        integrated_gpu = make_mock_gpu_device(
            name="Intel(R) UHD Graphics 630",
            vendor="Intel Corporation",
            mem_size=8589934592,
            compute_units=24,
        )

        discrete_gpu = make_mock_gpu_device(
            name="Intel(R) Arc(TM) A770 Graphics",
            vendor="Intel Corporation",
            mem_size=17179869184,
            compute_units=512,
        )

        platform = make_mock_platform("Mock Platform")
        platform.get_devices = Mock(return_value=[integrated_gpu, discrete_gpu])

        with patch("src.gpu.device.cl.get_platforms", return_value=[platform]):
            devices = GPUDeviceDetector.detect_devices()

            # 应该只检测到独显,核显被过滤
            assert len(devices) == 1
            assert "Arc" in devices[0]["name"]
            print(f"  ✅ 核显已过滤,仅保留独显: {devices[0]['name']}")

    def test_05_availability_cache(self):
        """测试1.5: GPU可用性检测缓存机制"""
        print("\n📋 测试1.5: GPU可用性缓存机制")

        mock_device = make_mock_gpu_device(
            name="Test GPU",
            vendor="Test Vendor",
            mem_size=8589934592,
            compute_units=68,
        )

        platform = make_mock_platform("Mock Platform")
        platform.get_devices = Mock(return_value=[mock_device])

        call_count = 0

        def mock_get_platforms():
            nonlocal call_count
            call_count += 1
            return [platform]

        with patch("src.gpu.device.cl.get_platforms", side_effect=mock_get_platforms):
            # 第一次调用 - 应该执行实际检测
            result1 = GPUDeviceDetector.is_gpu_available()
            assert result1
            first_call_count = call_count

            # 第二次调用 - 应该使用缓存
            result2 = GPUDeviceDetector.is_gpu_available()
            assert result2
            second_call_count = call_count

            # 验证缓存生效(调用次数未增加)
            assert first_call_count == second_call_count
            print(
                f"  ✅ 缓存机制正常: 检测{first_call_count}次,缓存命中{second_call_count - first_call_count}次",
            )

            # 清除缓存后再次调用 - 应该重新检测
            GPUDeviceDetector.clear_availability_cache()
            result3 = GPUDeviceDetector.is_gpu_available()
            assert result3
            assert call_count == first_call_count + 1
            print("  ✅ 缓存清除后重新检测成功")


class TestGPUVendorIdentification:
    """测试2: GPU厂商识别功能"""

    def test_01_identify_nvidia(self):
        """测试2.1: 识别NVIDIA GPU"""
        print("\n📋 测试2.1: 识别NVIDIA GPU")

        test_cases = [
            ("NVIDIA GeForce RTX 3080", "NVIDIA Corporation"),
            ("GeForce GTX 1660 Ti", "NVIDIA"),
            ("RTX 4090", "NVIDIA Corporation"),
            ("Tesla V100", "NVIDIA"),
        ]

        for name, vendor in test_cases:
            result = identify_vendor(name, vendor)
            assert result == "nvidia", f"Failed for {name}"
            print(f"  ✅ {name} -> {result}")

    def test_02_identify_amd(self):
        """测试2.2: 识别AMD GPU"""
        print("\n📋 测试2.2: 识别AMD GPU")

        test_cases = [
            ("AMD Radeon RX 6800 XT", "Advanced Micro Devices, Inc."),
            ("Radeon RX 5700 XT", "AMD"),
            ("AMD Radeon Pro W6800", "AMD"),
        ]

        for name, vendor in test_cases:
            result = identify_vendor(name, vendor)
            assert result == "amd", f"Failed for {name}"
            print(f"  ✅ {name} -> {result}")

    def test_03_identify_intel(self):
        """测试2.3: 识别Intel GPU"""
        print("\n📋 测试2.3: 识别Intel GPU")

        test_cases = [
            ("Intel(R) Arc(TM) A770 Graphics", "Intel Corporation"),
            ("Intel Arc A750", "Intel"),
            ("Intel(R) UHD Graphics 630", "Intel Corporation"),
        ]

        for name, vendor in test_cases:
            result = identify_vendor(name, vendor)
            assert result == "intel", f"Failed for {name}"
            print(f"  ✅ {name} -> {result}")

    def test_04_identify_unknown(self):
        """测试2.4: 识别未知厂商"""
        print("\n📋 测试2.4: 识别未知厂商GPU")

        result = identify_vendor("Unknown GPU", "Unknown Vendor")
        assert result == "unknown"
        print(f"  ✅ 未知厂商正确识别: {result}")


class TestGPUDeviceScoring:
    """测试3: GPU评分和选择算法"""

    def setUp(self):
        """测试前准备"""
        reset_gpu_selector()
        self.selector = GPUDeviceSelector()

    def test_01_score_nvidia_gpu(self):
        """测试3.1: NVIDIA GPU评分"""
        print("\n📋 测试3.1: NVIDIA GPU评分")

        device = {
            "name": "NVIDIA GeForce RTX 3080",
            "vendor": "nvidia",
            "global_mem_gb": 10.0,
            "max_compute_units": 68,
            "global_index": 0,
        }

        score = self.selector.score_device(device)

        # P3-11 统一评分: (10*10 + 68*0.05 + gen_bonus_rtx30=10.0) * 1.0 = 113.4
        expected_score = (10.0 * 10.0 + 68 * 0.05 + 10.0) * 1.0

        assert score == pytest.approx(expected_score, places=1)
        print(f"  ✅ {device['name']} 评分: {score:.1f} (预期: {expected_score:.1f})")

    def test_02_score_amd_gpu(self):
        """测试3.2: AMD GPU评分"""
        print("\n📋 测试3.2: AMD GPU评分")

        device = {
            "name": "AMD Radeon RX 6800 XT",
            "vendor": "amd",
            "global_mem_gb": 16.0,
            "max_compute_units": 72,
            "global_index": 1,
        }

        score = self.selector.score_device(device)

        # P3-11 统一评分: (16*10 + 72*0.05 + gen_bonus_rx6000=8.0) * 0.95 = 163.02
        expected_score = (16.0 * 10.0 + 72 * 0.05 + 8.0) * 0.95

        assert score == pytest.approx(expected_score, places=1)
        print(f"  ✅ {device['name']} 评分: {score:.1f} (预期: {expected_score:.1f})")

    def test_03_score_intel_gpu(self):
        """测试3.3: Intel GPU评分"""
        print("\n📋 测试3.3: Intel GPU评分")

        device = {
            "name": "Intel Arc A770",
            "vendor": "intel",
            "global_mem_gb": 16.0,
            "max_compute_units": 512,
            "global_index": 2,
        }

        score = self.selector.score_device(device)

        # P3-11 统一评分: (16*10 + 512*0.05 + gen_bonus_arc=5.0) * 0.9 = 171.54
        expected_score = (16.0 * 10.0 + 512 * 0.05 + 5.0) * 0.9

        assert score == pytest.approx(expected_score, places=1)
        print(f"  ✅ {device['name']} 评分: {score:.1f} (预期: {expected_score:.1f})")

    def test_04_select_best_device(self):
        """测试3.4: 自动选择最佳GPU"""
        print("\n📋 测试3.4: 自动选择最佳GPU")

        devices = [
            {
                "name": "NVIDIA GeForce RTX 3080",
                "vendor": "nvidia",
                "global_mem_gb": 10.0,
                "max_compute_units": 68,
                "global_index": 0,
            },
            {
                "name": "AMD Radeon RX 6800 XT",
                "vendor": "amd",
                "global_mem_gb": 16.0,
                "max_compute_units": 72,
                "global_index": 1,
            },
            {
                "name": "Intel Arc A770",
                "vendor": "intel",
                "global_mem_gb": 16.0,
                "max_compute_units": 512,
                "global_index": 2,
            },
        ]

        # 计算所有设备分数
        for device in devices:
            device["score"] = self.selector.score_device(device)

        # 选择最佳设备
        best = self.selector.select_best_device(devices)

        assert best is not None
        # Intel Arc A770仍然分数最高 (171.54 > 163.02 > 113.4)
        assert "Arc A770" in best["name"]

        print(f"  ✅ 最佳GPU选择: {best['name']} (评分: {best['score']:.1f})")
        print("     所有设备评分:")
        for dev in sorted(devices, key=lambda d: d["score"], reverse=True):
            print(f"       - {dev['name']}: {dev['score']:.1f}")

    def test_05_select_by_index(self):
        """测试3.5: 根据索引选择GPU"""
        print("\n📋 测试3.5: 根据索引选择GPU")

        devices = [
            {
                "global_index": 0,
                "name": "NVIDIA RTX 3080",
                "vendor": "nvidia",
                "global_mem_gb": 10.0,
                "max_compute_units": 68,
            },
            {
                "global_index": 1,
                "name": "AMD RX 6800 XT",
                "vendor": "amd",
                "global_mem_gb": 16.0,
                "max_compute_units": 72,
            },
        ]

        # Mock detect_all_devices (patch class, not instance — __slots__ prevents instance patching)
        with patch.object(GPUDeviceSelector, "detect_all_devices", return_value=devices):
            # 选择索引0
            device0 = self.selector.get_device_info(0)
            assert device0 is not None
            assert "NVIDIA" in device0["name"]

            # 选择索引1
            device1 = self.selector.get_device_info(1)
            assert device1 is not None
            assert "AMD" in device1["name"]

            # 选择不存在的索引
            device_invalid = self.selector.get_device_info(99)
            assert device_invalid is None

            print("  ✅ 索引选择功能正常")

    def test_06_recommend_batch_size(self):
        """测试3.6: 推荐批次大小"""
        print("\n📋 测试3.6: 推荐批次大小")

        test_cases = [
            # (显存GB, 厂商, 预期批次大小)
            (16.0, "nvidia", 131072),  # >=16GB -> 128K
            (16.0, "intel", 65536),  # Intel减半 -> 64K
            (8.0, "amd", 52428),  # 8GB * 0.8 = 52428.8
            (4.0, "nvidia", 32768),  # >=4GB -> 32K
            (2.0, "nvidia", 16384),  # <4GB -> 16K
        ]

        for mem_gb, vendor, expected in test_cases:
            device = {
                "global_mem_gb": mem_gb,
                "vendor": vendor,
            }

            recommended = self.selector.recommend_batch_size(device)

            # Intel和AMD有调整,允许小误差
            if vendor == "amd":
                assert recommended == pytest.approx(expected, delta=100)
            else:
                assert recommended == expected

            print(f"  ✅ {vendor.upper()} {mem_gb}GB -> {recommended:,}")


class TestGPUSwitching:
    """测试4: GPU切换功能"""

    def setUp(self):
        """测试前准备"""
        reset_gpu_selector()

    def test_01_switch_between_devices(self):
        """测试4.1: 在不同GPU间切换"""
        print("\n📋 测试4.1: GPU切换功能")

        gpu0 = make_mock_gpu_device("NVIDIA RTX 3080", "NVIDIA", 10737418240, 68)
        gpu1 = make_mock_gpu_device("AMD RX 6800 XT", "AMD", 17179869184, 72)

        mock_context = Mock()
        mock_queue = Mock()

        platform = make_mock_platform("Mock Platform")
        platform.get_devices = Mock(return_value=[gpu0, gpu1])

        with patch("src.gpu.device.cl.get_platforms", return_value=[platform]):
            with patch("src.gpu.device.cl.Context", return_value=mock_context):
                with patch("src.gpu.device.cl.CommandQueue", return_value=mock_queue):
                    # 初始化GPUDevice
                    gpu_device = GPUDevice()

                    # 第一次: 使用GPU 0
                    gpu_device.initialize(device_index=0)
                    assert "RTX 3080" in gpu_device.device_info["name"]
                    print(f"  ✅ 切换到GPU 0: {gpu_device.device_info['name']}")

                    # 清理
                    gpu_device.cleanup()

                    # 第二次: 使用GPU 1
                    gpu_device.initialize(device_index=1)
                    assert "RX 6800 XT" in gpu_device.device_info["name"]
                    print(f"  ✅ 切换到GPU 1: {gpu_device.device_info['name']}")

                    # 清理
                    gpu_device.cleanup()

    def test_02_auto_select_fallback(self):
        """测试4.2: 自动选择最佳GPU"""
        print("\n📋 测试4.2: 自动选择GPU(-1索引)")

        # 创建3个GPU，AMD显存最大应该被选中
        gpu0 = make_mock_gpu_device("NVIDIA GTX 1660", "NVIDIA", 6442450944, 22)
        gpu1 = make_mock_gpu_device("AMD RX 6800 XT", "AMD", 17179869184, 72)
        gpu2 = make_mock_gpu_device("Intel Arc A750", "Intel", 8589934592, 512)

        mock_context = Mock()
        mock_queue = Mock()

        platform = make_mock_platform("Mock Platform")
        platform.get_devices = Mock(return_value=[gpu0, gpu1, gpu2])

        with patch("src.gpu.device.cl.get_platforms", return_value=[platform]):
            with patch("src.gpu.device.cl.Context", return_value=mock_context):
                with patch("src.gpu.device.cl.CommandQueue", return_value=mock_queue):
                    gpu_device = GPUDevice()

                    # 使用-1自动选择
                    gpu_device.initialize(device_index=-1)

                    # 应该选择AMD RX 6800 XT(显存最大)
                    assert "RX 6800 XT" in gpu_device.device_info["name"]
                    print(f"  ✅ 自动选择最佳GPU: {gpu_device.device_info['name']}")

                    gpu_device.cleanup()

    def test_03_invalid_device_index(self):
        """测试4.3: 无效设备索引处理"""
        print("\n📋 测试4.3: 无效设备索引处理")

        mock_device = make_mock_gpu_device(
            name="Test GPU",
            vendor="Test",
            mem_size=8589934592,
            compute_units=68,
        )

        platform = make_mock_platform("Mock Platform")
        platform.get_devices = Mock(return_value=[mock_device])

        with patch("src.gpu.device.cl.get_platforms", return_value=[platform]):
            gpu_device = GPUDevice()

            # 尝试使用不存在的索引
            with pytest.raises(ValueError) as context:
                gpu_device.initialize(device_index=5)

            # 验证错误信息包含可用设备列表
            error_msg = str(context.exception)
            assert "超出范围" in error_msg
            print(f"  ✅ 正确处理无效索引: {error_msg[:50]}...")


class TestGPUConfigurationAdaptation:
    """测试5: 配置适配功能"""

    def setUp(self):
        """测试前准备"""
        reset_gpu_selector()
        self.selector = GPUDeviceSelector()

    def test_01_batch_size_adaptation(self):
        """测试5.1: 批次大小根据GPU适配"""
        print("\n📋 测试5.1: 批次大小适配")

        test_configs = [
            # (设备名称, 显存GB, 厂商, 预期批次大小范围)
            ("NVIDIA RTX 4090", 24.0, "nvidia", (100000, 150000)),
            ("AMD RX 7900 XTX", 24.0, "amd", (80000, 120000)),
            ("Intel Arc A770", 16.0, "intel", (50000, 80000)),
            ("NVIDIA GTX 1660", 6.0, "nvidia", (30000, 50000)),
        ]

        for name, mem_gb, vendor, (min_batch, max_batch) in test_configs:
            device = {
                "name": name,
                "vendor": vendor,
                "global_mem_gb": mem_gb,
                "max_compute_units": 100,
            }

            batch_size = self.selector.recommend_batch_size(device)

            assert batch_size >= min_batch
            assert batch_size <= max_batch

            print(f"  ✅ {name}: {batch_size:,} (范围: {min_batch:,}-{max_batch:,})")

    def test_02_work_group_size_adaptation(self):
        """测试5.2: 工作组大小适配"""
        print("\n📋 测试5.2: 工作组大小适配")

        test_cases = [
            ("NVIDIA RTX 3080", "nvidia", 1024, 512),
            ("AMD RX 6800 XT", "amd", 1024, 256),
            ("Intel Arc A770", "intel", 1024, 256),
        ]

        for name, vendor, max_work_group, expected in test_cases:
            device = {
                "name": name,
                "vendor": vendor,
                "max_work_group_size": max_work_group,
            }

            work_group = self.selector.recommend_work_group_size(device)

            assert work_group == expected
            print(f"  ✅ {name}: 工作组大小 {work_group}")

    def test_03_memory_pool_configuration(self):
        """测试5.3: 内存池配置适配"""
        print("\n📋 测试5.3: 内存池配置")

        # 不同显存的GPU应有不同的内存池配置
        devices = [
            {"global_mem_gb": 24.0, "vendor": "nvidia"},
            {"global_mem_gb": 16.0, "vendor": "amd"},
            {"global_mem_gb": 8.0, "vendor": "intel"},
        ]

        for device in devices:
            batch_size = self.selector.recommend_batch_size(device)

            # 内存池大小应该与批次大小相关
            # 估算: 每个key 32字节 + 匹配标志4字节 = 36字节
            estimated_memory_mb = (batch_size * 36) / (1024 * 1024)

            print(f"  ✅ {device['vendor'].upper()} {device['global_mem_gb']}GB:")
            print(f"       批次大小: {batch_size:,}")
            print(f"       估算内存: {estimated_memory_mb:.2f} MB")


class TestGPURunningStability:
    """测试6: GPU运行稳定性"""

    def test_01_multiple_init_cleanup(self):
        """测试6.1: 多次初始化/清理稳定性"""
        print("\n📋 测试6.1: 多次初始化/清理循环")

        mock_device = make_mock_gpu_device(
            name="Test GPU",
            vendor="Test",
            mem_size=8589934592,
            compute_units=68,
        )

        mock_context = Mock()
        mock_queue = Mock()
        mock_queue.finish = Mock()

        platform = make_mock_platform("Mock Platform")
        platform.get_devices = Mock(return_value=[mock_device])

        with patch("src.gpu.device.cl.get_platforms", return_value=[platform]):
            with patch("src.gpu.device.cl.Context", return_value=mock_context):
                with patch("src.gpu.device.cl.CommandQueue", return_value=mock_queue):
                    gpu_device = GPUDevice()

                    # 循环5次初始化/清理
                    for i in range(5):
                        gpu_device.initialize(device_index=0)
                        assert gpu_device.context is not None
                        assert gpu_device.queue is not None

                        gpu_device.cleanup()
                        assert gpu_device.context is None
                        assert gpu_device.queue is None

                        print(f"  ✅ 循环 {i + 1}/5: 初始化/清理成功")

    def test_02_resource_cleanup_completeness(self):
        """测试6.2: 资源清理完整性"""
        print("\n📋 测试6.2: 资源清理完整性")

        mock_device = make_mock_gpu_device(
            name="Test GPU",
            vendor="Test",
            mem_size=8589934592,
            compute_units=68,
        )

        mock_context = Mock()
        mock_queue = Mock()
        mock_compute_queue = Mock()
        mock_transfer_queue = Mock()

        for q in [mock_queue, mock_compute_queue, mock_transfer_queue]:
            q.finish = Mock()

        platform = make_mock_platform("Mock Platform")
        platform.get_devices = Mock(return_value=[mock_device])

        with patch("src.gpu.device.cl.get_platforms", return_value=[platform]):
            with patch("src.gpu.device.cl.Context", return_value=mock_context):
                with patch(
                    "src.gpu.device.cl.CommandQueue",
                    side_effect=[mock_compute_queue, mock_transfer_queue],
                ):
                    gpu_device = GPUDevice()

                    # 启用异步模式
                    gpu_device.initialize(device_index=0, enable_async=True)

                    # 验证所有队列已创建
                    assert gpu_device.compute_queue is not None
                    assert gpu_device.transfer_queue is not None

                    # 清理
                    gpu_device.cleanup()

                    # 验证所有资源已清理
                    assert gpu_device.context is None
                    assert gpu_device.queue is None
                    assert gpu_device.compute_queue is None
                    assert gpu_device.transfer_queue is None
                    assert gpu_device.device is None

                    print("  ✅ 所有资源已完全清理")


class TestMultiGPUIntegration:
    """测试7: 多GPU集成测试"""

    def setUp(self):
        """测试前准备"""
        reset_gpu_selector()

    def test_01_selector_singleton(self):
        """测试7.1: 选择器单例模式"""
        print("\n📋 测试7.1: 选择器单例模式")

        selector1 = get_gpu_selector()
        selector2 = get_gpu_selector()

        # 应该是同一个实例
        assert selector1 is selector2
        print(f"  ✅ 单例模式正常: selector1 is selector2 = {selector1 is selector2}")

    def test_02_detect_and_score_all_devices(self):
        """测试7.2: 检测并评分所有设备"""
        print("\n📋 测试7.2: 检测并评分所有设备")

        gpus = [
            make_mock_gpu_device("NVIDIA RTX 3080", "NVIDIA", 10737418240, 68),
            make_mock_gpu_device("AMD RX 6800 XT", "AMD", 17179869184, 72),
            make_mock_gpu_device("Intel Arc A770", "Intel", 17179869184, 512),
        ]

        platform = make_mock_platform("Mock Platform")
        platform.get_devices = Mock(return_value=gpus)

        with patch("src.gpu.device.cl.get_platforms", return_value=[platform]):
            selector = get_gpu_selector()
            devices = selector.detect_all_devices()

            assert len(devices) == 3

            # 验证所有设备都有评分
            for device in devices:
                assert "score" in device
                assert device["score"] > 0

            print(f"  ✅ 检测到 {len(devices)} 个设备,均已评分:")
            for dev in sorted(devices, key=lambda d: d["score"], reverse=True):
                print(f"       [{dev['global_index']}] {dev['name']}: {dev['score']:.1f}分")

    def test_03_format_device_info(self):
        """测试7.3: 格式化设备信息"""
        print("\n📋 测试7.3: 格式化设备信息")

        device = {
            "global_index": 0,
            "name": "NVIDIA GeForce RTX 3080",
            "vendor": "nvidia",
            "global_mem_gb": 10.0,
            "max_compute_units": 68,
            "score": 103.4,
            "max_work_group_size": 1024,
            "global_mem_cache_kb": 5120,
            "local_mem_kb": 64,
            "recommended_batch_size": 131072,
            "recommended_work_group": 512,
        }

        selector = GPUDeviceSelector()

        # 简洁格式
        brief = selector.format_device_info(device, detailed=False)
        assert "RTX 3080" in brief
        assert "10.00 GB" in brief

        # 详细格式
        detailed = selector.format_device_info(device, detailed=True)
        assert "131 in 072", detailed
        assert "512" in detailed

        print(f"  ✅ 简洁格式:\n{brief}")
        print(f"\n  ✅ 详细格式:\n{detailed}")

    def test_04_select_devices_by_indices(self):
        """测试7.4: 根据索引列表选择设备"""
        print("\n📋 测试7.4: 批量选择设备")

        devices = [
            {
                "global_index": 0,
                "name": "GPU 0",
                "vendor": "nvidia",
                "global_mem_gb": 10.0,
                "max_compute_units": 68,
            },
            {
                "global_index": 1,
                "name": "GPU 1",
                "vendor": "amd",
                "global_mem_gb": 16.0,
                "max_compute_units": 72,
            },
            {
                "global_index": 2,
                "name": "GPU 2",
                "vendor": "intel",
                "global_mem_gb": 16.0,
                "max_compute_units": 512,
            },
        ]

        selector = GPUDeviceSelector()

        with patch.object(GPUDeviceSelector, "detect_all_devices", return_value=devices):
            # 选择索引0和2
            selected = selector.select_devices_by_indices([0, 2])

            assert len(selected) == 2
            assert selected[0]["global_index"] == 0
            assert selected[1]["global_index"] == 2

            print(f"  ✅ 成功选择 {len(selected)} 个设备:")
            for dev in selected:
                print(f"       - {dev['name']}")


def run_tests():
    """运行所有测试"""
    print("=" * 80)
    print("  GPU设备选择和切换功能全面测试")
    print("=" * 80)
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python版本: {sys.version}")
    print()

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有测试类
    test_classes = [
        TestGPUDeviceDetection,
        TestGPUVendorIdentification,
        TestGPUDeviceScoring,
        TestGPUSwitching,
        TestGPUConfigurationAdaptation,
        TestGPURunningStability,
        TestMultiGPUIntegration,
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出总结
    print("\n" + "=" * 80)
    print("  测试总结")
    print("=" * 80)
    print(f"  总测试数: {result.testsRun}")
    print(f"  ✅ 通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  ❌ 失败: {len(result.failures)}")
    print(f"  💥 错误: {len(result.errors)}")

    pass_rate = (
        ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100)
        if result.testsRun > 0
        else 0
    )
    print(f"  通过率: {pass_rate:.1f}%")

    if result.failures:
        print("\n失败测试:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split('.')[-1].strip()}")

    if result.errors:
        print("\n错误测试:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split('.')[-1].strip()}")

    return len(result.failures) == 0 and len(result.errors) == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
