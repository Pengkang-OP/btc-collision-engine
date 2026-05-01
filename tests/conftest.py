#!/usr/bin/env python3
"""Pytest配置文件 - 提供全局Fixture和测试配置

本文件包含:
- GPU引擎测试的统一Mock链Fixture
- Mock验证辅助函数
- 测试环境配置
- pyopencl.Buffer全局修复

常见问题:
    Q1: 什么时候使用mock_gpu_chain,什么时候使用mock_gpu_device?
    A1:
        - mock_gpu_chain: 需要完整初始化GPUCollisionEngine时
        - mock_gpu_device: 只测试GPU设备相关逻辑,不需要引擎初始化

    Q2: 如何自定义Mock行为?
    A2:
        def test_custom_behavior(self, mock_gpu_chain):
            mock_device, mock_context, mock_kernel = mock_gpu_chain
            mock_kernel.run_batch = Mock(side_effect=RuntimeError("GPU Error"))
            # ...

    Q3: 测试失败提示"GPU初始化失败"?
    A3: 确保使用了mock_gpu_chain fixture,而不是手动Mock

    Q4: pyopencl.Buffer Mock报错怎么办?
    A4: 已全局修复,使用mock_gpu_chain或mock_pyopencl_buffer fixture即可
"""

import pytest
from unittest.mock import Mock, patch
from contextlib import ExitStack, contextmanager

# 导入GPU Mock修复补丁
from tests.gpu_mock_patch import (
    mock_pyopencl_buffer,
    mock_pyopencl_full,
    mock_gpu_collision_engine_full,
)

# ============================================================================
# GPU测试常量定义
# ============================================================================


class GPUConstants:
    """GPU测试相关常量

    集中管理GPU测试中的硬编码值,提高可维护性
    """

    # 显存大小
    DEFAULT_MEM_SIZE = 8 * 1024**3  # 8GB
    HIGH_MEM_SIZE = 16 * 1024**3  # 16GB
    ULTRA_MEM_SIZE = 32 * 1024**3  # 32GB

    # Batch Size
    DEFAULT_BATCH_SIZE = 65536
    MIN_BATCH_SIZE = 1024
    MAX_BATCH_SIZE = 1048576  # 1M

    # 厂商字符串
    VENDOR_NVIDIA = "NVIDIA Corporation"
    VENDOR_AMD = "AMD"
    VENDOR_INTEL = "Intel Corporation"

    # 设备名称
    DEVICE_NVIDIA = "Test GPU"
    DEVICE_AMD = "Radeon RX 6800"
    DEVICE_INTEL = "Intel Arc A770"


# ============================================================================
# 公共Mock创建函数 (减少代码重复)
# ============================================================================


def _create_mock_gpu_objects(
    batch_size=GPUConstants.DEFAULT_BATCH_SIZE,
    vendor="nvidia",
    device_name=GPUConstants.DEVICE_NVIDIA,
    vendor_str=GPUConstants.VENDOR_NVIDIA,
    global_mem_size=GPUConstants.DEFAULT_MEM_SIZE,
):
    """创建标准GPU Mock对象集(内部辅助函数)

    Args:
        batch_size: 批次大小
        vendor: 厂商标识 ('nvidia', 'amd', 'intel')
        device_name: 设备名称
        vendor_str: 厂商字符串
        global_mem_size: 显存大小(字节)

    Returns:
        tuple: (mock_device, mock_context, mock_kernel)
    """
    # 创建Mock GPU设备
    mock_device = Mock()
    mock_device.context = Mock()
    mock_device.queue = Mock()
    mock_device.device_info = {
        "name": device_name,
        "vendor": vendor_str,
        "global_mem_size": global_mem_size,
    }
    mock_device.initialize = Mock()
    mock_device.get_device_info = Mock(return_value=mock_device.device_info)
    mock_device.cleanup = Mock()

    # 创建Mock GPU上下文
    mock_context = Mock()
    mock_context.program = Mock()
    mock_context.apply_optimizations = Mock()
    mock_context.calculate_batch_size = Mock(return_value=batch_size)
    mock_context.compile_kernel = Mock()
    mock_context.cleanup = Mock()

    # 创建Mock GPU内核
    mock_kernel = Mock()
    mock_kernel.run_batch = Mock(return_value=[])
    mock_kernel.set_targets = Mock()
    mock_kernel.cleanup = Mock()
    mock_kernel.max_batch_size = batch_size
    mock_kernel.gpu_optimizer = Mock()
    mock_kernel.gpu_optimizer.analyze_and_adjust = Mock(return_value=(batch_size, {}))

    return mock_device, mock_context, mock_kernel


