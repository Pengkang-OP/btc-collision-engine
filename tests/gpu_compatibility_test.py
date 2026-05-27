#!/usr/bin/env python3
"""GPU兼容性测试脚本.

测试系统在不同厂商和型号的GPU上的兼容性和性能。
"""

from unittest.mock import Mock, patch

import pytest

pytestmark = [
    pytest.mark.gpu,
    pytest.mark.gpu_unit,
    pytest.mark.timeout(90),
]


@pytest.fixture
def mock_pyopencl():
    """Fixture to mock pyopencl module and GPUDeviceDetector.detect_devices."""
    mock_cl = Mock()

    # Create mock platform and device
    mock_platform = Mock()
    mock_platform.get_info.return_value = "Mock Platform"

    mock_device = Mock()
    mock_device.get_info.side_effect = lambda key: {
        0x1000: 0x4,  # TYPE: GPU
        0x1001: "NVIDIA GeForce RTX 3080",  # NAME
        0x1002: "NVIDIA Corporation",  # VENDOR
    }.get(key, Mock())
    mock_device.global_mem_size = 8 * 1024**3
    mock_device.max_compute_units = 68
    mock_device.max_work_group_size = 1024
    mock_device.local_mem_size = 16384

    mock_platform.get_devices.return_value = [mock_device]
    mock_cl.get_platforms.return_value = [mock_platform]

    class device_type:
        GPU = 0x4
        CPU = 0x2

    class device_info:
        TYPE = 0x1000
        NAME = 0x1001
        VENDOR = 0x1002
        VERSION = 0x1003
        OPENCL_C_VERSION = 0x1004

    class platform_info:
        NAME = 0x0900

    mock_cl.device_type = device_type
    mock_cl.device_info = device_info
    mock_cl.platform_info = platform_info

    return mock_cl


class TestGPUCompatibility:
    """GPU兼容性测试."""

    def test_gpu_device_detection(self, mock_pyopencl):
        """测试GPU设备检测功能."""
        # 先patch，再import
        with patch.dict("sys.modules", {"pyopencl": mock_pyopencl}):
            with patch("src.gpu._availability.PYOPENCL_AVAILABLE", True):
                # 清除已经可能已导入的模块，强制重新导入
                import sys

                for mod in list(sys.modules.keys()):
                    if mod.startswith("src.gpu"):
                        del sys.modules[mod]
                from src.gpu.device import GPUDeviceDetector, identify_gpu_model, identify_vendor

                devices = GPUDeviceDetector.detect_devices()
                assert len(devices) == 1
                device = devices[0]
                assert device["name"] == "NVIDIA GeForce RTX 3080"
                assert device["vendor"] == "NVIDIA Corporation"

                vendor = identify_vendor(device["name"], device["vendor"])
                assert vendor == "nvidia"

                model = identify_gpu_model(device["name"], vendor)
                assert model == "rtx30"

    @pytest.mark.usefixtures("mock_gpu_chain")
    def test_gpu_initialization(self, mock_gpu_chain):
        """测试GPU设备初始化."""
        from src.collision.gpu.engine import GPUCollisionEngine

        targets = {
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        }
        engine = GPUCollisionEngine(targets=targets, device_index=0, batch_size=8192)
        assert engine is not None
        engine.start(mode="random")
        assert engine.is_running()
        engine.stop()
        assert not engine.is_running()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
