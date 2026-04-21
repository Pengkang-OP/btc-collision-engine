#!/usr/bin/env python3
"""Pytest配置文件 - 提供全局Fixture和测试配置

本文件包含:
- GPU引擎测试的统一Mock链Fixture
- Mock验证辅助函数
- 测试环境配置

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
"""
import pytest
from unittest.mock import Mock, patch
from contextlib import ExitStack


# ============================================================================
# 公共Mock创建函数 (减少代码重复)
# ============================================================================

def _create_mock_gpu_objects(batch_size=65536, vendor='nvidia', 
                              device_name='Test GPU', 
                              vendor_str='NVIDIA Corporation',
                              global_mem_size=8 * 1024**3):
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
        'name': device_name,
        'vendor': vendor_str,
        'global_mem_size': global_mem_size
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


def _apply_gpu_patches(mock_device, mock_context, mock_kernel, vendor='nvidia'):
    """应用7层GPU Mock链(内部辅助函数)
    
    Args:
        mock_device: GPU设备Mock
        mock_context: GPU上下文Mock
        mock_kernel: GPU内核Mock
        vendor: 厂商标识
    
    Returns:
        contextmanager: 上下文管理器
    """
    from contextlib import contextmanager
    
    @contextmanager
    def _patch_context():
        with ExitStack() as stack:
            # 应用7层Mock
            stack.enter_context(patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', True))
            stack.enter_context(patch('src.collision.gpu_collision_engine.GPUDeviceDetector.is_gpu_available', return_value=True))
            stack.enter_context(patch('src.collision.gpu_collision_engine.GPUDevice', return_value=mock_device))
            stack.enter_context(patch('src.collision.gpu_collision_engine.GPUContext', return_value=mock_context))
            stack.enter_context(patch('src.collision.gpu_collision_engine.GPUKernel', return_value=mock_kernel))
            mock_profile_loader = stack.enter_context(
                patch('src.collision.gpu_collision_engine.GPUProfileLoader')
            )
            stack.enter_context(patch('src.gpu.device.identify_vendor', return_value=vendor))
            
            # 配置ProfileLoader返回None(使用默认配置)
            mock_profile_loader.return_value.get_profile.return_value = None
            
            yield mock_device, mock_context, mock_kernel
    
    return _patch_context()


# ============================================================================
# Mock验证辅助函数
# ============================================================================

class MockAssertions:
    """Mock断言辅助类
    
    提供常用的Mock验证方法,简化测试代码
    
    使用示例:
        def test_engine(self, mock_gpu_chain):
            mock_device, mock_context, mock_kernel = mock_gpu_chain
            # ... 测试代码 ...
            MockAssertions.assert_cleanup_called(mock_device, mock_context, mock_kernel)
    """
    
    @staticmethod
    def assert_cleanup_called(mock_device, mock_context, mock_kernel):
        """验证GPU资源清理是否正确调用"""
        mock_kernel.cleanup.assert_called_once()
        mock_context.cleanup.assert_called_once()
        mock_device.cleanup.assert_called_once()
    
    @staticmethod
    def assert_kernel_executed(mock_kernel, min_calls=1):
        """验证GPU内核执行批次调用
        
        Args:
            mock_kernel: GPU内核Mock
            min_calls: 最小调用次数
        """
        assert mock_kernel.run_batch.call_count >= min_calls, \
            f"GPU内核执行次数{mock_kernel.run_batch.call_count} < {min_calls}"
    
    @staticmethod
    def assert_targets_set(mock_kernel, expected_count):
        """验证目标地址设置
        
        Args:
            mock_kernel: GPU内核Mock
            expected_count: 期望的目标地址数量
        """
        mock_kernel.set_targets.assert_called_once()
        call_args = mock_kernel.set_targets.call_args
        assert call_args[0][1] == expected_count, \
            f"目标地址数量{call_args[0][1]} != {expected_count}"
    
    @staticmethod
    def assert_engine_running(engine):
        """验证引擎正在运行"""
        assert engine.is_running() is True
    
    @staticmethod
    def assert_engine_stopped(engine):
        """验证引擎已停止"""
        assert engine.is_running() is False


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
    
    与mock_gpu_chain类似,但允许指定batch_size
    
    使用示例:
        def test_custom_batch(mock_gpu_chain_custom_batch):
            mock_device, mock_context, mock_kernel = mock_gpu_chain_custom_batch(1000)
            # 测试代码...
    """
    def _create_chain(batch_size=65536):
        # 使用公共函数创建Mock对象
        mock_device, mock_context, mock_kernel = _create_mock_gpu_objects(batch_size=batch_size)
        
        # 应用7层Mock链
        with _apply_gpu_patches(mock_device, mock_context, mock_kernel) as mocks:
            yield mocks
    
    return _create_chain


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
        'name': 'Test GPU',
        'vendor': 'NVIDIA Corporation',
        'global_mem_size': 8 * 1024**3
    }
    mock_device.initialize = Mock()
    mock_device.get_device_info = Mock(return_value=mock_device.device_info)
    mock_device.cleanup = Mock()
    
    yield mock_device


@pytest.fixture
def clear_gpu_detector_cache():
    """清除GPUDeviceDetector的所有缓存
    
    用于需要重新检测GPU的测试
    
    使用示例:
        def test_gpu_detection(clear_gpu_detector_cache):
            # 缓存已清除,可以重新检测
            pass
    """
    from src.gpu.device import GPUDeviceDetector
    
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
        vendor='amd',
        device_name='Radeon RX 6800',
        vendor_str='AMD',
        global_mem_size=16 * 1024**3  # 16GB显存
    )
    
    with _apply_gpu_patches(mock_device, mock_context, mock_kernel, vendor='amd') as mocks:
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
        vendor='intel',
        device_name='Intel Arc A770',
        vendor_str='Intel Corporation',
        global_mem_size=16 * 1024**3  # 16GB显存
    )
    
    # Intel特殊配置
    mock_kernel.use_uint32_workaround = True
    mock_kernel.enable_async_execution = False
    
    with _apply_gpu_patches(mock_device, mock_context, mock_kernel, vendor='intel') as mocks:
        yield mocks