def _apply_gpu_patches(mock_device, mock_context, mock_kernel, vendor="nvidia"):
    """应用7层GPU Mock链(内部辅助函数)

    Args:
        mock_device: GPU设备Mock
        mock_context: GPU上下文Mock
        mock_kernel: GPU内核Mock
        vendor: 厂商标识

    Returns:
        contextmanager: 上下文管理器
    """

    @contextmanager
    def _patch_context():
        # F-1修复: 创建 Mock cl.Buffer，避免 pyopencl.Buffer 要求真实 Context
        mock_cl_buffer = Mock()
        mock_cl_module = Mock()
        mock_cl_module.Buffer = Mock(return_value=mock_cl_buffer)
        mock_cl_module.mem_flags = Mock()
        mock_cl_module.mem_flags.READ_WRITE = 1
        mock_cl_module.mem_flags.COPY_HOST_PTR = 2
        mock_cl_module.mem_flags.READ_ONLY = 4
        mock_cl_module.mem_flags.WRITE_ONLY = 8
        # 为 pyopencl.array 子模块创建 Mock，避免函数级 'import pyopencl.array as cl_array' 失败
        mock_cl_array = Mock()
        mock_cl_array.Array = Mock()

        with ExitStack() as stack:
            # 应用7层Mock
            stack.enter_context(
                patch("src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE", True)
            )
            stack.enter_context(
                patch(
                    "src.collision.gpu_collision_engine.GPUDeviceDetector.is_gpu_available",
                    return_value=True,
                )
            )
            stack.enter_context(
                patch("src.collision.gpu_collision_engine.GPUDevice", return_value=mock_device)
            )
            stack.enter_context(
                patch("src.collision.gpu_collision_engine.GPUContext", return_value=mock_context)
            )
            stack.enter_context(
                patch("src.collision.gpu_collision_engine.GPUKernel", return_value=mock_kernel)
            )
            mock_profile_loader = stack.enter_context(
                patch("src.collision.gpu_collision_engine.GPUProfileLoader")
            )
            stack.enter_context(patch("src.gpu.device.identify_vendor", return_value=vendor))
            # async_executor采用函数级导入，通过patch sys.modules使内部 import pyopencl as cl 使用Mock
            # 同时注入 pyopencl.array 子模块，避免 'import pyopencl.array as cl_array' 失败
            stack.enter_context(
                patch.dict(
                    "sys.modules",
                    {
                        "pyopencl": mock_cl_module,
                        "pyopencl.array": mock_cl_array,
                    },
                )
            )

            # 配置ProfileLoader返回None(使用默认配置)
            mock_profile_loader.return_value.get_profile.return_value = None

            yield mock_device, mock_context, mock_kernel

    return _patch_context()


# Mock验证辅助函数已从 tests.test_helpers 导入
# 如需使用: from tests.test_helpers import MockAssertions


# ============================================================================
# Fixture定义
# ============================================================================


@pytest.fixture
def mock_gpu_chain():
    """提供完整的GPU Mock链,用于GPU碰撞引擎测试

    这个fixture封装了7层Mock,避免在每个测试中重复编写:
    1. PYOPENCL_AVAILABLE
    2. GPUDeviceDetector.is_gpu_available
    3. GPUDevice
    4. GPUContext
    5. GPUKernel
    6. GPUProfileLoader
    7. identify_vendor

    使用示例:
        def test_gpu_engine(mock_gpu_chain):
            mock_device, mock_context, mock_kernel = mock_gpu_chain
            # 测试代码...

    Yields:
        tuple: (mock_device, mock_context, mock_kernel)
    """
    # 使用公共函数创建Mock对象
    mock_device, mock_context, mock_kernel = _create_mock_gpu_objects()

    # 应用7层Mock链
    with _apply_gpu_patches(mock_device, mock_context, mock_kernel) as mocks:
        yield mocks


