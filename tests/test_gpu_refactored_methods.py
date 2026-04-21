#!/usr/bin/env python3
"""GPU引擎P0-1重构辅助方法单元测试

测试GPU引擎重构后新增的7个辅助方法：
1. _generate_private_keys_batch
2. _start_async_key_generation
3. _wait_for_async_key_generation
4. _execute_gpu_batch
5. _process_gpu_matches
6. _update_performance_metrics
7. _check_and_report_progress
"""
import pytest
import time
import threading
import hashlib
from unittest.mock import Mock, patch, MagicMock
from src.collision.gpu_collision_engine import (
    GPUCollisionEngine,
    INITIAL_BATCH_SIZE,
    ASYNC_KEY_GEN_TIMEOUT,
    BATCH_LOG_FREQUENCY,
    INITIAL_BATCHES_LOG,
    EXCEPTION_RECOVERY_DELAY
)


def create_mock_gpu_engine(test_targets):
    """创建mock GPU引擎的统一辅助函数"""
    with patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', True):
        with patch('src.collision.gpu_collision_engine.GPUDevice') as mock_device, \
             patch('src.collision.gpu_collision_engine.GPUContext') as mock_context, \
             patch('src.collision.gpu_collision_engine.GPUKernel') as mock_kernel, \
             patch('src.collision.gpu_collision_engine.AsyncGPUExecutor') as mock_async_executor:
            
            mock_device_instance = Mock()
            mock_device_instance.context = Mock()
            mock_device_instance.queue = Mock()
            mock_device_instance.device_info = {'name': 'Test', 'vendor': 'Test', 'global_mem_size': 1024**3}
            mock_device_instance.initialize = Mock()
            mock_device_instance.get_device_info = Mock(return_value=mock_device_instance.device_info)
            mock_device_instance.cleanup = Mock()
            mock_device.return_value = mock_device_instance
            
            mock_context_instance = Mock()
            mock_context_instance.program = Mock()
            mock_context_instance.apply_optimizations = Mock()
            mock_context_instance.calculate_batch_size = Mock(return_value=65536)
            mock_context_instance.compile_kernel = Mock()
            mock_context_instance.cleanup = Mock()
            mock_context.return_value = mock_context_instance
            
            mock_kernel_instance = Mock()
            mock_kernel_instance.run_batch = Mock(return_value=[])
            mock_kernel_instance.set_targets = Mock()
            mock_kernel_instance.cleanup = Mock()
            mock_kernel_instance.max_batch_size = 65536
            mock_kernel.return_value = mock_kernel_instance
            
            # Mock异步执行器
            mock_async_instance = Mock()
            mock_async_instance.initialize_buffers = Mock()
            mock_async_instance.run_batch_async = Mock(return_value=([], 50.0))
            mock_async_instance.cleanup = Mock()
            mock_async_executor.return_value = mock_async_instance
            
            with patch('src.collision.gpu_collision_engine.GPUProfileLoader') as mock_profile:
                mock_profile.return_value.get_profile.return_value = None
                return GPUCollisionEngine(test_targets)


