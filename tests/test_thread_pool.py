"""线程池优化模块单元测试"""

import time

import pytest

from src.core.thread_pool import (
    DEFAULT_MAX_WORKERS,
    DEFAULT_MIN_WORKERS,
    GlobalThreadPoolManager,
    TaskBatch,
    WorkStealingThreadPool,
    _validate_worker_count,
    get_thread_pool,
    thread_pool_manager,
)


class TestWorkStealingThreadPool:
    """工作窃取线程池测试类"""

    def test_initialization(self):
        """测试初始化"""
        pool = WorkStealingThreadPool(num_threads=4)
        assert pool.num_threads == 4
        assert len(pool._queues) == 4

    def test_default_thread_count(self):
        """测试默认线程数 (P3-8: 不再-1, 直接使用CPU核心数)"""
        import os

        pool = WorkStealingThreadPool()
        expected = os.cpu_count() or 4
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
                pool.submit(lambda i=i: i)

            time.sleep(0.5)

            stats = pool.get_stats()
            assert "num_threads" in stats
            assert "tasks_submitted" in stats
            assert "tasks_completed" in stats
            assert stats["num_threads"] == 4
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

        assert manager._initialized is True
        assert manager._pool.num_threads == 4

    def test_get_pool(self):
        """测试获取池"""
        pool = get_thread_pool()
        assert pool is not None
        assert isinstance(pool, WorkStealingThreadPool)

    def test_initialize_already_initialized(self):
        """测试重复初始化被忽略"""
        manager = GlobalThreadPoolManager()
        manager._pool = None
        manager._initialized = False
        manager.initialize(num_threads=2)
        assert manager._initialized is True
        first_pool = manager._pool
        # 重复初始化应被忽略
        manager.initialize(num_threads=8)
        assert manager._pool is first_pool
        assert manager._pool.num_threads == 2

    def test_shutdown_clean(self):
        """测试正常关闭"""
        manager = GlobalThreadPoolManager()
        manager._pool = None
        manager._initialized = False
        manager._shutdown_complete = False
        manager.initialize(num_threads=2)
        manager.shutdown()
        assert manager._shutdown_complete is True
        assert manager._initialized is False

    def test_shutdown_already_complete(self):
        """测试重复关闭不报错"""
        manager = GlobalThreadPoolManager()
        manager._pool = None
        manager._initialized = False
        manager._shutdown_complete = False
        manager.initialize(num_threads=2)
        manager.shutdown()
        # 重复关闭
        manager.shutdown()
        assert manager._shutdown_complete is True

    def test_shutdown_with_health_issues(self):
        """测试关闭时检测到健康问题"""
        manager = GlobalThreadPoolManager()
        manager._pool = None
        manager._initialized = False
        manager._shutdown_complete = False
        manager.initialize(num_threads=4)
        pool = manager._pool
        pool.start()
        try:
            # 直接设置计数器产生多种健康问题
            with pool._stats_lock:
                # 高失败率: completed+failed>100, fail_rate>10%
                pool._tasks_completed = 80
                pool._tasks_failed = 30  # fail_rate=27%>10%
                # 线程饥饿: total_tasks>100 且不均衡
                pool._thread_tasks = [90, 5, 5, 5]  # total=105>100
            # shutdown 会做健康检查 → 触发 line 453
            manager.shutdown()
        finally:
            if pool._threads:
                pool.stop()

    def test_resize_pool_not_initialized(self):
        """测试线程池未初始化时 resize 返回 False"""
        manager = GlobalThreadPoolManager()
        original_pool = manager._pool
        manager._pool = None
        manager._initialized = False
        try:
            result = manager.resize(4)
            assert result is False
        finally:
            manager._pool = original_pool
            manager._initialized = True

    def test_resize_new_gte_current(self):
        """测试 resize 新线程数 >= 当前时返回 False"""
        manager = GlobalThreadPoolManager()
        manager._pool = None
        manager._initialized = False
        manager.initialize(num_threads=4)
        try:
            # 新线程数 >= 当前
            result = manager.resize(4)
            assert result is False
            result = manager.resize(8)
            assert result is False
        finally:
            manager._pool.stop()
            manager._initialized = False

    def test_resize_success(self):
        """测试 resize 缩容成功"""
        manager = GlobalThreadPoolManager()
        manager._pool = None
        manager._initialized = False
        manager.initialize(num_threads=8)
        try:
            result = manager.resize(2)
            assert result is True
            assert manager._resize_pending == 2
        finally:
            manager._pool.stop()
            manager._initialized = False

    def test_get_health_no_pool(self):
        """测试 get_health 线程池未初始化返回 None"""
        manager = GlobalThreadPoolManager()
        original_pool = manager._pool
        manager._pool = None
        try:
            result = manager.get_health()
            assert result is None
        finally:
            manager._pool = original_pool

    def test_get_health_with_pool(self):
        """测试 get_health 正常返回"""
        manager = GlobalThreadPoolManager()
        manager._pool = None
        manager._initialized = False
        manager.initialize(num_threads=2)
        try:
            health = manager.get_health()
            assert health is not None
            assert "status" in health
            assert "issues" in health
            assert "active_threads" in health
        finally:
            manager._pool.stop()
            manager._initialized = False