@pytest.fixture
def mock_gpu_chain_custom_batch():
    """提供可自定义batch_size的GPU Mock链

    返回上下文管理器,需要使用with语句

    使用示例:
        def test_custom_batch(mock_gpu_chain_custom_batch):
            with mock_gpu_chain_custom_batch(1000) as mocks:
                mock_device, mock_context, mock_kernel = mocks
                # 测试代码...
    """

    def _create_chain(batch_size=GPUConstants.DEFAULT_BATCH_SIZE):
        mock_device, mock_context, mock_kernel = _create_mock_gpu_objects(batch_size=batch_size)
        return _apply_gpu_patches(mock_device, mock_context, mock_kernel)

    return _create_chain


@pytest.fixture
def mock_gpu_chain_with_batch():
    """提供可直接使用的自定义batch_size GPU Mock链

    与mock_gpu_chain_custom_batch不同,这个fixture直接yield mocks,
    不需要with语句,但需要参数化测试使用pytest.mark.parametrize

    使用示例:
        @pytest.mark.parametrize("batch_size", [100, 1000, 10000])
        def test_multiple_batches(mock_gpu_chain_with_batch, batch_size):
            mock_device, mock_context, mock_kernel = mock_gpu_chain_with_batch
            # mock_gpu_chain_with_batch会在每个参数值下重新创建
            # 需要在测试外部通过其他方式传入batch_size
            pass

    注意: 这个fixture使用默认batch_size,如需自定义请使用mock_gpu_chain_custom_batch
    """
    mock_device, mock_context, mock_kernel = _create_mock_gpu_objects()
    with _apply_gpu_patches(mock_device, mock_context, mock_kernel) as mocks:
        yield mocks


@pytest.fixture
def mock_gpu_device():
    """仅提供GPU设备Mock(不包含完整链)

    用于不需要完整引擎初始化的测试

    Yields:
        Mock: GPU设备实例
    """
    mock_device = Mock()
    mock_device.context = Mock()
    mock_device.queue = Mock()
    mock_device.device_info = {
        "name": GPUConstants.DEVICE_NVIDIA,
        "vendor": GPUConstants.VENDOR_NVIDIA,
        "global_mem_size": GPUConstants.DEFAULT_MEM_SIZE,
    }
    mock_device.initialize = Mock()
    mock_device.get_device_info = Mock(return_value=mock_device.device_info)
    mock_device.cleanup = Mock()

    yield mock_device


@pytest.fixture(scope="module")
def mock_gpu_device_module():
    """模块级别的GPU设备Mock(多个测试共享)

    ⚠️ 注意: 此fixture在模块内共享,不适合修改Mock状态的测试!

    适用场景:
        - 只读测试(不修改Mock返回值)
        - 性能测试(避免重复创建Mock)
        - 测试组(多个测试使用相同配置)

    不适用场景:
        - 需要自定义Mock行为的测试
        - 需要隔离的测试
        - 会修改Mock状态的测试

    使用示例:
        class TestGPUDeviceReadOnly:
            def test_device_info_1(self, mock_gpu_device_module):
                # 使用共享的Mock
                info = mock_gpu_device_module.get_device_info()
                assert info['name'] == 'Test GPU'

            def test_device_info_2(self, mock_gpu_device_module):
                # 同一个Mock实例
                info = mock_gpu_device_module.get_device_info()
                assert info['vendor'] == 'NVIDIA Corporation'

    Yields:
        Mock: GPU设备实例(模块内共享)
    """
    mock_device = Mock()
    mock_device.context = Mock()
    mock_device.queue = Mock()
    mock_device.device_info = {
        "name": GPUConstants.DEVICE_NVIDIA,
        "vendor": GPUConstants.VENDOR_NVIDIA,
        "global_mem_size": GPUConstants.DEFAULT_MEM_SIZE,
    }
    mock_device.initialize = Mock()
    mock_device.get_device_info = Mock(return_value=mock_device.device_info)
    mock_device.cleanup = Mock()

    yield mock_device