class TestGeneratePrivateKeysBatch:
    """测试 _generate_private_keys_batch 方法"""
    
    def setup_method(self):
        """设置测试环境"""
        self.test_targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
    
    def test_generate_correct_size(self):
        """测试生成正确大小的私钥批次"""
        engine = create_mock_gpu_engine(self.test_targets)
        
        # 测试生成100个私钥
        keys = engine._generate_private_keys_batch(100)
        assert len(keys) == 3200  # 100 * 32 bytes
        
        # 测试生成1个私钥
        keys = engine._generate_private_keys_batch(1)
        assert len(keys) == 32
        
        # 测试生成0个私钥
        keys = engine._generate_private_keys_batch(0)
        assert len(keys) == 0
    
    def test_generate_random_keys(self):
        """测试生成的私钥是随机的"""
        with patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', True):
            with patch('src.collision.gpu_collision_engine.GPUDevice') as mock_device, \
                 patch('src.collision.gpu_collision_engine.GPUContext') as mock_context, \
                 patch('src.collision.gpu_collision_engine.GPUKernel') as mock_kernel:
                
                # 设置mock (简化版)
                mock_device_instance = Mock()
                mock_device_instance.context = Mock()
                mock_device_instance.queue = Mock()
                mock_device_instance.device_info = {'name': 'Test', 'vendor': 'Test', 'global_mem_size': 1024**3}
                mock_device_instance.initialize = Mock()
                mock_device_instance.get_device_info = Mock(return_value=mock_device_instance.device_info)
                mock_device_instance.cleanup = Mock()
                mock_device.return_value = mock_device_instance
                
                mock_context_instance = Mock()
                mock_context_instance.program = Mock()
                mock_context_instance.apply_optimizations = Mock()
                mock_context_instance.calculate_batch_size = Mock(return_value=65536)
                mock_context_instance.compile_kernel = Mock()
                mock_context_instance.cleanup = Mock()
                mock_context.return_value = mock_context_instance
                
                mock_kernel_instance = Mock()
                mock_kernel_instance.run_batch = Mock(return_value=[])
                mock_kernel_instance.set_targets = Mock()
                mock_kernel_instance.cleanup = Mock()
                mock_kernel_instance.max_batch_size = 65536
                mock_kernel.return_value = mock_kernel_instance
                
                with patch('src.collision.gpu_collision_engine.GPUProfileLoader') as mock_profile:
                    mock_profile.return_value.get_profile.return_value = None
                    
                    engine = GPUCollisionEngine(self.test_targets)
                    
                    # 生成两批私钥，应该不同
                    keys1 = engine._generate_private_keys_batch(10)
                    keys2 = engine._generate_private_keys_batch(10)
                    assert keys1 != keys2
    
    def test_generate_unique_keys(self):
        """测试同一批次内的私钥唯一性"""
        with patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', True):
            with patch('src.collision.gpu_collision_engine.GPUDevice') as mock_device, \
                 patch('src.collision.gpu_collision_engine.GPUContext') as mock_context, \
                 patch('src.collision.gpu_collision_engine.GPUKernel') as mock_kernel:
                
                # 设置mock
                mock_device_instance = Mock()
                mock_device_instance.context = Mock()
                mock_device_instance.queue = Mock()
                mock_device_instance.device_info = {'name': 'Test', 'vendor': 'Test', 'global_mem_size': 1024**3}
                mock_device_instance.initialize = Mock()
                mock_device_instance.get_device_info = Mock(return_value=mock_device_instance.device_info)
                mock_device_instance.cleanup = Mock()
                mock_device.return_value = mock_device_instance
                
                mock_context_instance = Mock()
                mock_context_instance.program = Mock()
                mock_context_instance.apply_optimizations = Mock()
                mock_context_instance.calculate_batch_size = Mock(return_value=65536)
                mock_context_instance.compile_kernel = Mock()
                mock_context_instance.cleanup = Mock()
                mock_context.return_value = mock_context_instance
                
                mock_kernel_instance = Mock()
                mock_kernel_instance.run_batch = Mock(return_value=[])
                mock_kernel_instance.set_targets = Mock()
                mock_kernel_instance.cleanup = Mock()
                mock_kernel_instance.max_batch_size = 65536
                mock_kernel.return_value = mock_kernel_instance
                
                with patch('src.collision.gpu_collision_engine.GPUProfileLoader') as mock_profile:
                    mock_profile.return_value.get_profile.return_value = None
                    
                    engine = GPUCollisionEngine(self.test_targets)
                    
                    # 生成1000个私钥
                    keys = engine._generate_private_keys_batch(1000)
                    
                    # 提取所有私钥
                    key_list = [keys[i:i+32] for i in range(0, len(keys), 32)]
                    
                    # 验证唯一性（基于概率，几乎不可能重复）
                    assert len(key_list) == len(set(key_list))