class TestValidateWorkerCount:
    """_validate_worker_count 函数边界测试"""

    def test_none_returns_cpu_count(self):
        """None 返回 CPU 核心数"""
        import os
        result = _validate_worker_count(None)
        assert result == (os.cpu_count() or 4)

    def test_zero_returns_cpu_count(self):
        """0 返回 CPU 核心数"""
        import os
        result = _validate_worker_count(0)
        assert result == (os.cpu_count() or 4)

    def test_negative_returns_cpu_count(self):
        """负数返回 CPU 核心数"""
        import os
        result = _validate_worker_count(-5)
        assert result == (os.cpu_count() or 4)

    def test_above_max_capped(self):
        """超过上限被截断"""
        result = _validate_worker_count(2000)
        assert result == DEFAULT_MAX_WORKERS

    def test_below_min_capped(self):
        """低于下限（浮点数小数）被修正"""
        result = _validate_worker_count(0.5)
        assert result == DEFAULT_MIN_WORKERS

    def test_valid_count_passthrough(self):
        """合法值原样返回"""
        result = _validate_worker_count(8)
        assert result == 8
        result = _validate_worker_count(1024)
        assert result == 1024
        result = _validate_worker_count(1)
        assert result == 1


class TestWorkStealingPoolEdgeCases:
    """WorkStealingThreadPool 边界/未覆盖路径测试"""

    def test_init_without_work_stealing(self):
        """测试禁用工作窃取初始化"""
        pool = WorkStealingThreadPool(num_threads=2, enable_work_stealing=False)
        assert pool.enable_work_stealing is False
        assert pool.num_threads == 2

    def test_get_task_no_stealing(self):
        """测试禁用窃取时 _get_task 返回 None"""
        pool = WorkStealingThreadPool(num_threads=2, enable_work_stealing=False)
        pool.start()
        try:
            # Queue is empty and stealing disabled, so _get_task returns None
            result = pool._get_task(0)
            assert result is None
        finally:
            pool.stop()

    def test_stop_no_wait(self):
        """测试 stop(wait=False) 不等待"""
        pool = WorkStealingThreadPool(num_threads=2)
        pool.start()
        pool.stop(wait=False)
        # 不应挂起，快速返回
        assert pool._stop_event.is_set()

    def test_stop_timeout_thread_alive(self):
        """测试 stop timeout 触发 is_alive 检查"""
        pool = WorkStealingThreadPool(num_threads=1)
        pool.start()
        # 提交一个长时间任务
        pool.submit(lambda: time.sleep(5))
        # 等待线程开始执行任务（进入 sleep(5)）
        time.sleep(0.1)
        # 用极短 timeout 停止，线程仍在运行 → 触发 is_alive()
        pool.stop(wait=True, timeout=0.001)

    def test_stats_before_start(self):
        """测试未启动时 get_stats（_start_time 为 None）"""
        pool = WorkStealingThreadPool(num_threads=2)
        stats = pool.get_stats()
        assert stats["uptime_seconds"] == 0

    def test_steal_work_returns_none_when_all_empty(self):
        """测试所有队列为空时窃取返回 None"""
        pool = WorkStealingThreadPool(num_threads=2, enable_work_stealing=True)
        pool.start()
        try:
            result = pool._steal_work(0)
            assert result is None
        finally:
            pool.stop()


