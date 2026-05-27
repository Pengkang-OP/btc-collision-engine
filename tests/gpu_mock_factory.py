#!/usr/bin/env python3
"""GPU Mock 测试基础设施 - 统一的 Mock 工厂.

提供标准化、可复用的 GPU Mock 对象，覆盖所有 GPU 测试场景：
- OpenCL 设备 / 平台 / 上下文
- GPU Buffer / Program / Kernel
- GPUDevice / GPUContext 包装对象
- pyopencl 模块级 patch 辅助
"""

from contextlib import contextmanager
from typing import Any
from unittest.mock import Mock, patch

import pytest

pytestmark = pytest.mark.gpu

# ---------------------------------------------------------------------------
# OpenCL 常量（优先从真实 pyopencl 读取，不可用时用字面量兜底）
# ---------------------------------------------------------------------------
try:
    import pyopencl as _cl
    import pyopencl as cl

    _CL_DEVICE_TYPE = _cl.device_info.TYPE
    _CL_DEVICE_NAME = _cl.device_info.NAME
    _CL_DEVICE_VENDOR = _cl.device_info.VENDOR
    _CL_DEVICE_TYPE_GPU = _cl.device_type.GPU
    _CL_DEVICE_TYPE_CPU = _cl.device_type.CPU
    _CL_PLATFORM_NAME = _cl.platform_info.NAME
    _PYOPENCL_AVAILABLE = True
    HAS_PYOPENCL = True
except ImportError:
    cl = None
    _CL_DEVICE_TYPE = 0x1000
    _CL_DEVICE_NAME = 0x1001
    _CL_DEVICE_VENDOR = 0x1002
    _CL_DEVICE_TYPE_GPU = 0x4
    _CL_DEVICE_TYPE_CPU = 0x2
    _CL_PLATFORM_NAME = 0x0900
    _PYOPENCL_AVAILABLE = False
    HAS_PYOPENCL = False

# ---------------------------------------------------------------------------
# 预置设备配置（方便测试直接引用）
# ---------------------------------------------------------------------------
PRESET_NVIDIA = dict(
    name="NVIDIA GeForce RTX 3080",
    vendor="NVIDIA Corporation",
    mem_size=8 * 1024**3,
    compute_units=68,
)

PRESET_AMD = dict(
    name="AMD Radeon RX 6800 XT",
    vendor="Advanced Micro Devices, Inc.",
    mem_size=16 * 1024**3,
    compute_units=72,
)

PRESET_INTEL_ARC = dict(
    name="Intel(R) Arc(TM) A770 Graphics",
    vendor="Intel Corporation",
    mem_size=16 * 1024**3,
    compute_units=512,
)

PRESET_INTEL_UHD = dict(
    name="Intel(R) UHD Graphics 630",
    vendor="Intel Corporation",
    mem_size=8 * 1024**3,
    compute_units=24,
)

PRESET_CPU = dict(
    name="Intel(R) Core(TM) i7-10700K",
    vendor="Intel(R) Corporation",
    mem_size=32 * 1024**3,
    compute_units=16,
    device_type=_CL_DEVICE_TYPE_CPU,
)


