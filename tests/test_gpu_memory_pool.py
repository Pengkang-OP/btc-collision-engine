# -*- coding: utf-8 -*-
"""GPU内存池优化模块单元测试"""
import pytest
from unittest.mock import Mock, MagicMock
from src.gpu.memory_pool import (
    GPUMemoryPool,
    GPUBufferAllocator,
    GlobalGPUMemoryManager,
    gpu_memory_manager,
    get_gpu_memory_pool
)


class TestGPUMemoryPool:
    """GPU内存池测试类"""
    
    def test_initialization(self):
        """测试初始化"""
        mock_context = Mock()
        pool = GPUMemoryPool(mock_context, max_buffers=50, max_memory_mb=256)
        
        assert pool._max_buffers == 50
        assert pool._max_memory_bytes == 256 * 1024 * 1024
    
    def test_allocate_new_buffer(self):
        """测试分配新缓冲区"""
        try:
            import pyopencl as cl
        except ImportError:
            pytest.skip("pyopencl未安装,跳过GPU测试")
            return
        
        mock_context = Mock()
        mock_buffer = Mock()
        
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("pyopencl.Buffer", lambda ctx, flags, size: mock_buffer)
            
            pool = GPUMemoryPool(mock_context, max_buffers=10)
            buf = pool.allocate(1024)
            
            assert buf is mock_buffer
            assert pool._total_allocated == 1
    
    def test_reuse_buffer(self):
        """测试缓冲区复用"""
        try:
            import pyopencl as cl
        except ImportError:
            pytest.skip("pyopencl未安装")
            return
        
        mock_context = Mock()
        call_count = {'count': 0}
        
        def mock_buffer_factory(ctx, flags, size):
            call_count['count'] += 1
            return Mock()
        
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("pyopencl.Buffer", mock_buffer_factory)
            
            pool = GPUMemoryPool(mock_context, max_buffers=10)
            
            # 第一次分配
            buf1 = pool.allocate(1024)
            assert call_count['count'] == 1
            
            # 归还
            pool.release(buf1, size=1024)
            
            # 第二次分配(应该复用)
            buf2 = pool.allocate(1024)
            
            # 仍然只有1次分配调用
            assert call_count['count'] == 1
            assert pool._total_reused == 1
    
    def test_max_buffers_limit(self):
        """测试最大缓冲区限制"""
        mock_context = Mock()
        
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("pyopencl.Buffer", lambda ctx, flags, size: Mock())
            
            pool = GPUMemoryPool(mock_context, max_buffers=3)
            
            # 分配并归还,超过限制
            buffers = []
            for _ in range(5):
                buf = pool.allocate(1024)
                buffers.append(buf)
            
            for buf in buffers:
                pool.release(buf, size=1024)
            
            # 池中不应该超过max_buffers
            total_pooled = sum(len(b) for b in pool._pool.values())
            assert total_pooled <= 3
    
    def test_get_stats(self):
        """测试统计信息获取"""
        mock_context = Mock()
        
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("pyopencl.Buffer", lambda ctx, flags, size: Mock())
            
            pool = GPUMemoryPool(mock_context, max_buffers=10)
            
            # 分配一些缓冲区
            for _ in range(5):
                buf = pool.allocate(512)
                pool.release(buf, size=512)
            
            stats = pool.get_stats()
            
            assert 'total_allocated' in stats
            assert 'total_reused' in stats
            assert 'reuse_rate' in stats
            # 第1次分配,后4次应该复用
            assert stats['total_allocated'] >= 1
            assert stats['total_reused'] >= 1
    
    def test_clear(self):
        """测试清空池"""
        mock_context = Mock()
        
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("pyopencl.Buffer", lambda ctx, flags, size: Mock())
            
            pool = GPUMemoryPool(mock_context, max_buffers=10)
            
            # 分配一些
            for _ in range(3):
                buf = pool.allocate(256)
                pool.release(buf, size=256)
            
            # 清空
            pool.clear()
            
            assert len(pool._pool) == 0


class TestGPUBufferAllocator:
    """GPU缓冲区分配器测试类"""
    
    def test_initialization(self):
        """测试初始化"""
        mock_context = Mock()
        allocator = GPUBufferAllocator(mock_context, max_pool_size=30)
        
        assert allocator is not None
    
    def test_allocate_different_types(self):
        """测试分配不同类型缓冲区"""
        mock_context = Mock()
        
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("pyopencl.Buffer", lambda ctx, flags, size: Mock())
            
            allocator = GPUBufferAllocator(mock_context)
            
            input_buf = allocator.allocate_input(1024)
            output_buf = allocator.allocate_output(2048)
            temp_buf = allocator.allocate_temp(512)
            
            assert input_buf is not None
            assert output_buf is not None
            assert temp_buf is not None


class TestGlobalGPUMemoryManager:
    """全局GPU内存管理器测试类"""
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        manager1 = GlobalGPUMemoryManager()
        manager2 = GlobalGPUMemoryManager()
        assert manager1 is manager2
    
    def test_get_pool_caching(self):
        """测试池缓存"""
        mock_context = Mock()
        manager = GlobalGPUMemoryManager()
        manager._pools.clear()  # 清空测试
        
        pool1 = manager.get_pool(mock_context)
        pool2 = manager.get_pool(mock_context)
        
        assert pool1 is pool2
    
    def test_clear_all(self):
        """测试清空所有池"""
        mock_context = Mock()
        manager = GlobalGPUMemoryManager()
        manager._pools.clear()
        
        # 创建一些池
        manager.get_pool(mock_context)
        manager.get_pool(Mock())
        
        # 清空
        manager.clear_all()
        
        assert len(manager._pools) == 0
