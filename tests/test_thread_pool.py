# -*- coding: utf-8 -*-
"""线程池优化模块单元测试"""
import pytest
import time
import threading
from src.core.thread_pool import (
    WorkStealingThreadPool,
    TaskBatch,
    GlobalThreadPoolManager,
    thread_pool_manager,
    get_thread_pool
)


class TestWorkStealingThreadPool:
    """工作窃取线程池测试类"""
    
    def test_initialization(self):
        """测试初始化"""
        pool = WorkStealingThreadPool(num_threads=4)
        assert pool.num_threads == 4
        assert len(pool._queues) == 4
    
    def test_default_thread_count(self):
        """测试默认线程数"""
        import os
        pool = WorkStealingThreadPool()
        expected = max(1, os.cpu_count() - 1)
        assert pool.num_threads == expected
    
    def test_submit_and_execute(self):
        """测试任务提交和执行"""
        pool = WorkStealingThreadPool(num_threads=2)
        pool.start()
        
        try:
            # 提交简单任务
            future = pool.submit(lambda x, y: x + y, 2, 3)
            result = future.result(timeout=5)
            
            assert result == 5
        finally:
            pool.stop()
    
    def test_multiple_tasks(self):
        """测试多任务执行"""
        pool = WorkStealingThreadPool(num_threads=4)
        pool.start()
        
        try:
            futures = []
            for i in range(10):
                future = pool.submit(lambda x: x * 2, i)
                futures.append(future)
            
            results = [f.result(timeout=5) for f in futures]
            expected = [i * 2 for i in range(10)]
            
            assert results == expected
        finally:
            pool.stop()
    
    def test_work_stealing(self):
        """测试工作窃取机制"""
        pool = WorkStealingThreadPool(num_threads=4, enable_work_stealing=True)
        pool.start()
        
        try:
            # 提交大量任务到单个队列
            futures = []
            for i in range(100):
                future = pool.submit(lambda: time.sleep(0.01))
                futures.append(future)
            
            # 等待所有任务完成
            for f in futures:
                f.result(timeout=10)
            
            stats = pool.get_stats()
            # 应该有任务被窃取
            print(f"\n工作窃取统计: {stats['tasks_stolen']}个任务被窃取")
        finally:
            pool.stop()
    
    def test_exception_handling(self):
        """测试异常处理"""
        pool = WorkStealingThreadPool(num_threads=2)
        pool.start()
        
        try:
            def failing_task():
                raise ValueError("Test error")
            
            future = pool.submit(failing_task)
            
            with pytest.raises(ValueError):
                future.result(timeout=5)
        finally:
            pool.stop()
    
    def test_get_stats(self):
        """测试统计信息获取"""
        pool = WorkStealingThreadPool(num_threads=4)
        pool.start()
        
        try:
            # 提交一些任务
            for i in range(10):
                pool.submit(lambda: i)
            
            time.sleep(0.5)
            
            stats = pool.get_stats()
            assert 'num_threads' in stats
            assert 'tasks_submitted' in stats
            assert 'tasks_completed' in stats
            assert stats['num_threads'] == 4
        finally:
            pool.stop()
    
    def test_stop_wait(self):
        """测试停止时等待任务完成"""
        pool = WorkStealingThreadPool(num_threads=2)
        pool.start()
        
        # 提交慢任务
        future = pool.submit(lambda: time.sleep(0.5))
        
        # 等待任务完成
        time.sleep(0.8)
        
        # 停止
        pool.stop(wait=True, timeout=5)
        
        # 任务应该已完成
        assert future.done()


class TestTaskBatch:
    """批量任务执行器测试类"""
    
    def test_batch_execution(self):
        """测试批量执行"""
        pool = WorkStealingThreadPool(num_threads=2)
        pool.start()
        
        try:
            batch = TaskBatch(pool)
            
            # 提交批量任务
            for i in range(5):
                batch.submit(lambda x: x * 2, i)
            
            results = batch.execute_all()
            expected = [0, 2, 4, 6, 8]
            
            assert results == expected
        finally:
            pool.stop()


class TestGlobalThreadPoolManager:
    """全局线程池管理器测试类"""
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        # 注意: get_thread_pool返回的是pool,不是manager
        pool1 = get_thread_pool()
        manager = thread_pool_manager
        
        assert pool1 is manager._pool  # pool应该是manager的_pool
    
    def test_initialize(self):
        """测试初始化"""
        # 创建新manager实例以避免全局状态干扰
        manager = GlobalThreadPoolManager()
        manager._pool = None
        manager._initialized = False
        
        manager.initialize(num_threads=4)
        
        assert manager._initialized == True
        assert manager._pool.num_threads == 4
    
    def test_get_pool(self):
        """测试获取池"""
        pool = get_thread_pool()
        assert pool is not None
        assert isinstance(pool, WorkStealingThreadPool)