# ---------------------------------------------------------------------------
# GPUMockFactory
# ---------------------------------------------------------------------------
class GPUMockFactory:
    """提供标准化的 GPU Mock 对象，供所有 GPU 测试文件复用。."""

    # ------------------------------------------------------------------
    # OpenCL 底层 Mock
    # ------------------------------------------------------------------

    @staticmethod
    def create_cl_device(
        name: str = "Mock GPU",
        vendor: str = "Mock Vendor",
        mem_size: int = 8 * 1024**3,
        compute_units: int = 32,
        device_type: int = _CL_DEVICE_TYPE_GPU,
    ) -> Mock:
        """创建标准 Mock OpenCL 设备（cl.Device 替代品）。.

        设备属性同时作为直接属性 *和* ``get_info()`` 响应暴露，
        兼容不同源码读取方式。

        Args:
            name:          设备名称
            vendor:        厂商名称
            mem_size:      全局显存大小（字节）
            compute_units: 计算单元数量
            device_type:   设备类型常量（默认 GPU）

        Returns:
            配置好的 Mock 对象

        """
        device = Mock()

        # 直接属性访问（src.gpu.device 部分代码路径）
        device.type = device_type
        device.name = name
        device.vendor = vendor
        device.global_mem_size = mem_size
        device.max_compute_units = compute_units

        # get_info() 响应真实 cl.device_info 常量
        _info_map: dict[int, Any] = {
            _CL_DEVICE_TYPE: device_type,
            _CL_DEVICE_NAME: name,
            _CL_DEVICE_VENDOR: vendor,
        }

        def _get_info(key):
            return _info_map.get(key, Mock())

        device.get_info = _get_info
        return device

    @staticmethod
    def create_cl_platform(
        name: str = "Mock Platform",
        devices: list[Mock] | None = None,
    ) -> Mock:
        """创建标准 Mock OpenCL 平台（cl.Platform 替代品）。.

        Args:
            name:    平台名称
            devices: 该平台上的设备列表（为 None 时自动创建一个默认 GPU 设备）

        Returns:
            配置好的 Mock 平台对象

        """
        if devices is None:
            devices = [GPUMockFactory.create_cl_device()]

        platform = Mock()
        platform.name = name
        platform.get_devices = Mock(return_value=devices)
        platform.get_info = Mock(return_value=name)
        return platform

    @staticmethod
    def create_cl_context(device: Mock | None = None) -> Mock:
        """创建标准 Mock OpenCL 上下文（cl.Context 替代品）。.

        Args:
            device: 绑定的设备（为 None 时自动创建）

        Returns:
            配置好的 Mock 上下文对象

        """
        if device is None:
            device = GPUMockFactory.create_cl_device()

        ctx = Mock(spec=cl.Context) if HAS_PYOPENCL else Mock()
        ctx.devices = [device]
        ctx.get_info = Mock(return_value=Mock())
        return ctx

    @staticmethod
    def create_cl_buffer(size: int = 1024) -> Mock:
        """创建标准 Mock OpenCL Buffer（cl.Buffer 替代品）。.

        重要: pyopencl.Buffer 的构造函数签名为:
            Buffer(context, flags, size=0, hostbuf=None)

        因此 Mock 必须能够接受这些参数并返回有效的 Mock 对象。

        Args:
            size: 缓冲区大小（字节，仅用于元数据）

        Returns:
            配置好的 Mock Buffer 对象

        """
        buf = Mock(spec=cl.Buffer) if HAS_PYOPENCL else Mock()
        buf.size = size

        # 关键修复: Buffer 构造函数需要正确处理参数
        # 当代码调用 cl.Buffer(context, flags, hostbuf=...) 时
        # Mock 必须能够接受这些位置参数和关键字参数
        buf_constructor = Mock(return_value=buf)  # noqa: F841

        return buf

    @staticmethod
    def create_cl_queue(context: Mock | None = None) -> Mock:
        """创建标准 Mock OpenCL 命令队列（cl.CommandQueue 替代品）。."""
        queue = Mock()
        queue.context = context or GPUMockFactory.create_cl_context()
        queue.finish = Mock()
        queue.flush = Mock()
        return queue

    @staticmethod
    def create_cl_program(build_success: bool = True) -> Mock:
        """创建标准 Mock OpenCL Program。.

        Args:
            build_success: 若为 False，``build()`` 将抛出 ``Exception``

        Returns:
            配置好的 Mock Program 对象

        """
        prog = Mock()
        if build_success:
            prog.build = Mock(return_value=Mock())
        else:
            prog.build = Mock(side_effect=Exception("compile error: mock build failure"))
        return prog

    # ------------------------------------------------------------------
    # 高层 GPU 包装对象 Mock
    # ------------------------------------------------------------------

    @staticmethod
    def create_gpu_device(
        name: str = "Mock GPU",
        vendor: str = "Mock Vendor",
        mem_size: int = 8 * 1024**3,
    ) -> Mock:
        """创建标准 Mock ``GPUDevice`` 包装对象。.

        该对象模拟 ``src.collision.gpu_collision_engine.GPUDevice``
        或 ``src.gpu.device.GPUDevice`` 的公开接口。

        Args:
            name:     设备名称
            vendor:   厂商名称
            mem_size: 全局显存大小（字节）

        Returns:
            配置好的 Mock GPUDevice 对象

        """
        device_info = {
            "name": name,
            "vendor": vendor,
            "global_mem_size": mem_size,
        }

        device = Mock()
        device.context = Mock()
        device.queue = Mock()
        device.device_info = device_info

        # 方法接口
        device.initialize = Mock()
        device.get_device_info = Mock(return_value=device_info)
        device.cleanup = Mock()

        # 性能相关属性（部分路径会做数值运算，需为 float/int）
        device.memory_efficiency = 0.85
        device.compute_efficiency = 0.90

        return device

    @staticmethod
    def create_gpu_context(batch_size: int = 100) -> Mock:
        """创建标准 Mock ``GPUContext`` 包装对象。.

        Args:
            batch_size: ``calculate_batch_size()`` 的返回值

        Returns:
            配置好的 Mock GPUContext 对象

        """
        ctx = Mock()
        ctx.program = Mock()
        ctx.apply_optimizations = Mock()
        ctx.calculate_batch_size = Mock(return_value=batch_size)
        ctx.compile_kernel = Mock()
        ctx.cleanup = Mock()
        return ctx

    @staticmethod
    def create_gpu_kernel(
        batch_size: int = 100,
        run_batch_result=None,
        run_batch_side_effect=None,
    ) -> Mock:
        """创建标准 Mock ``GPUKernel`` 包装对象。.

        Args:
            batch_size:            ``max_batch_size`` 属性值
            run_batch_result:      ``run_batch_async`` 的返回值（默认 ``([], 1.0)``）
            run_batch_side_effect: ``run_batch_async`` 的副作用（优先于 result）

        Returns:
            配置好的 Mock GPUKernel 对象

        """
        if run_batch_result is None:
            run_batch_result = ([], 1.0)

        kernel = Mock()
        kernel.max_batch_size = batch_size
        kernel.set_targets = Mock()
        kernel.cleanup = Mock()
        kernel.gpu_optimizer = Mock()
        kernel.gpu_optimizer.analyze_and_adjust = Mock(return_value=(batch_size, {}))

        # run_batch 同步接口（_execute_gpu_batch 使用）
        kernel.run_batch = Mock(return_value=[])

        if run_batch_side_effect is not None:
            kernel.run_batch_async = Mock(side_effect=run_batch_side_effect)
        else:
            kernel.run_batch_async = Mock(return_value=run_batch_result)

        return kernel

    # ------------------------------------------------------------------
    # pyopencl 模块级 Mock
    # ------------------------------------------------------------------

    @staticmethod
    def create_mock_cl_module() -> Mock:
        """创建完整的 Mock ``pyopencl`` 模块。.

        包含 ``device_type``、``device_info``、``platform_info``、
        ``command_queue_properties`` 等常量类，以及常用函数桩。

        Returns:
            配置好的 Mock cl 模块对象

        """
        mock_cl = Mock()

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
            NAME = 0x0900

        class command_queue_properties:
            PROFILING_ENABLE = 0x1

        class mem_flags:
            READ_ONLY = 0x0001
            READ_WRITE = 0x0002
            WRITE_ONLY = 0x0004
            COPY_HOST_PTR = 0x0010

        mock_cl.device_type = device_type
        mock_cl.device_info = device_info
        mock_cl.platform_info = platform_info
        mock_cl.command_queue_properties = command_queue_properties
        mock_cl.mem_flags = mem_flags

        # 常用异常类型
        mock_cl.Error = Exception
        mock_cl.MemoryError = MemoryError
        mock_cl.RuntimeError = RuntimeError

        # 关键修复: pyopencl.Buffer 的 Mock 必须正确处理构造函数签名
        # Buffer(context, flags, size=0, hostbuf=None)
        mock_buffer_instance = Mock()
        mock_buffer_instance.size = 1024
        mock_cl.Buffer = Mock(return_value=mock_buffer_instance)

        # 常用函数桩（可被测试用例覆盖）
        mock_cl.get_platforms = Mock(return_value=[])
        mock_cl.Program = Mock(return_value=GPUMockFactory.create_cl_program())
        mock_cl.CommandQueue = Mock(return_value=GPUMockFactory.create_cl_queue())
        mock_cl.Context = Mock(return_value=GPUMockFactory.create_cl_context())

        return mock_cl

    # ------------------------------------------------------------------
    # 便捷的 patch 上下文管理器
    # ------------------------------------------------------------------

    @staticmethod
    @contextmanager
    def patch_pyopencl_buffer():
        """对 ``pyopencl.Buffer`` 打 patch，避免真实 OpenCL 调用。.

        用法::

            with GPUMockFactory.patch_pyopencl_buffer() as mock_buf:
                ...  # mock_buf 是 Buffer 的 Mock 返回值
        """
        mock_buf = Mock()
        with patch("pyopencl.Buffer", return_value=mock_buf):
            yield mock_buf

    @staticmethod
    @contextmanager
    def patch_gpu_collision_engine(
        batch_size: int = 100,
        run_batch_side_effect=None,
    ):
        """一站式 patch GPUCollisionEngine 所需的全部依赖。.

        同时 patch：
        - ``PYOPENCL_AVAILABLE`` → True
        - ``GPUDevice``          → Mock GPUDevice
        - ``GPUContext``         → Mock GPUContext
        - ``GPUKernel``          → Mock GPUKernel
        - ``GPUProfileLoader``   → Mock（get_profile 返回 None）
        - ``pyopencl.Buffer``    → Mock Buffer
        - ``AsyncGPUExecutor.initialize_buffers``
        - ``AsyncGPUExecutor.run_batch_async``（可指定副作用）

        用法::

            with GPUMockFactory.patch_gpu_collision_engine() as mocks:
                engine = GPUCollisionEngine(targets, batch_size=100)
                engine.start(mode="random")
        """
        mock_device = GPUMockFactory.create_gpu_device()
        mock_context = GPUMockFactory.create_gpu_context(batch_size)
        mock_kernel = GPUMockFactory.create_gpu_kernel(
            batch_size=batch_size,
            run_batch_side_effect=run_batch_side_effect,
        )
        mock_buffer = GPUMockFactory.create_cl_buffer()

        with (
            patch("src.gpu._availability.PYOPENCL_AVAILABLE", True),
            patch("src.gpu.device_manager.GPUDevice", return_value=mock_device),
            patch("src.gpu.device_manager.GPUContext", return_value=mock_context),
            patch("src.gpu.device_manager.GPUKernel", return_value=mock_kernel),
            patch("src.gpu.device_manager.GPUProfileLoader") as mock_loader,
            patch("pyopencl.Buffer", return_value=mock_buffer),
            patch("src.gpu.async_executor.AsyncGPUExecutor.initialize_buffers"),
            patch(
                "src.gpu.async_executor.AsyncGPUExecutor.run_batch_async",
                side_effect=mock_kernel.run_batch_async.side_effect,
                return_value=(
                    mock_kernel.run_batch_async.return_value if run_batch_side_effect is None else None
                ),
            ),
        ):
            mock_loader.return_value.get_profile.return_value = None

            yield {
                "device": mock_device,
                "context": mock_context,
                "kernel": mock_kernel,
                "buffer": mock_buffer,
                "loader": mock_loader,
            }

    # ------------------------------------------------------------------
    # 预置场景快捷方法
    # ------------------------------------------------------------------

    @classmethod
    def nvidia_device(cls) -> Mock:
        """返回预置的 NVIDIA RTX 3080 Mock 设备（cl.Device 级别）。."""
        return cls.create_cl_device(**PRESET_NVIDIA)

    @classmethod
    def amd_device(cls) -> Mock:
        """返回预置的 AMD RX 6800 XT Mock 设备（cl.Device 级别）。."""
        return cls.create_cl_device(**PRESET_AMD)

    @classmethod
    def intel_arc_device(cls) -> Mock:
        """返回预置的 Intel Arc A770 Mock 设备（cl.Device 级别）。."""
        return cls.create_cl_device(**PRESET_INTEL_ARC)

    @classmethod
    def intel_uhd_device(cls) -> Mock:
        """返回预置的 Intel UHD 630 核显 Mock 设备（cl.Device 级别）。."""
        return cls.create_cl_device(**PRESET_INTEL_UHD)

    @classmethod
    def cpu_device(cls) -> Mock:
        """返回预置的 CPU Mock 设备（cl.Device 级别，type=CPU）。."""
        p = dict(PRESET_CPU)
        device_type = p.pop("device_type")
        return cls.create_cl_device(**p, device_type=device_type)

    @classmethod
    def multi_vendor_platforms(cls) -> list[Mock]:
        """返回包含 NVIDIA / AMD / Intel Arc 三种设备的多平台列表。."""
        platform1 = cls.create_cl_platform("Platform NVIDIA", [cls.nvidia_device()])
        platform2 = cls.create_cl_platform(
            "Platform AMD-Intel",
            [cls.amd_device(), cls.intel_arc_device()],
        )
        return [platform1, platform2]
