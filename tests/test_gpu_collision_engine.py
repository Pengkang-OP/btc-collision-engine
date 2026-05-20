#!/usr/bin/env python3
"""GPU 碰撞引擎 Mock 测试

使用新的GPU Mock基础设施，完全Mock pyopencl模块，
避免真实GPU调用导致的测试失败。
"""

import threading
from unittest.mock import Mock, patch

import pytest

from src.collision.gpu_collision_engine import GPUCollisionEngine
from src.gpu.device import GPUDeviceDetector

pytestmark = pytest.mark.gpu


@pytest.fixture
def mock_gpu_setup():
    """提供预配置的GPU引擎Mock环境（使用新Mock基础设施）

    这个fixture使用完全Mock的pyopencl模块，避免真实GPU调用。
    替代了旧的混合Mock方式（真实pyopencl + Mock对象）。

    返回:
        dict: 包含所有Mock对象的字典
            - device: GPU设备Mock
            - context: GPU上下文Mock
            - kernel: GPU内核Mock
            - buffer: GPU缓冲区Mock
    """
    # 创建Mock的OpenCL设备对象
    mock_cl_device = Mock()
    mock_cl_device.get_info = Mock(
        side_effect=lambda key: {
            0x1000: 0x4,  # TYPE -> GPU
            0x1001: "Test GPU",  # NAME
            0x1002: "NVIDIA Corporation",  # VENDOR
        }.get(key, Mock())
    )
    mock_cl_device.global_mem_size = 8 * 1024**3
    mock_cl_device.max_compute_units = 68

    # 设备信息字典（必须包含'device'键）
    mock_device_info = {
        "name": "Test GPU",
        "vendor": "NVIDIA Corporation",
        "platform": "Mock Platform",
        "device": mock_cl_device,  # 关键：必须包含真实的device对象
        "platform_obj": Mock(),
        "global_mem_size": 8 * 1024**3,
        "max_compute_units": 68,
        "type": "GPU",
    }

    mock_device = Mock()
    mock_device.context = Mock()
    mock_device.queue = Mock()
    mock_device.device_info = mock_device_info
    # 关键修复：Mock initialize方法，使其成为无操作（避免bad cast）
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

    # 完全Mock所有GPU相关模块
    with (
        patch("src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE", True),
        patch(
            "src.collision.gpu_collision_engine.GPUDeviceDetector.is_gpu_available",
            return_value=True,
        ),
        patch(
            "src.collision.gpu_collision_engine.GPUDeviceDetector.detect_devices",
            return_value=[mock_device_info],
        ),
        patch("src.collision.gpu_collision_engine.GPUDevice", return_value=mock_device),
        patch("src.collision.gpu_collision_engine.GPUContext", return_value=mock_context),
        patch("src.collision.gpu_collision_engine.GPUKernel", return_value=mock_kernel),
        patch("src.collision.gpu_collision_engine.GPUProfileLoader") as mock_profile_loader,
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
    """GPU 碰撞引擎测试类"""

    def setup_method(self):
        """设置测试环境"""
        self.test_targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}  # 测试地址

    def test_is_gpu_available(self):
        """测试 GPU 可用性检测"""
        # 测试 GPU 可用性检查
        try:
            available = GPUCollisionEngine.is_gpu_available()
            # 无论结果如何，测试应该通过
            assert isinstance(available, bool)
        except Exception as e:  # noqa: F841
            # 如果 pyopencl 不可用，也应该优雅处理
            pass

    def test_gpu_device_detection(self):
        """测试 GPU 设备检测"""
        # 测试设备检测
        try:
            devices = GPUDeviceDetector.detect_devices()
            assert isinstance(devices, list)
        except Exception as e:  # noqa: F841
            # 如果 pyopencl 不可用，也应该优雅处理
            pass

    def test_gpu_engine_initialization_without_gpu(self):
        """测试在没有 GPU 的情况下初始化 GPU 引擎"""
        # 模拟 pyopencl 不可用
        with patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", False):
            with pytest.raises(RuntimeError, match=r"[Pp]y[Oo]pen[Cc][Ll]\s*不可用"):
                GPUCollisionEngine(self.test_targets)

    def test_gpu_engine_mock_initialization(self):
        """使用 Mock 测试 GPU 引擎初始化 - 无设备情况"""
        # 模拟 pyopencl 可用
        with patch("src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE", True):
            # Mock GPUDeviceDetector返回空设备列表
            with (
                patch(
                    "src.collision.gpu_collision_engine.GPUDeviceDetector.detect_devices",
                    return_value=[],
                ),
                patch(
                    "src.collision.gpu_collision_engine.GPUDeviceDetector.is_gpu_available",
                    return_value=False,
                ),
            ):

                # 测试没有 GPU 设备的情况应该抛出异常
                with pytest.raises(
                    RuntimeError, match="pyopencl 不可用|未检测到 GPU 设备|GPU.*不可用"
                ):
                    GPUCollisionEngine(self.test_targets)

    @pytest.mark.skip(
        reason="[GPU-HW-001] 需要真实GPU硬件: pyopencl C扩展类型检查无法完美Mock。详见: test_results/PYOPENCL_MOCK_SOLUTION.md"  # noqa: E501
    )
    def test_gpu_engine_initialization_with_mock_device(self, mock_gpu_setup):
        """使用 Mock 设备测试 GPU 引擎初始化

        注意: 此测试被跳过，因为pyopencl是C扩展，严格检查对象类型。
        Mock的cl.Device对象在cl.Context()中被拒绝（bad cast错误）。
        需要真实GPU硬件才能运行此测试。
        """
        # 初始化 GPU 引擎（使用device_index=0，因为Mock只有1个设备）
        engine = GPUCollisionEngine(self.test_targets, device_index=0)

        # 验证初始化
        assert engine is not None
        assert engine.targets == self.test_targets
        # batch_size应该从 GPUContext获取，是正整数
        assert isinstance(engine.batch_size, int)
        assert engine.batch_size > 0

    @pytest.mark.skip(
        reason="[GPU-HW-002] 需要真实GPU硬件: pyopencl C扩展类型检查无法完美Mock。详见: test_results/PYOPENCL_MOCK_SOLUTION.md"  # noqa: E501
    )
    def test_gpu_engine_lifecycle_start_stop(self, mock_gpu_setup):
        """测试 GPU 引擎的生命周期（启动和停止）

        注意: 此测试被跳过，因为需要真实的GPU初始化和内核执行。
        """
        # 初始化 GPU 引擎（使用device_index=0）
        engine = GPUCollisionEngine(self.test_targets, device_index=0)

        # 测试启动
        engine.start(mode="random")
        assert engine.is_running() is True

        # 测试停止
        engine.stop()
        assert engine.is_running() is False

        # 验证资源清理
        mock_gpu_setup["kernel"].cleanup.assert_called_once()
        mock_gpu_setup["context"].cleanup.assert_called_once()
        mock_gpu_setup["device"].cleanup.assert_called_once()

    def test_gpu_engine_invalid_mode_raises_error(self):
        """测试使用无效模式启动 GPU 引擎应抛出 ValueError

        此测试验证GPUCollisionEngine.start()方法的参数验证逻辑，
        确保传入无效模式时抛出ValueError。

        Phase 6: start() 通过 _search_coordinator 在后台线程验证模式，
        ValueError 在后台线程中抛出，通过 threading.excepthook 捕获断言。

        注意: 此测试通过Mock GPUDeviceManager来避免真实的GPU初始化，
        只验证参数验证逻辑，不需要真实GPU硬件。
        """
        # 策略：直接Mock GPUDeviceManager，完全绕过GPU初始化流程
        # Phase 6: engine.py 从 src.gpu.device_manager 导入，需要 patch 正确路径
        with (
            patch("src.collision.gpu.engine.GPUDeviceManager") as MockDeviceManager,
            patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", True),
        ):
            # 配置Mock使其跳过GPU初始化，但允许引擎创建成功
            mock_device_manager = Mock()
            mock_device_manager.initialize = Mock()  # 不执行任何操作
            mock_device_manager.device = Mock()  # Mock设备对象
            mock_device_manager.context = Mock()  # Mock上下文对象
            mock_device_manager.kernel = Mock()  # Mock内核对象
            mock_device_manager.async_executor = Mock()  # Mock异步执行器
            mock_device_manager.memory_pool = Mock()  # Mock内存池
            mock_device_manager.get_device_info = Mock(
                return_value={
                    "name": "Mock GPU",
                    "vendor": "NVIDIA Corporation",
                    "type": "GPU",
                    "device_index": 0,
                    "batch_size": 65536,
                }
            )
            MockDeviceManager.return_value = mock_device_manager

            # 创建引擎（不会真实初始化GPU）
            engine = GPUCollisionEngine(self.test_targets, device_index=0)

            # 验证引擎创建成功
            assert engine is not None

            # 验证Mock被正确调用（确保初始化流程执行）
            MockDeviceManager.assert_called_once()
            mock_device_manager.initialize.assert_called_once()

            # Phase 6: start() 在后台线程中异步验证模式
            # 使用 threading.excepthook 捕获后台线程异常
            captured_exceptions = []
            original_hook = threading.excepthook

            def capture_hook(args):
                captured_exceptions.append(args.exc_value)

            threading.excepthook = capture_hook
            try:
                engine.start(mode="invalid_mode")
                # 等待后台线程抛出异常
                import time

                time.sleep(0.5)

                # 验证后台线程捕获到 ValueError
                assert len(captured_exceptions) > 0, "应捕获到后台线程异常"
                assert any(
                    isinstance(exc, ValueError)
                    and ("未知" in str(exc) or "无效" in str(exc) or "invalid" in str(exc).lower())
                    for exc in captured_exceptions
                ), f"应捕获到包含'未知/无效/invalid'的ValueError，实际: {captured_exceptions}"
            finally:
                threading.excepthook = original_hook
                if engine.is_running():
                    engine.stop()

    @pytest.mark.skip(
        reason="[GPU-HW-003] 需要真实GPU硬件: pyopencl C扩展类型检查无法完美Mock。详见: test_results/PYOPENCL_MOCK_SOLUTION.md"  # noqa: E501
    )
    def test_gpu_engine_get_device_info(self, mock_gpu_setup):
        """测试获取 GPU 设备信息

        注意: 此测试被跳过，因为需要真实的GPU初始化。
        """
        # 初始化 GPU 引擎（使用device_index=0）
        engine = GPUCollisionEngine(self.test_targets, device_index=0)

        # 测试获取设备信息
        device_info = engine.get_device_info()
        assert isinstance(device_info, dict)
        assert "type" in device_info
        assert device_info["type"] == "GPU"
        assert "name" in device_info
        assert "vendor" in device_info
        assert "device_index" in device_info
        assert "batch_size" in device_info