@pytest.fixture(scope="module")
def mock_gpu_chain_module():
    """模块级别的完整GPU Mock链

    ⚠️ 注意: 此fixture在模块内共享7层Mock链!

    适用场景:
        - 模块内多个测试使用相同Mock配置
        - 性能敏感测试(减少Mock创建开销)
        - 集成测试组

    不适用场景:
        - 需要自定义Mock行为的测试
        - 需要严格隔离的测试
        - 会修改Mock返回值的测试

    使用示例:
        class TestGPUEngineIntegration:
            def test_engine_init(self, mock_gpu_chain_module):
                mock_device, mock_context, mock_kernel = mock_gpu_chain_module
                engine = GPUCollisionEngine(targets)
                # 测试...

            def test_engine_start(self, mock_gpu_chain_module):
                # 同一个Mock实例
                mock_device, mock_context, mock_kernel = mock_gpu_chain_module
                # 测试...

    Yields:
        tuple: (mock_device, mock_context, mock_kernel)
    """
    mock_device, mock_context, mock_kernel = _create_mock_gpu_objects()
    with _apply_gpu_patches(mock_device, mock_context, mock_kernel) as mocks:
        yield mocks


@pytest.fixture
def clear_gpu_detector_cache():
    """清除GPUDeviceDetector的所有缓存

    ⚠️ 警告: 此fixture修改类级别缓存,不建议在并发测试中使用!

    当使用pytest-xdist进行并行测试时,多个测试进程可能同时修改
    类级别的缓存,导致测试不稳定。

    安全使用场景:
        - 顺序执行的测试
        - 单线程测试
        - 不需要并发隔离的测试

    不安全使用场景:
        - pytest -n auto (并行测试)
        - 多线程测试
        - 需要严格隔离的测试

    使用示例:
        def test_gpu_detection(clear_gpu_detector_cache):
            # 缓存已清除,可以重新检测
            pass

    替代方案:
        如果需要并发安全,请在测试中直接Mock GPUDeviceDetector:
        @patch('src.gpu.device.GPUDeviceDetector.is_gpu_available')
        def test_safe(mock_is_available):
            mock_is_available.return_value = True
    """
    import warnings
    from src.gpu.device import GPUDeviceDetector

    # 发出并发安全警告
    warnings.warn(
        "clear_gpu_detector_cache修改类级别缓存,不建议在并发测试中使用",
        RuntimeWarning,
        stacklevel=2,
    )

    # 保存原始缓存值
    old_availability = GPUDeviceDetector._availability_cache
    old_timestamp = GPUDeviceDetector._cache_timestamp
    old_devices = GPUDeviceDetector._devices_cache
    old_devices_timestamp = GPUDeviceDetector._devices_cache_timestamp

    # 清除缓存
    GPUDeviceDetector._availability_cache = None
    GPUDeviceDetector._cache_timestamp = 0
    GPUDeviceDetector._devices_cache = None
    GPUDeviceDetector._devices_cache_timestamp = 0

    yield

    # 恢复原始缓存(避免影响其他测试)
    GPUDeviceDetector._availability_cache = old_availability
    GPUDeviceDetector._cache_timestamp = old_timestamp
    GPUDeviceDetector._devices_cache = old_devices
    GPUDeviceDetector._devices_cache_timestamp = old_devices_timestamp


# ============================================================================
# 厂商预设Fixture
# ============================================================================


@pytest.fixture
def mock_gpu_chain_nvidia(mock_gpu_chain):
    """NVIDIA GPU预设(默认)

    使用示例:
        def test_nvidia_optimizations(mock_gpu_chain_nvidia):
            mock_device, mock_context, mock_kernel = mock_gpu_chain_nvidia
            # NVIDIA特定测试...
    """
    yield mock_gpu_chain


@pytest.fixture
def mock_gpu_chain_amd():
    """AMD GPU预设

    使用示例:
        def test_amd_optimizations(mock_gpu_chain_amd):
            mock_device, mock_context, mock_kernel = mock_gpu_chain_amd
            # AMD特定测试...
    """
    mock_device, mock_context, mock_kernel = _create_mock_gpu_objects(
        vendor="amd",
        device_name=GPUConstants.DEVICE_AMD,
        vendor_str=GPUConstants.VENDOR_AMD,
        global_mem_size=GPUConstants.HIGH_MEM_SIZE,  # 16GB显存
    )

    with _apply_gpu_patches(mock_device, mock_context, mock_kernel, vendor="amd") as mocks:
        yield mocks