class TestAsyncKeyGeneration:
    """测试异步私钥生成相关方法"""
    
    def setup_method(self):
        """设置测试环境"""
        self.test_targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
    
    def _create_mock_engine(self):
        """创建mock引擎"""
        with patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', True):
            with patch('src.collision.gpu_collision_engine.GPUDevice') as mock_device, \
                 patch('src.collision.gpu_collision_engine.GPUContext') as mock_context, \
                 patch('src.collision.gpu_collision_engine.GPUKernel') as mock_kernel:
                
                mock_device_instance = Mock()
                mock_device_instance.context = Mock()
                mock_device_instance.queue = Mock()
                mock_device_instance.device_info = {'name': 'Test', 'vendor': 'Test', 'global_mem_size': 1024**3}
                mock_device_instance.initialize = Mock()
                mock_device_instance.get_device_info = Mock(return_value=mock_device_instance.device_info)
                mock_device_instance.cleanup = Mock()
                mock_device.return_value = mock_device_instance
                
                mock_context_instance = Mock()
                mock_context_instance.program = Mock()
                mock_context_instance.apply_optimizations = Mock()
                mock_context_instance.calculate_batch_size = Mock(return_value=65536)
                mock_context_instance.compile_kernel = Mock()
                mock_context_instance.cleanup = Mock()
                mock_context.return_value = mock_context_instance
                
                mock_kernel_instance = Mock()
                mock_kernel_instance.run_batch = Mock(return_value=[])
                mock_kernel_instance.set_targets = Mock()
                mock_kernel_instance.cleanup = Mock()
                mock_kernel_instance.max_batch_size = 65536
                mock_kernel.return_value = mock_kernel_instance
                
                with patch('src.collision.gpu_collision_engine.GPUProfileLoader') as mock_profile:
                    mock_profile.return_value.get_profile.return_value = None
                    return GPUCollisionEngine(self.test_targets)
    
    def test_start_async_key_generation(self):
        """测试启动异步私钥生成"""
        engine = self._create_mock_engine()
        
        # 启动异步生成
        thread, result = engine._start_async_key_generation(100)
        
        # 验证返回类型
        assert isinstance(thread, threading.Thread)
        assert isinstance(result, list)
        assert len(result) == 1
        
        # 等待生成完成
        thread.join(timeout=5.0)
        
        # 验证结果
        assert result[0] is not None
        assert len(result[0]) == 3200  # 100 * 32 bytes
    
    def test_wait_for_async_key_generation_success(self):
        """测试等待异步生成成功"""
        engine = self._create_mock_engine()
        
        # 启动异步生成
        thread, result = engine._start_async_key_generation(50)
        
        # 等待完成
        keys = engine._wait_for_async_key_generation(thread, result, batch_num=1)
        
        # 验证结果
        assert isinstance(keys, bytes)
        assert len(keys) == 1600  # 50 * 32 bytes
    
    def test_wait_for_async_key_generation_timeout(self):
        """测试异步生成超时处理"""
        engine = self._create_mock_engine()
        
        # 创建一个永远不会完成的线程
        def never_finish():
            time.sleep(100)
        
        thread = threading.Thread(target=never_finish, daemon=True)
        thread.start()
        result = [None]
        
        # 应该超时并返回fallback结果
        keys = engine._wait_for_async_key_generation(thread, result, batch_num=1)
        
        # 验证返回了fallback生成的私钥
        assert isinstance(keys, bytes)
        assert len(keys) == engine.batch_size * 32
    
    def test_wait_for_async_key_generation_none_result(self):
        """测试异步生成结果为None的处理"""
        engine = self._create_mock_engine()
        
        # 创建一个已完成但结果为None的线程
        def set_none():
            pass
        
        thread = threading.Thread(target=set_none, daemon=True)
        thread.start()
        thread.join()  # 立即完成
        result = [None]
        
        # 应该返回fallback结果
        keys = engine._wait_for_async_key_generation(thread, result, batch_num=1)
        
        assert isinstance(keys, bytes)
        assert len(keys) == engine.batch_size * 32


