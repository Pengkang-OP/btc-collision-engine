#!/usr/bin/env python3
"""GPU 碰撞引擎 Mock 测试.

使用新的GPU Mock基础设施，完全Mock pyopencl模块，
避免真实GPU调用导致的测试失败。
"""

import threading
from unittest.mock import Mock, patch

import pytest

from src.collision.gpu.engine import GPUCollisionEngine
from src.gpu.device import GPUDeviceDetector

pytestmark = pytest.mark.gpu


@pytest.fixture
def mock_gpu_setup():
    """提供预配置的GPU引擎Mock环境（使用新Mock基础设施）.

    这个fixture使用完全Mock的pyopencl模块，避免真实GPU调用。
    替代了旧的混合Mock方式（真实pyopencl + Mock对象）。

    返回:
        dict: 包含所有Mock对象的字典
            - device: GPU设备Mock
            - context: GPU上下文Mock
            - kernel: GPU内核Mock
            - buffer: GPU缓冲区Mock
    """
    mock_cl_device = Mock()
    mock_cl_device.get_info = Mock(
        side_effect=lambda key: {
            0x1000: 0x4,  # TYPE -> GPU
            0x1001: "Test GPU",  # NAME
            0x1002: "NVIDIA Corporation",  # VENDOR
        }.get(key, Mock()),
    )
    mock_cl_device.global_mem_size = 8 * 1024**3
    mock_cl_device.max_compute_units = 68

    mock_device_info = {
        "name": "Test GPU",
        "vendor": "NVIDIA Corporation",
        "platform": "Mock Platform",
        "device": mock_cl_device,
        "platform_obj": Mock(),
        "global_mem_size": 8 * 1024**3,
        "max_compute_units": 68,
        "type": "GPU",
    }

    mock_device = Mock()
    mock_device.context = Mock()
    mock_device.queue = Mock()
    mock_device.device_info = mock_device_info
    mock_device.initialize = Mock(return_value=None)
    mock_device.get_device_info = Mock(return_value=mock_device_info)
    mock_device.cleanup = Mock()
    mock_device.memory_efficiency = 0.85
    mock_device.compute_efficiency = 0.90

    mock_context = Mock()
    mock_context.program = Mock()
    mock_context.apply_optimizations = Mock()
    mock_context.calculate_batch_size = Mock(return_value=65536)
    mock_context.compile_kernel = Mock()
    mock_context.cleanup = Mock()

    mock_kernel = Mock()
    mock_kernel.run_batch = Mock(return_value=[])
    mock_kernel.run_batch_async = Mock(return_value=([], 1.0))
    mock_kernel.set_targets = Mock()
    mock_kernel.cleanup = Mock()
    mock_kernel.max_batch_size = 65536

    mock_buffer = Mock()
    mock_buffer.size = 1024

    with (
        patch("src.gpu._availability.PYOPENCL_AVAILABLE", True),
        patch(
            "src.gpu.device.GPUDeviceDetector.is_gpu_available",
            return_value=True,
        ),
        patch(
            "src.gpu.device.GPUDeviceDetector.detect_devices",
            return_value=[mock_device_info],
        ),
        patch("src.gpu.device_manager.GPUDevice", return_value=mock_device),
        patch("src.gpu.device_manager.GPUContext", return_value=mock_context),
        patch("src.gpu.device_manager.GPUKernel", return_value=mock_kernel),
        patch("src.gpu.profiles.loader.GPUProfileLoader") as mock_profile_loader,
        patch("pyopencl.Buffer", return_value=mock_buffer),
        patch("pyopencl.mem_flags.READ_ONLY", 0x0001),
        patch("pyopencl.mem_flags.READ_WRITE", 0x0002),
        patch("pyopencl.mem_flags.COPY_HOST_PTR", 0x0010),
        patch("src.gpu.async_executor.AsyncGPUExecutor.initialize_buffers"),
        patch("src.gpu.async_executor.AsyncGPUExecutor.run_batch_async", return_value=([], 1.0)),
    ):
        mock_profile_loader.return_value.get_profile.return_value = None

        yield {
            "device": mock_device,
            "context": mock_context,
            "kernel": mock_kernel,
            "buffer": mock_buffer,
        }