class TestHealthCheck:
    """health_check 全面测试"""

    def test_health_check_healthy(self):
        """测试健康检查：正常状态"""
        pool = WorkStealingThreadPool(num_threads=2)
        pool.start()
        try:
            for _ in range(20):
                pool.submit(lambda: 1 + 1)
            time.sleep(0.3)
            health = pool.health_check()
            assert health["status"] == "healthy"
            assert health["issues"] == []
            assert health["active_threads"] == 2
        finally:
            pool.stop()

    def test_health_check_dead_thread_detected(self):
        """测试健康检查：检测死线程"""
        pool = WorkStealingThreadPool(num_threads=4)
        pool.start()
        try:
            # 直接清空部分线程记录来模拟死线程
            pool._threads = pool._threads[:2]  # 保留2个
            health = pool.health_check()
            assert health["status"] == "degraded"
            assert len(health["issues"]) >= 1
            assert any("死线程" in issue for issue in health["issues"])
        finally:
            pool._threads = []  # 清理引用避免stop报错
            pool.stop()

    def test_health_check_thread_starvation(self):
        """测试健康检查：线程饥饿检测"""
        pool = WorkStealingThreadPool(num_threads=4)
        pool.start()
        try:
            # 先提交少量任务确保线程启动
            for _ in range(10):
                pool.submit(lambda: 1 + 1)
            time.sleep(0.3)

            # 直接设置计数器制造线程饥饿场景
            # total_tasks=120>100, avg=30, thread[2]=1 < 3 → 饥饿
            with pool._stats_lock:
                pool._thread_tasks = [50, 40, 1, 30]  # total=121
            health = pool.health_check()
            assert any("线程饥饿" in issue for issue in health["issues"])
        finally:
            pool.stop()

    def test_health_check_high_failure_rate(self):
        """测试健康检查：高失败率检测"""
        pool = WorkStealingThreadPool(num_threads=2)
        pool.start()
        try:
            def fail():
                raise RuntimeError("fail")

            # 提交一些失败任务
            for _ in range(30):
                pool.submit(fail)
            time.sleep(0.5)

            # 直接设置计数器以触发高失败率检测
            # 需要 completed + failed > 100 且 fail_rate > 0.1
            with pool._stats_lock:
                pool._tasks_completed = 50
                pool._tasks_failed = 60  # 总=110>100, 失败率=54%>10%
            health = pool.health_check()
            assert any("高失败率" in issue for issue in health["issues"])
            assert health["status"] == "degraded"
        finally:
            pool.stop()


class TestGetThreadPool:
    """get_thread_pool 函数边界测试"""

    def test_get_thread_pool_initializes_if_needed(self):
        """测试 pool 为 None 时自动初始化"""
        # 模拟未初始化状态
        original_pool = thread_pool_manager._pool
        original_initialized = thread_pool_manager._initialized
        thread_pool_manager._pool = None
        thread_pool_manager._initialized = False
        thread_pool_manager._shutdown_complete = False
        try:
            p = get_thread_pool()
            assert p is not None
            assert isinstance(p, WorkStealingThreadPool)
            assert thread_pool_manager._initialized is True
        finally:
            # 恢复原始状态
            if thread_pool_manager._pool and thread_pool_manager._pool is not original_pool:
                thread_pool_manager._pool.stop()
            thread_pool_manager._pool = original_pool
            thread_pool_manager._initialized = original_initialized

    def test_get_thread_pool_reinitialize_on_none(self):
        """测试 pool=None 但 initialized=True 时的二次初始化路径 (lines 505-506)"""
        original_pool = thread_pool_manager._pool
        original_initialized = thread_pool_manager._initialized
        original_shutdown = thread_pool_manager._shutdown_complete
        original_initialize = thread_pool_manager.initialize

        # 模拟已初始化但 pool 为 None 的异常状态
        thread_pool_manager._pool = None
        thread_pool_manager._initialized = True
        thread_pool_manager._shutdown_complete = False

        # Patch initialize：即使 _initialized=True 也能重新初始化
        def patched_initialize(num_threads=None):
            thread_pool_manager._pool = WorkStealingThreadPool(2)
            thread_pool_manager._pool.start()
            thread_pool_manager._initialized = True
            thread_pool_manager._shutdown_complete = False

        thread_pool_manager.initialize = patched_initialize

        try:
            p = get_thread_pool()
            assert p is not None
            assert isinstance(p, WorkStealingThreadPool)
        finally:
            if thread_pool_manager._pool:
                thread_pool_manager._pool.stop()
            thread_pool_manager._pool = original_pool
            thread_pool_manager._initialized = original_initialized
            thread_pool_manager._shutdown_complete = original_shutdown
            thread_pool_manager.initialize = original_initialize
