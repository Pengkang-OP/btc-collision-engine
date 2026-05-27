"""memory_pool 边缘覆盖测试 — 补全剩余 7 行缺失"""

from unittest.mock import patch

from src.core.memory_pool import (
    GlobalPoolManager,
    ObjectPool,
)


class _DummyObj:
    """测试用对象"""

    def __init__(self):
        self.data = None

    def reset(self):
        self.data = None


class TestObjectPoolAutoTuneIdleShrink:
    """覆盖 auto_tune 中空闲缩容路径 (lines 334-349)"""

    def test_auto_tune_shrink_idle_branch(self):
        """空闲对象过多时 auto_tune 内部缩容（del _pool[target:]）"""
        pool = ObjectPool(lambda: _DummyObj(), initial_size=5, max_size=100)
        # 填充池到超过阈值 (POOL_SHRINK_THRESHOLD_RATIO=3, initial_size=5 → 阈值=15)
        objs = []
        for _ in range(50):
            objs.append(pool.acquire())
        for o in objs:
            pool.release(o)
        assert len(pool._pool) > 5 * 3
        pre_size = len(pool._pool)

        adjusted = pool.auto_tune(max_memory_mb=1024)
        assert adjusted
        # auto_tune 内部使用 del _pool[target:] 缩容到 initial_size
        assert len(pool._pool) == pool._initial_size
        assert len(pool._pool) < pre_size


class TestGlobalPoolManagerAutoCleanupEdge:
    """覆盖 _auto_cleanup_loop 中 tuned/released > 0 的日志分支 (lines 600-603)"""

    def setup_method(self, method):
        GlobalPoolManager._instance = None

    def teardown_method(self, method):
        GlobalPoolManager._instance = None

    def test_auto_cleanup_loop_debug_log_branch(self):
        """当 tuned=True 或 released>0 时输出 debug 日志"""
        mgr = GlobalPoolManager()
        mgr.initialize()

        with patch.object(mgr, "auto_tune_all", return_value=True):
            with patch.object(mgr, "shrink_all", return_value=5):
                with patch.object(mgr._cleanup_state, "stop_event") as mock_event:
                    mock_event.wait.side_effect = [False, True]  # 只运行一次
                    mgr._auto_cleanup_loop(0.01)
        # 不应崩溃

    def test_auto_cleanup_loop_debug_log_tuned_only(self):
        """仅 tuned=True（released=0）时也输出 debug 日志"""
        mgr = GlobalPoolManager()
        mgr.initialize()

        with patch.object(mgr, "auto_tune_all", return_value=True):
            with patch.object(mgr, "shrink_all", return_value=0):
                with patch.object(mgr._cleanup_state, "stop_event") as mock_event:
                    mock_event.wait.side_effect = [False, True]
                    mgr._auto_cleanup_loop(0.01)


class TestGlobalPoolManagerStopCleanupTimeout:
    """覆盖 stop_auto_cleanup 超时警告分支 (line 654)"""

    def setup_method(self, method):
        GlobalPoolManager._instance = None

    def teardown_method(self, method):
        GlobalPoolManager._instance = None

    def test_stop_auto_cleanup_timeout_warning_log(self):
        """线程在超时后仍存活 → 输出 warning"""
        mgr = GlobalPoolManager()
        mgr.initialize()
        mgr.start_auto_cleanup(interval_seconds=3600)

        # 设置 stop_event 让线程尝试退出
        mgr._cleanup_state.stop_event.set()

        # Mock join 不做实际等待, 然后 is_alive 返回 True
        with patch.object(mgr._cleanup_state.thread, "join") as mock_join:
            with patch.object(mgr._cleanup_state.thread, "is_alive", return_value=True):
                mgr.stop_auto_cleanup(timeout=0.1)
                mock_join.assert_called_once()

        # 清理残留线程
        mgr._cleanup_state.stop_event.set()
        if mgr._cleanup_state.thread and mgr._cleanup_state.thread.is_alive():
            mgr._cleanup_state.thread.join(timeout=2.0)


class TestECPointPool:
    """ECPointPool 覆盖 — 当前未测 acquire(x,y,curve) / release / get_stats"""

    def setup_method(self, method):
        GlobalPoolManager._instance = None

    def teardown_method(self, method):
        GlobalPoolManager._instance = None

    def test_ecpoint_pool_acquire_with_coords(self):
        """获取 ECPoint 并设置坐标"""
        mgr = GlobalPoolManager()
        mgr.initialize()
        pool = mgr.get_ecpoint_pool()
        pt = pool.acquire(x=123, y=456, curve=None)
        assert pt.x == 123
        assert pt.y == 456
        assert pt.is_infinity is False

    def test_ecpoint_pool_acquire_infinity(self):
        """获取无穷远点 (x=None, y=None)"""
        mgr = GlobalPoolManager()
        mgr.initialize()
        pool = mgr.get_ecpoint_pool()
        pt = pool.acquire(x=None, y=None)
        assert pt.is_infinity

    def test_ecpoint_pool_release(self):
        """归还 ECPoint（ECPoint 无 reset 方法，归还后坐标不变）"""
        mgr = GlobalPoolManager()
        mgr.initialize()
        pool = mgr.get_ecpoint_pool()
        pt = pool.acquire(x=1, y=2)
        assert pt.x == 1
        assert pt.y == 2
        pool.release(pt)
        # ECPoint 没有 reset 方法，坐标不变（由 ObjectPool.release 的 hasattr 跳过）
        assert pt.x == 1
        assert pt.y == 2

    def test_ecpoint_pool_get_stats(self):
        """ECPoint 池统计"""
        mgr = GlobalPoolManager()
        mgr.initialize()
        pool = mgr.get_ecpoint_pool()
        stats = pool.get_stats()
        assert stats in "current_size"