class TestExecuteGPUBatch:
    """测试 _execute_gpu_batch 方法"""
    
    def setup_method(self):
        """设置测试环境"""
        self.test_targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
    
    def _create_mock_engine(self):
        """创建mock引擎"""
        with patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', True):
            with patch('src.collision.gpu_collision_engine.GPUDevice') as mock_device, \
                 patch('src.collision.gpu_collision_engine.GPUContext') as mock_context, \
                 patch('src.collision.gpu_collision_engine.GPUKernel') as mock_kernel:
                
                mock_device_instance = Mock()
                mock_device_instance.context = Mock()
                mock_device_instance.queue = Mock()
                mock_device_instance.device_info = {'name': 'Test', 'vendor': 'Test', 'global_mem_size': 1024**3}
                mock_device_instance.initialize = Mock()
                mock_device_instance.get_device_info = Mock(return_value=mock_device_instance.device_info)
                mock_device_instance.cleanup = Mock()
                mock_device.return_value = mock_device_instance
                
                mock_context_instance = Mock()
                mock_context_instance.program = Mock()
                mock_context_instance.apply_optimizations = Mock()
                mock_context_instance.calculate_batch_size = Mock(return_value=65536)
                mock_context_instance.compile_kernel = Mock()
                mock_context_instance.cleanup = Mock()
                mock_context.return_value = mock_context_instance
                
                mock_kernel_instance = Mock()
                mock_kernel_instance.run_batch = Mock(return_value=[])
                mock_kernel_instance.set_targets = Mock()
                mock_kernel_instance.cleanup = Mock()
                mock_kernel_instance.max_batch_size = 65536
                mock_kernel.return_value = mock_kernel_instance
                
                with patch('src.collision.gpu_collision_engine.GPUProfileLoader') as mock_profile:
                    mock_profile.return_value.get_profile.return_value = None
                    return GPUCollisionEngine(self.test_targets)
    
    def test_execute_gpu_batch_no_matches(self):
        """测试执行GPU batch无匹配"""
        engine = self._create_mock_engine()
        
        # 准备私钥
        private_keys = b'\x00' * 3200  # 100个私钥
        
        # 执行batch
        matches, exec_time = engine._execute_gpu_batch(private_keys, 100, 1)
        
        # 验证结果
        assert isinstance(matches, list)
        assert isinstance(exec_time, float)
        assert exec_time >= 0
        assert len(matches) == 0  # mock返回空列表
    
    def test_execute_gpu_batch_with_matches(self):
        """测试执行GPU batch有匹配"""
        engine = self._create_mock_engine()
        
        # 设置mock返回匹配结果
        engine._gpu_kernel.run_batch = Mock(return_value=[
            {"key_index": 0, "target_index": 0},
            {"key_index": 50, "target_index": 0}
        ])
        
        private_keys = b'\x00' * 3200
        
        matches, exec_time = engine._execute_gpu_batch(private_keys, 100, 1)
        
        assert len(matches) == 2
        assert matches[0]["key_index"] == 0
        assert matches[1]["key_index"] == 50
    
    def test_execute_gpu_batch_logging_frequency(self):
        """测试日志记录频率控制"""
        engine = self._create_mock_engine()
        
        private_keys = b'\x00' * 3200
        
        # 测试初始批次（应该记录日志）
        with patch('src.collision.gpu_collision_engine.logger') as mock_logger:
            engine._execute_gpu_batch(private_keys, 100, 1)
            # batch_num=1 <= INITIAL_BATCHES_LOG=3，应该记录日志
            assert mock_logger.debug.call_count >= 1
            
            mock_logger.reset_mock()
            
            # 测试非初始批次（不应该记录日志）
            engine._execute_gpu_batch(private_keys, 100, 50)
            # batch_num=50 > 3 且 50 % 100 != 0，不应该记录日志
            assert mock_logger.debug.call_count == 0
            
            mock_logger.reset_mock()
            
            # 测试频率批次（应该记录日志）
            engine._execute_gpu_batch(private_keys, 100, 100)
            # batch_num=100 % 100 == 0，应该记录日志
            assert mock_logger.debug.call_count >= 1