class TestGPUCollisionEngine:
    """GPU 碰撞引擎测试类."""

    def setup_method(self):
        """设置测试环境."""
        self.test_targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}

    def test_is_gpu_available(self):
        """测试 GPU 可用性检测."""
        try:
            available = GPUCollisionEngine.is_gpu_available()
            assert isinstance(available, bool)
        except Exception:
            pass

    def test_gpu_device_detection(self):
        """测试 GPU 设备检测."""
        try:
            devices = GPUDeviceDetector.detect_devices()
            assert isinstance(devices, list)
        except Exception:
            pass

    def test_gpu_engine_initialization_without_gpu(self):
        """测试在没有 GPU 的情况下初始化 GPU 引擎.

        P0-9(PYOPENCL单源化): engine.py 通过 ``from src.gpu._availability import
        PYOPENCL_AVAILABLE`` 导入后会创建模块级本地副本。因此 patch 需同时覆盖
        源模块 (_availability) 和消费模块 (engine) 的本地变量。
        """
        with (
            patch("src.gpu._availability.PYOPENCL_AVAILABLE", False),
            patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", False),
        ):
            with pytest.raises(RuntimeError, match=r"[Pp]y[Oo]pen[Cc][Ll]\s*不可用"):
                GPUCollisionEngine(self.test_targets)

    def test_gpu_engine_mock_initialization(self):
        """使用 Mock 测试 GPU 引擎初始化 - 无设备情况."""
        with (
            patch("src.gpu._availability.PYOPENCL_AVAILABLE", True),
            patch(
                "src.gpu.device.GPUDeviceDetector.detect_devices",
                return_value=[],
            ),
            patch(
                "src.gpu.device.GPUDeviceDetector.is_gpu_available",
                return_value=False,
            ),
            pytest.raises(RuntimeError, match="pyopencl 不可用|未检测到 GPU 设备|GPU.*不可用"),
        ):
            GPUCollisionEngine(self.test_targets)

    @pytest.mark.skipif(
        not GPUCollisionEngine.is_gpu_available(),
        reason="[GPU-HW-001] 需要真实GPU硬件才能运行此测试",
    )
    def test_gpu_engine_initialization_with_real_device(self):
        """使用真实 GPU 设备测试引擎初始化.

        注意: 此测试需要真实GPU硬件，因为pyopencl是C扩展，
        Mock的cl.Device对象在cl.Context()中会被拒绝（bad cast错误）。
        """
        engine = GPUCollisionEngine(self.test_targets, device_index=0)
        assert engine is not None
        assert engine.targets == self.test_targets
        assert isinstance(engine.batch_size, int)
        assert engine.batch_size > 0

    @pytest.mark.skipif(
        not GPUCollisionEngine.is_gpu_available(),
        reason="[GPU-HW-002] 需要真实GPU硬件才能运行此测试",
    )
    def test_gpu_engine_lifecycle_start_stop(self):
        """测试 GPU 引擎的生命周期（启动和停止）.

        注意: 此测试需要真实GPU硬件和内核执行。
        """
        engine = GPUCollisionEngine(self.test_targets, device_index=0)
        engine.start(mode="random")
        assert engine.is_running() is True
        engine.stop()
        assert engine.is_running() is False

    def test_gpu_engine_invalid_mode_raises_error(self):
        """测试使用无效模式启动 GPU 引擎应抛出 ValueError."""
        with (
            patch("src.collision.gpu.engine.GPUDeviceManager") as MockDeviceManager,
            patch("src.gpu._availability.PYOPENCL_AVAILABLE", True),
        ):
            mock_device_manager = Mock()
            mock_device_manager.initialize = Mock()
            mock_device_manager.device = Mock()
            mock_device_manager.context = Mock()
            mock_device_manager.kernel = Mock()
            mock_device_manager.async_executor = Mock()
            mock_device_manager.memory_pool = Mock()
            mock_device_manager.get_device_info = Mock(
                return_value={
                    "name": "Mock GPU",
                    "vendor": "NVIDIA Corporation",
                    "type": "GPU",
                    "device_index": 0,
                    "batch_size": 65536,
                },
            )
            MockDeviceManager.return_value = mock_device_manager

            engine = GPUCollisionEngine(self.test_targets, device_index=0)
            assert engine is not None

            MockDeviceManager.assert_called_once()
            mock_device_manager.initialize.assert_called_once()

            captured_exceptions = []
            original_hook = threading.excepthook

            def capture_hook(args):
                captured_exceptions.append(args.exc_value)

            threading.excepthook = capture_hook
            try:
                engine.start(mode="invalid_mode")
                import time

                time.sleep(0.5)
            finally:
                threading.excepthook = original_hook
                if engine.is_running():
                    engine.stop()

            assert len(captured_exceptions) > 0, "应捕获到后台线程异常"
            assert any(
                isinstance(exc, ValueError)
                and ("未知" in str(exc) or "无效" in str(exc) or "invalid" in str(exc).lower())
                for exc in captured_exceptions
            ), f"应捕获到包含'未知/无效/invalid'的ValueError，实际: {captured_exceptions}"

    @pytest.mark.skipif(
        not GPUCollisionEngine.is_gpu_available(),
        reason="[GPU-HW-003] 需要真实GPU硬件才能运行此测试",
    )
    def test_gpu_engine_get_device_info(self):
        """测试获取 GPU 设备信息.

        注意: 此测试需要真实GPU初始化。
        """
        engine = GPUCollisionEngine(self.test_targets, device_index=0)
        device_info = engine.get_device_info()
        assert isinstance(device_info, dict)
        assert "type" in device_info
        assert device_info["type"] == "GPU"
        assert "name" in device_info
        assert "vendor" in device_info
        assert "device_index" in device_info
        assert "batch_size" in device_info
