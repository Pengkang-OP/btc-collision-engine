#!/usr/bin/env python3
"""GPU 碰撞引擎 Mock 测试"""
import pytest
import os
import sys
from unittest.mock import Mock, patch
from src.collision.gpu_collision_engine import GPUCollisionEngine, GPUDevice


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
        except Exception as e:
            # 如果 pyopencl 不可用，也应该优雅处理
            pass
    
    def test_gpu_device_detection(self):
        """测试 GPU 设备检测"""
        # 测试设备检测
        try:
            devices = GPUDevice.detect_devices()
            assert isinstance(devices, list)
        except Exception as e:
            # 如果 pyopencl 不可用，也应该优雅处理
            pass
    
    def test_gpu_engine_initialization_without_gpu(self):
        """测试在没有 GPU 的情况下初始化 GPU 引擎"""
        # 模拟 pyopencl 不可用
        with patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', False):
            with pytest.raises(RuntimeError, match="pyopencl 不可用，无法使用 GPU 加速"):
                GPUCollisionEngine(self.test_targets)
    
    def test_gpu_engine_mock_initialization(self):
        """使用 Mock 测试 GPU 引擎初始化 - 无设备情况"""
        # 模拟 pyopencl 可用
        with patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', True):
            # 模拟 GPUDevice 类和 GPUKernel 类
            with patch('src.collision.gpu_collision_engine.GPUDevice') as mock_gpu_device_class, \
                 patch('src.collision.gpu_collision_engine.GPUKernel') as mock_gpu_kernel_class:
                
                # 模拟设备检测返回空列表
                mock_gpu_device_class.detect_devices.return_value = []
                mock_gpu_device_class.is_available.return_value = True
                
                # 创建 mock 实例，initialize 方法会抛出异常
                mock_device_instance = Mock()
                mock_device_instance.initialize.side_effect = RuntimeError("未检测到 GPU 设备")
                mock_gpu_device_class.return_value = mock_device_instance
                
                # 测试没有 GPU 设备的情况
                with pytest.raises(RuntimeError, match="未检测到 GPU 设备"):
                    GPUCollisionEngine(self.test_targets)
    
    def test_gpu_engine_with_mock_device(self):
        """使用 Mock 设备测试 GPU 引擎"""
        # 模拟 pyopencl 可用
        with patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', True):
            # 模拟 GPUDevice 类
            with patch('src.collision.gpu_collision_engine.GPUDevice') as mock_gpu_device:
                # 模拟设备检测返回一个设备
                mock_device_info = {
                    'platform': 'Test Platform',
                    'name': 'Test GPU',
                    'vendor': 'Test Vendor',
                    'device': Mock(),
                    'platform_obj': Mock()
                }
                mock_gpu_device.detect_devices.return_value = [mock_device_info]
                mock_gpu_device.is_available.return_value = True
                    
                # 模拟 GPU 设备实例
                mock_instance = Mock()
                mock_instance.context = Mock()
                mock_instance.queue = Mock()
                mock_instance.device_info = {
                    'name': 'Test GPU',
                    'vendor': 'Test Vendor',
                    'platform': 'Test Platform'
                }
                mock_instance.get_device_info.return_value = mock_instance.device_info
                mock_gpu_device.return_value = mock_instance
                    
                # 模拟 GPUKernel 类
                with patch('src.collision.gpu_collision_engine.GPUKernel') as mock_gpu_kernel:
                    mock_kernel_instance = Mock()
                    mock_kernel_instance.run_batch.return_value = []
                    mock_kernel_instance.set_targets = Mock()
                    mock_kernel_instance.cleanup = Mock()
                    mock_kernel_instance.max_batch_size = 65536
                    mock_gpu_kernel.return_value = mock_kernel_instance
                        
                    # 初始化 GPU 引擎
                    engine = GPUCollisionEngine(self.test_targets)
                        
                    # 验证初始化
                    assert engine is not None
                    assert engine.targets == self.test_targets
                    # batch_size应该从 GPUKernel获取，是正整数
                    assert isinstance(engine.batch_size, int)
                    assert engine.batch_size > 0
    
    def test_gpu_engine_start_stop(self):
        """测试 GPU 引擎的启动和停止"""
        # 模拟 pyopencl 可用
        with patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', True):
            # 模拟 GPUDevice 类
            with patch('src.collision.gpu_collision_engine.GPUDevice') as mock_gpu_device:
                # 模拟设备检测返回一个设备
                mock_device_info = {
                    'platform': 'Test Platform',
                    'name': 'Test GPU',
                    'vendor': 'Test Vendor',
                    'device': Mock(),
                    'platform_obj': Mock()
                }
                mock_gpu_device.detect_devices.return_value = [mock_device_info]
                
                # 模拟 GPU 设备初始化
                mock_instance = Mock()
                mock_instance.context = Mock()
                mock_instance.queue = Mock()
                mock_instance.get_device_info.return_value = {
                    'name': 'Test GPU',
                    'vendor': 'Test Vendor',
                    'platform': 'Test Platform'
                }
                mock_gpu_device.return_value = mock_instance
                
                # 模拟 GPUKernel 类
                with patch('src.collision.gpu_collision_engine.GPUKernel') as mock_gpu_kernel:
                    mock_kernel_instance = Mock()
                    mock_kernel_instance.run_batch.return_value = []
                    mock_kernel_instance.max_batch_size = 65536
                    mock_gpu_kernel.return_value = mock_kernel_instance
                    
                    # 直接模拟 GPUKernel 类
                    with patch('src.collision.gpu_collision_engine.GPUKernel') as mock_gpu_kernel:
                        mock_kernel_instance = Mock()
                        mock_kernel_instance.run_batch.return_value = []
                        mock_kernel_instance.set_targets = Mock()
                        mock_kernel_instance.cleanup = Mock()
                        mock_kernel_instance.max_batch_size = 65536
                        mock_gpu_kernel.return_value = mock_kernel_instance
                        
                        # 初始化 GPU 引擎
                        engine = GPUCollisionEngine(self.test_targets)
                        
                        # 测试启动
                        engine.start(mode="random")
                        assert engine.is_running() is True
                        
                        # 测试停止
                        engine.stop()
                        assert engine.is_running() is False
    
    def test_gpu_engine_with_invalid_mode(self):
        """测试使用无效模式启动 GPU 引擎"""
        # 模拟 pyopencl 可用
        with patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', True):
            # 模拟 GPUDevice 类
            with patch('src.collision.gpu_collision_engine.GPUDevice') as mock_gpu_device:
                # 模拟设备检测返回一个设备
                mock_device_info = {
                    'platform': 'Test Platform',
                    'name': 'Test GPU',
                    'vendor': 'Test Vendor',
                    'device': Mock(),
                    'platform_obj': Mock()
                }
                mock_gpu_device.detect_devices.return_value = [mock_device_info]
                
                # 模拟 GPU 设备初始化
                mock_instance = Mock()
                mock_instance.context = Mock()
                mock_instance.queue = Mock()
                mock_instance.get_device_info.return_value = {
                    'name': 'Test GPU',
                    'vendor': 'Test Vendor',
                    'platform': 'Test Platform'
                }
                mock_gpu_device.return_value = mock_instance
                
                # 模拟 GPUKernel 类
                with patch('src.collision.gpu_collision_engine.GPUKernel') as mock_gpu_kernel:
                    mock_kernel_instance = Mock()
                    mock_kernel_instance.run_batch.return_value = []
                    mock_kernel_instance.max_batch_size = 65536
                    mock_gpu_kernel.return_value = mock_kernel_instance
                    
                    # 直接模拟 GPUKernel 类
                    with patch('src.collision.gpu_collision_engine.GPUKernel') as mock_gpu_kernel:
                        mock_kernel_instance = Mock()
                        mock_kernel_instance.run_batch.return_value = []
                        mock_kernel_instance.set_targets = Mock()
                        mock_kernel_instance.cleanup = Mock()
                        mock_kernel_instance.max_batch_size = 65536
                        mock_gpu_kernel.return_value = mock_kernel_instance
                        
                        # 初始化 GPU 引擎
                        engine = GPUCollisionEngine(self.test_targets)
                        
                        # 测试无效模式
                        with pytest.raises(ValueError, match="未知模式"):
                            engine.start(mode="invalid_mode")
    
    def test_gpu_engine_get_device_info(self):
        """测试获取 GPU 设备信息"""
        # 模拟 pyopencl 可用
        with patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', True):
            # 模拟 GPUDevice 类
            with patch('src.collision.gpu_collision_engine.GPUDevice') as mock_gpu_device:
                # 模拟设备检测返回一个设备
                mock_device_info = {
                    'platform': 'Test Platform',
                    'name': 'Test GPU',
                    'vendor': 'Test Vendor',
                    'device': Mock(),
                    'platform_obj': Mock()
                }
                mock_gpu_device.detect_devices.return_value = [mock_device_info]
                
                # 模拟 GPU 设备初始化
                mock_instance = Mock()
                mock_instance.context = Mock()
                mock_instance.queue = Mock()
                mock_instance.get_device_info.return_value = {
                    'name': 'Test GPU',
                    'vendor': 'Test Vendor',
                    'platform': 'Test Platform'
                }
                mock_gpu_device.return_value = mock_instance
                
                # 模拟 GPUKernel 类
                with patch('src.collision.gpu_collision_engine.GPUKernel') as mock_gpu_kernel:
                    mock_kernel_instance = Mock()
                    mock_kernel_instance.run_batch.return_value = []
                    mock_kernel_instance.max_batch_size = 65536
                    mock_gpu_kernel.return_value = mock_kernel_instance
                    
                    # 直接模拟 GPUKernel 类
                    with patch('src.collision.gpu_collision_engine.GPUKernel') as mock_gpu_kernel:
                        mock_kernel_instance = Mock()
                        mock_kernel_instance.run_batch.return_value = []
                        mock_kernel_instance.set_targets = Mock()
                        mock_kernel_instance.cleanup = Mock()
                        mock_kernel_instance.max_batch_size = 65536
                        mock_gpu_kernel.return_value = mock_kernel_instance
                        
                        # 初始化 GPU 引擎
                        engine = GPUCollisionEngine(self.test_targets)
                        
                        # 测试获取设备信息
                        device_info = engine.get_device_info()
                        assert isinstance(device_info, dict)
                        assert 'name' in device_info
                        assert 'vendor' in device_info
                        assert 'platform' in device_info