class TestProcessGPUMatches:
    """测试 _process_gpu_matches 方法"""
    
    def setup_method(self):
        """设置测试环境"""
        self.test_targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
        self.target_list = ["1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"]
    
    def _create_mock_engine(self):
        """创建mock引擎"""
        with patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', True):
            with patch('src.collision.gpu_collision_engine.GPUDevice') as mock_device, \
                 patch('src.collision.gpu_collision_engine.GPUContext') as mock_context, \
                 patch('src.collision.gpu_collision_engine.GPUKernel') as mock_kernel:
                
                mock_device_instance = Mock()
                mock_device_instance.context = Mock()
                mock_device_instance.queue = Mock()
                mock_device_instance.device_info = {'name': 'Test', 'vendor': 'Test', 'global_mem_size': 1024**3}
                mock_device_instance.initialize = Mock()
                mock_device_instance.get_device_info = Mock(return_value=mock_device_instance.device_info)
                mock_device_instance.cleanup = Mock()
                mock_device.return_value = mock_device_instance
                
                mock_context_instance = Mock()
                mock_context_instance.program = Mock()
                mock_context_instance.apply_optimizations = Mock()
                mock_context_instance.calculate_batch_size = Mock(return_value=65536)
                mock_context_instance.compile_kernel = Mock()
                mock_context_instance.cleanup = Mock()
                mock_context.return_value = mock_context_instance
                
                mock_kernel_instance = Mock()
                mock_kernel_instance.run_batch = Mock(return_value=[])
                mock_kernel_instance.set_targets = Mock()
                mock_kernel_instance.cleanup = Mock()
                mock_kernel_instance.max_batch_size = 65536
                mock_kernel.return_value = mock_kernel_instance
                
                with patch('src.collision.gpu_collision_engine.GPUProfileLoader') as mock_profile:
                    mock_profile.return_value.get_profile.return_value = None
                    return GPUCollisionEngine(self.test_targets)
    
    def test_process_matches_success(self):
        """测试成功处理匹配"""
        engine = self._create_mock_engine()
        
        # 创建mock回调
        match_callback = Mock()
        engine.on_match = match_callback
        
        # 准备私钥和匹配结果
        private_keys = b'\x01' * 32 + b'\x02' * 32  # 2个私钥
        matches = [
            {"key_index": 0, "target_index": 0}
        ]
        
        # 处理匹配
        engine._process_gpu_matches(private_keys, matches)
        
        # 验证回调被调用
        assert match_callback.called
    
    def test_process_matches_deduplication(self):
        """测试去重过滤"""
        engine = self._create_mock_engine()
        
        match_callback = Mock()
        engine.on_match = match_callback
        
        private_keys = b'\x01' * 32
        matches = [{"key_index": 0, "target_index": 0}]
        
        # 第一次处理
        engine._process_gpu_matches(private_keys, matches)
        call_count_1 = match_callback.call_count
        
        # 第二次处理（应该被去重）
        engine._process_gpu_matches(private_keys, matches)
        call_count_2 = match_callback.call_count
        
        # 验证第二次没有触发回调（去重）
        assert call_count_2 == call_count_1


class TestPerformanceMetrics:
    """测试 _update_performance_metrics 方法"""
    
    def setup_method(self):
        """设置测试环境"""
        self.test_targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
    
    def _create_mock_engine(self):
        """创建mock引擎"""
        with patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', True):
            with patch('src.collision.gpu_collision_engine.GPUDevice') as mock_device, \
                 patch('src.collision.gpu_collision_engine.GPUContext') as mock_context, \
                 patch('src.collision.gpu_collision_engine.GPUKernel') as mock_kernel:
                
                mock_device_instance = Mock()
                mock_device_instance.context = Mock()
                mock_device_instance.queue = Mock()
                mock_device_instance.device_info = {'name': 'Test', 'vendor': 'Test', 'global_mem_size': 1024**3}
                mock_device_instance.initialize = Mock()
                mock_device_instance.get_device_info = Mock(return_value=mock_device_instance.device_info)
                mock_device_instance.cleanup = Mock()
                mock_device.return_value = mock_device_instance
                
                mock_context_instance = Mock()
                mock_context_instance.program = Mock()
                mock_context_instance.apply_optimizations = Mock()
                mock_context_instance.calculate_batch_size = Mock(return_value=65536)
                mock_context_instance.compile_kernel = Mock()
                mock_context_instance.cleanup = Mock()
                mock_context.return_value = mock_context_instance
                
                mock_kernel_instance = Mock()
                mock_kernel_instance.run_batch = Mock(return_value=[])
                mock_kernel_instance.set_targets = Mock()
                mock_kernel_instance.cleanup = Mock()
                mock_kernel_instance.max_batch_size = 65536
                mock_kernel.return_value = mock_kernel_instance
                
                with patch('src.collision.gpu_collision_engine.GPUProfileLoader') as mock_profile:
                    mock_profile.return_value.get_profile.return_value = None
                    return GPUCollisionEngine(self.test_targets)
    
    def test_update_performance_metrics(self):
        """测试更新性能指标"""
        engine = self._create_mock_engine()
        
        # 创建mock性能监控器
        mock_monitor = Mock()
        engine.gpu_performance_monitor = mock_monitor
        
        # 更新性能指标
        engine._update_performance_metrics(batch_size=1000, execution_time_ms=50.5)
        
        # 验证调用
        assert mock_monitor.record_kernel_metrics.called
        call_args = mock_monitor.record_kernel_metrics.call_args
        assert call_args[1]['batch_size'] == 1000
        assert call_args[1]['execution_time_ms'] == 50.5
    
    def test_update_performance_metrics_no_monitor(self):
        """测试没有性能监控器时不报错"""
        engine = self._create_mock_engine()
        engine.gpu_performance_monitor = None
        
        # 应该不抛出异常
        engine._update_performance_metrics(batch_size=1000, execution_time_ms=50.5)


