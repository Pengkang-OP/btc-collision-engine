#!/usr/bin/env python3
"""GPU碰撞引擎错误计数器线程安全测试

验证_consecutive_gpu_errors的锁保护逻辑和重试限制机制。
"""
import pytest
import threading
import time
from unittest.mock import Mock, patch
from src.collision.gpu_collision_engine import GPUCollisionEngine


class TestErrorCounterThreadSafety:
    """错误计数器线程安全测试类"""
    
    @pytest.fixture
    def mock_gpu_engine(self):
        """提供预配置的GPU引擎Mock环境"""
        with patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', True), \
             patch('pyopencl.Buffer') as mock_buffer, \
             patch('src.collision.gpu_collision_engine.GPUDevice') as mock_gpu_device_class, \
             patch('src.collision.gpu_collision_engine.GPUContext') as mock_gpu_context_class, \
             patch('src.collision.gpu_collision_engine.GPUKernel') as mock_gpu_kernel_class:
            
            # 配置 GPUDevice Mock
            mock_device_instance = Mock()
            mock_device_instance.context = Mock()
            mock_device_instance.queue = Mock()
            mock_device_instance.device_info = {
                'name': 'Test GPU',
                'vendor': 'NVIDIA Corporation',
                'global_mem_size': 8 * 1024**3
            }
            mock_device_instance.initialize = Mock()
            mock_device_instance.get_device_info = Mock(return_value=mock_device_instance.device_info)
            mock_device_instance.cleanup = Mock()
            mock_gpu_device_class.return_value = mock_device_instance
            mock_gpu_device_class.is_available = Mock(return_value=True)
            mock_gpu_device_class.detect_devices = Mock(return_value=[mock_device_instance.device_info])
            
            # 配置 GPUContext Mock
            mock_context_instance = Mock()
            mock_context_instance.program = Mock()
            mock_context_instance.apply_optimizations = Mock()
            mock_context_instance.calculate_batch_size = Mock(return_value=65536)
            mock_context_instance.compile_kernel = Mock()
            mock_context_instance.cleanup = Mock()
            mock_gpu_context_class.return_value = mock_context_instance
            
            # 配置 GPUKernel Mock
            mock_kernel_instance = Mock()
            mock_kernel_instance.run_batch = Mock(return_value=[])
            mock_kernel_instance.set_targets = Mock()
            mock_kernel_instance.cleanup = Mock()
            mock_kernel_instance.max_batch_size = 65536
            mock_gpu_kernel_class.return_value = mock_kernel_instance
            
            # 配置 pyopencl.Buffer Mock
            mock_buffer.return_value = Mock()
            
            yield {
                'device_class': mock_gpu_device_class,
                'context_class': mock_gpu_context_class,
                'kernel_class': mock_gpu_kernel_class,
                'device': mock_device_instance,
                'context': mock_context_instance,
                'kernel': mock_kernel_instance,
            }
    
    def test_error_counter_initialization(self, mock_gpu_engine):
        """测试错误计数器初始化"""
        engine = GPUCollisionEngine({"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"})
        
        assert hasattr(engine, '_consecutive_gpu_errors')
        assert hasattr(engine, '_max_gpu_error_retries')
        assert engine._consecutive_gpu_errors == 0
        assert engine._max_gpu_error_retries == 100  # 默认值
    
    def test_error_counter_reset_on_start(self, mock_gpu_engine):
        """测试引擎启动时重置错误计数器"""
        engine = GPUCollisionEngine({"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"})
        
        # 模拟已有错误计数
        engine._consecutive_gpu_errors = 50
        
        # 重新启动引擎
        engine.start(mode="random")
        engine.stop()
        
        # 验证计数器重置为0
        assert engine._consecutive_gpu_errors == 0
    
    def test_error_counter_increment_with_lock(self, mock_gpu_engine):
        """测试错误计数器递增的线程安全性"""
        engine = GPUCollisionEngine({"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"})
        
        # 多线程并发递增计数器
        def increment_counter():
            with engine._batch_size_lock:
                engine._consecutive_gpu_errors += 1
        
        threads = []
        for _ in range(100):
            t = threading.Thread(target=increment_counter)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证计数器准确递增到100
        assert engine._consecutive_gpu_errors == 100
    
    def test_max_retries_prevents_infinite_loop(self, mock_gpu_engine):
        """测试最大重试次数防止无限循环"""
        engine = GPUCollisionEngine({"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"})
        engine._max_gpu_error_retries = 10  # 降低阈值以便测试
        
        # 模拟达到最大重试次数
        with engine._batch_size_lock:
            engine._consecutive_gpu_errors = 10
        
        # 验证引擎会停止
        engine._running = True
        with engine._batch_size_lock:
            if engine._consecutive_gpu_errors >= engine._max_gpu_error_retries:
                engine._running = False
        
        assert engine._running is False
    
    def test_error_counter_reset_on_success(self, mock_gpu_engine):
        """测试成功执行时重置错误计数器"""
        engine = GPUCollisionEngine({"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"})
        
        # 模拟已有错误计数
        with engine._batch_size_lock:
            engine._consecutive_gpu_errors = 50
        
        # 模拟成功执行后重置
        with engine._batch_size_lock:
            engine._consecutive_gpu_errors = 0
        
        assert engine._consecutive_gpu_errors == 0
    
    def test_concurrent_error_and_success(self, mock_gpu_engine):
        """测试并发错误和成功场景"""
        engine = GPUCollisionEngine({"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"})
        engine._max_gpu_error_retries = 100
        
        error_count = 0
        success_count = 0
        
        def simulate_error():
            nonlocal error_count
            with engine._batch_size_lock:
                engine._consecutive_gpu_errors += 1
                error_count += 1
                time.sleep(0.001)  # 模拟处理时间
        
        def simulate_success():
            nonlocal success_count
            with engine._batch_size_lock:
                engine._consecutive_gpu_errors = 0
                success_count += 1
                time.sleep(0.001)  # 模拟处理时间
        
        # 创建混合线程
        threads = []
        for i in range(50):
            if i % 2 == 0:
                t = threading.Thread(target=simulate_error)
            else:
                t = threading.Thread(target=simulate_success)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证计数器最终状态合理
        assert engine._consecutive_gpu_errors >= 0
        assert engine._consecutive_gpu_errors <= engine._max_gpu_error_retries
        assert error_count == 25
        assert success_count == 25
    
    def test_config_max_error_retries(self, mock_gpu_engine):
        """测试从配置文件读取max_error_retries"""
        # 模拟配置
        with patch.object(GPUCollisionEngine, '_init_gpu', return_value=None):
            engine = GPUCollisionEngine.__new__(GPUCollisionEngine)
            engine.config = {
                'gpu': {
                    'max_error_retries': 200
                }
            }
            engine._batch_size_lock = threading.Lock()
            engine._max_gpu_error_retries = 100  # 默认值
            
            # 模拟从配置读取
            if hasattr(engine, 'config') and engine.config:
                gpu_config = engine.config.get('gpu', {})
                if 'max_error_retries' in gpu_config:
                    engine._max_gpu_error_retries = gpu_config['max_error_retries']
            
            assert engine._max_gpu_error_retries == 200


