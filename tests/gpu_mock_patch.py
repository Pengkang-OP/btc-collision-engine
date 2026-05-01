#!/usr/bin/env python3
"""GPU测试Mock修复补丁

修复归档测试中 pyopencl.Buffer Mock 不兼容问题。

问题根因:
    pyopencl.Buffer 构造函数签名: Buffer(context, flags, size=0, hostbuf=None)
    旧的Mock方式无法正确处理位置参数和关键字参数的组合。

解决方案:
    使用正确的patch策略，确保cl.Buffer能够接受任意参数组合。
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tests.gpu_mock_factory import GPUMockFactory  # noqa: E402


def patch_pyopencl_buffer_for_test(test_func):
    """装饰器: 为测试函数添加pyopencl.Buffer的正确Mock

    用法:
        @patch_pyopencl_buffer_for_test
        def test_my_gpu_function(self):
            ...
    """

    def wrapper(*args, **kwargs):
        # 创建正确的Mock对象
        mock_buffer = Mock()
        mock_buffer.size = 1024

        # 关键: Mock必须能够接受任意参数组合
        mock_buffer_class = Mock(return_value=mock_buffer)

        with patch("pyopencl.Buffer", mock_buffer_class):
            return test_func(*args, **kwargs)

    wrapper.__name__ = test_func.__name__
    return wrapper


@pytest.fixture
def mock_pyopencl_buffer():
    """Fixture: 提供正确的pyopencl.Buffer Mock

    用法:
        def test_something(self, mock_pyopencl_buffer):
            # mock_pyopencl_buffer 是 cl.Buffer 的Mock类
            # 调用 cl.Buffer(...) 会返回 mock_pyopencl_buffer.return_value
    """
    mock_buffer = Mock()
    mock_buffer.size = 1024

    mock_buffer_class = Mock(return_value=mock_buffer)

    with patch("pyopencl.Buffer", mock_buffer_class) as mock:
        yield mock


@pytest.fixture
def mock_pyopencl_full():
    """Fixture: 提供完整的pyopencl模块Mock

    包含:
        - cl.Buffer
        - cl.mem_flags (READ_ONLY, READ_WRITE, COPY_HOST_PTR)
        - cl.Context
        - cl.CommandQueue
        - cl.Program
    """
    mock_cl = GPUMockFactory.create_mock_cl_module()

    with patch.dict("sys.modules", {"pyopencl": mock_cl}):
        with patch("pyopencl.Buffer", mock_cl.Buffer):
            with patch("pyopencl.mem_flags", mock_cl.mem_flags):
                with patch("pyopencl.Context", mock_cl.Context):
                    with patch("pyopencl.CommandQueue", mock_cl.CommandQueue):
                        with patch("pyopencl.Program", mock_cl.Program):
                            yield mock_cl


@pytest.fixture
def mock_gpu_collision_engine_full():
    """Fixture: 一站式Mock GPUCollisionEngine的所有GPU依赖

    这是最完整的Mock，适用于测试GPU碰撞引擎初始化。
    """
    mock_device = GPUMockFactory.create_gpu_device()
    mock_context = GPUMockFactory.create_gpu_context()
    mock_kernel = GPUMockFactory.create_gpu_kernel()
    mock_buffer = GPUMockFactory.create_cl_buffer()

    # 确保Mock设备有必要的属性
    mock_device.memory_efficiency = 0.85
    mock_device.compute_efficiency = 0.90
    mock_device.get_device_info.return_value = {
        "name": "Mock GPU",
        "vendor": "Mock Vendor",
        "global_mem_size": 8 * 1024**3,
    }

    patches = [
        patch("src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE", True),
        patch(
            "src.collision.gpu_collision_engine.GPUDeviceDetector.is_gpu_available",
            return_value=True,
        ),
        patch("src.collision.gpu_collision_engine.GPUDevice", return_value=mock_device),
        patch("src.collision.gpu_collision_engine.GPUContext", return_value=mock_context),
        patch("src.collision.gpu_collision_engine.GPUKernel", return_value=mock_kernel),
        patch("pyopencl.Buffer", return_value=mock_buffer),
        patch("src.gpu.async_executor.AsyncGPUExecutor.initialize_buffers"),
        patch("src.gpu.async_executor.AsyncGPUExecutor.run_batch_async", return_value=([], 1.0)),
    ]

    # 进入所有patch上下文
    for p in patches:
        p.start()

    yield {
        "device": mock_device,
        "context": mock_context,
        "kernel": mock_kernel,
        "buffer": mock_buffer,
    }

    # 退出所有patch上下文
    for p in patches:
        p.stop()


def apply_buffer_patch():
    """全局应用Buffer补丁（用于pytest configure）

    在conftest.py中调用此函数可以为所有测试应用补丁。
    """
    mock_buffer = Mock()
    mock_buffer.size = 1024
    mock_buffer_class = Mock(return_value=mock_buffer)

    return patch("pyopencl.Buffer", mock_buffer_class)