class TestProgressReporting:
    """测试 _check_and_report_progress 方法"""
    
    def setup_method(self):
        """设置测试环境"""
        self.test_targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
    
    def _create_mock_engine(self):
        """创建mock引擎"""
        with patch('src.collision.gpu_collision_engine.PYOPENCL_AVAILABLE', True):
            with patch('src.collision.gpu_collision_engine.GPUDevice') as mock_device, \
                 patch('src.collision.gpu_collision_engine.GPUContext') as mock_context, \
                 patch('src.collision.gpu_collision_engine.GPUKernel') as mock_kernel:
                
                mock_device_instance = Mock()
                mock_device_instance.context = Mock()
                mock_device_instance.queue = Mock()
                mock_device_instance.device_info = {'name': 'Test', 'vendor': 'Test', 'global_mem_size': 1024**3}
                mock_device_instance.initialize = Mock()
                mock_device_instance.get_device_info = Mock(return_value=mock_device_instance.device_info)
                mock_device_instance.cleanup = Mock()
                mock_device.return_value = mock_device_instance
                
                mock_context_instance = Mock()
                mock_context_instance.program = Mock()
                mock_context_instance.apply_optimizations = Mock()
                mock_context_instance.calculate_batch_size = Mock(return_value=65536)
                mock_context_instance.compile_kernel = Mock()
                mock_context_instance.cleanup = Mock()
                mock_context.return_value = mock_context_instance
                
                mock_kernel_instance = Mock()
                mock_kernel_instance.run_batch = Mock(return_value=[])
                mock_kernel_instance.set_targets = Mock()
                mock_kernel_instance.cleanup = Mock()
                mock_kernel_instance.max_batch_size = 65536
                mock_kernel.return_value = mock_kernel_instance
                
                with patch('src.collision.gpu_collision_engine.GPUProfileLoader') as mock_profile:
                    mock_profile.return_value.get_profile.return_value = None
                    return GPUCollisionEngine(self.test_targets)
    
    def test_progress_report_trigger(self):
        """测试进度报告触发"""
        engine = self._create_mock_engine()
        
        # 设置进度回调
        progress_callback = Mock()
        engine.on_progress = progress_callback
        
        # 重置最后进度时间（强制触发）
        engine._last_progress_time = 0
        
        # 检查进度
        engine._check_and_report_progress(batch_count=10000, current_batch_size=1000)
        
        # 验证回调被调用
        assert progress_callback.called
    
    def test_progress_report_throttle(self):
        """测试进度报告节流"""
        engine = self._create_mock_engine()
        
        progress_callback = Mock()
        engine.on_progress = progress_callback
        
        # 设置最后进度时间为当前时间
        engine._last_progress_time = time.time()
        
        # 检查进度（不应该触发）
        engine._check_and_report_progress(batch_count=10000, current_batch_size=1000)
        
        # 验证回调未被调用
        assert not progress_callback.called


class TestConstants:
    """测试常量定义"""
    
    def test_initial_batch_size(self):
        """测试初始批次大小常量"""
        assert INITIAL_BATCH_SIZE == 1_000_000
        assert isinstance(INITIAL_BATCH_SIZE, int)
    
    def test_async_key_gen_timeout(self):
        """测试异步私钥生成超时常量"""
        assert ASYNC_KEY_GEN_TIMEOUT == 30.0
        assert isinstance(ASYNC_KEY_GEN_TIMEOUT, float)
    
    def test_batch_log_frequency(self):
        """测试日志记录频率常量"""
        assert BATCH_LOG_FREQUENCY == 100
        assert isinstance(BATCH_LOG_FREQUENCY, int)
    
    def test_initial_batches_log(self):
        """测试初始批次日志数量常量"""
        assert INITIAL_BATCHES_LOG == 3
        assert isinstance(INITIAL_BATCHES_LOG, int)
    
    def test_exception_recovery_delay(self):
        """测试异常恢复延迟常量"""
        assert EXCEPTION_RECOVERY_DELAY == 0.1
        assert isinstance(EXCEPTION_RECOVERY_DELAY, float)