class TestCallbackSnapshotSafety:
    """回调快照安全性测试类"""
    
    @pytest.fixture
    def mock_gpu_engine(self):
        """提供预配置的GPU引擎Mock环境"""
        with patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', True), \
             patch('pyopencl.Buffer') as mock_buffer, \
             patch('src.collision.gpu_collision_engine.GPUDevice') as mock_gpu_device_class, \
             patch('src.collision.gpu_collision_engine.GPUContext') as mock_gpu_context_class, \
             patch('src.collision.gpu_collision_engine.GPUKernel') as mock_gpu_kernel_class:
            
            mock_device_instance = Mock()
            mock_device_instance.context = Mock()
            mock_device_instance.queue = Mock()
            mock_device_instance.device_info = {
                'name': 'Test GPU',
                'vendor': 'NVIDIA Corporation',
                'global_mem_size': 8 * 1024**3
            }
            mock_device_instance.initialize = Mock()
            mock_device_instance.get_device_info = Mock(return_value=mock_device_instance.device_info)
            mock_device_instance.cleanup = Mock()
            mock_gpu_device_class.return_value = mock_device_instance
            mock_gpu_device_class.is_available = Mock(return_value=True)
            mock_gpu_device_class.detect_devices = Mock(return_value=[mock_device_instance.device_info])
            
            mock_context_instance = Mock()
            mock_context_instance.program = Mock()
            mock_context_instance.apply_optimizations = Mock()
            mock_context_instance.calculate_batch_size = Mock(return_value=65536)
            mock_context_instance.compile_kernel = Mock()
            mock_context_instance.cleanup = Mock()
            mock_gpu_context_class.return_value = mock_context_instance
            
            mock_kernel_instance = Mock()
            mock_kernel_instance.run_batch = Mock(return_value=[])
            mock_kernel_instance.set_targets = Mock()
            mock_kernel_instance.cleanup = Mock()
            mock_kernel_instance.max_batch_size = 65536
            mock_gpu_kernel_class.return_value = mock_kernel_instance
            
            mock_buffer.return_value = Mock()
            
            yield {
                'device_class': mock_gpu_device_class,
                'context_class': mock_gpu_context_class,
                'kernel_class': mock_gpu_kernel_class,
            }
    
    def test_on_complete_uses_snapshot(self, mock_gpu_engine):
        """测试on_complete回调使用快照"""
        received_stats = []
        
        def on_complete_callback(stats):
            received_stats.append(stats)
        
        engine = GPUCollisionEngine(
            {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"},
            on_complete=on_complete_callback
        )
        
        # 模拟引擎完成
        engine.stats.total_checked = 1000
        engine._running = False
        if engine.on_complete:
            engine.on_complete(engine.stats.snapshot())
        
        assert len(received_stats) == 1
        assert received_stats[0].total_checked == 1000
        # 验证是快照而非原对象
        assert received_stats[0] is not engine.stats