@pytest.fixture
def mock_gpu_chain_intel():
    """Intel GPU预设(包含uint32 workaround)

    使用示例:
        def test_intel_workaround(mock_gpu_chain_intel):
            mock_device, mock_context, mock_kernel = mock_gpu_chain_intel
            # Intel特定测试...
    """
    mock_device, mock_context, mock_kernel = _create_mock_gpu_objects(
        vendor="intel",
        device_name=GPUConstants.DEVICE_INTEL,
        vendor_str=GPUConstants.VENDOR_INTEL,
        global_mem_size=GPUConstants.HIGH_MEM_SIZE,  # 16GB显存
    )

    # Intel特殊配置
    mock_kernel.use_uint32_workaround = True
    mock_kernel.enable_async_execution = False

    with _apply_gpu_patches(mock_device, mock_context, mock_kernel, vendor="intel") as mocks:
        yield mocks


# ============================================================================
# pytest配置钩子
# ============================================================================


def pytest_configure(config):
    """配置pytest环境,注册自定义marker"""
    # GPU测试相关marker
    config.addinivalue_line("markers", "gpu_hardware: 需要真实GPU硬件的测试")
    config.addinivalue_line("markers", "gpu_unit: GPU单元测试（可Mock）")
    config.addinivalue_line("markers", "gpu_integration: GPU集成测试")

    # 性能测试相关marker
    config.addinivalue_line("markers", "performance: 性能基准测试")
    config.addinivalue_line("markers", "benchmark: 基准测试")

    # 安全测试相关marker
    config.addinivalue_line("markers", "security: 安全合规测试")

    # 标记为预期失败的测试
    config.addinivalue_line("markers", "expected_failure: 已知问题,预期失败")

    # P2-7: 注册 timeout marker (由 pytest-timeout 插件提供)
    config.addinivalue_line("markers", "timeout: 测试超时时间(秒)")


def pytest_collection_modifyitems(config, items):
    """修改测试项集合

    根据marker对测试进行分类和排序

    P2-7: 为GPU标记测试添加超时配置 (90秒)
    """
    import os

    # 检查是否需要跳过 GPU 硬件测试
    # CI 环境可通过 BTC_SKIP_GPU_HW=1 强制跳过，否则自动检测 GPU 可用性
    skip_gpu_hw = os.environ.get("BTC_SKIP_GPU_HW", "") == "1"
    gpu_availability_checked = False

    # 为GPU测试添加超时标记
    gpu_timeout_marker = pytest.mark.timeout(90)
    for item in items:
        # 为需要GPU硬件的测试条件跳过（仅在无 GPU 或 CI 强制跳过时）
        if "gpu_hardware" in item.keywords:
            if skip_gpu_hw:
                item.add_marker(pytest.mark.skip(reason="[GPU-HW] BTC_SKIP_GPU_HW=1 强制跳过"))
            elif not gpu_availability_checked:
                gpu_availability_checked = True
                try:
                    from src.gpu.device import GPUDeviceDetector

                    if not GPUDeviceDetector.is_gpu_available():
                        skip_gpu_hw = True
                except (ImportError, Exception):
                    skip_gpu_hw = True
                if skip_gpu_hw:
                    item.add_marker(pytest.mark.skip(reason="[GPU-HW] 未检测到可用 GPU 设备"))
            elif skip_gpu_hw:
                item.add_marker(pytest.mark.skip(reason="[GPU-HW] 未检测到可用 GPU 设备"))
        # P2-7: GPU测试超时保护
        if any(m in item.keywords for m in ("gpu", "gpu_hardware", "gpu_unit", "gpu_integration")):
            item.add_marker(gpu_timeout_marker)


@pytest.fixture(autouse=True)
def reset_cli_output_singleton():
    """每个测试前重置 CLIOutput 单例，避免跨测试 sys.stdout 污染。

    问题背景：test_cli_advanced_features.py 等测试会替换 sys.stdout 为 StringIO，
    若 CLIOutput 单例在替换前已创建，其内部 Console 持有旧的 sys.stdout 引用，
    恢复时可能导致 I/O 操作已关闭文件的错误。
    """
    try:
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
    except ImportError:
        pass
    yield
    # teardown: 再次重置，确保下一个测试干净启动
    try:
        from src.cli.output import CLIOutput

        CLIOutput.reset_instance()
    except ImportError:
        pass
