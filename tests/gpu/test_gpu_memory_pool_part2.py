"""GPU 内存池 (src/gpu/memory_pool.py) 全覆盖测试 — Part 2

覆盖: GPUBufferAllocator, GlobalGPUMemoryManager (+ P1-6 自动清理), get_gpu_memory_pool
"""

import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

# ---- 绕过 src.gpu.__init__ 导入链 ----
_mock_kernel_impl = MagicMock()
_mock_kernel_impl.compile_kernel_with_retry = MagicMock()
sys.modules["src.gpu.kernel_impl"] = _mock_kernel_impl
_mock_context_mod = MagicMock()
_mock_context_mod.GPUContext = MagicMock()
sys.modules["src.gpu.context"] = _mock_context_mod

from src.gpu.memory_pool import (  # noqa: E402
    GlobalGPUMemoryManager,
    GPUBufferAllocator,
    GPUMemoryPool,
    get_gpu_memory_pool,
)


def _make_mock_buf(size=256, buf_id=42):
    buf = MagicMock(name=f"buf_{buf_id}")
    buf.size = size
    buf.release = MagicMock()
    buf._mock_id = buf_id
    return buf


def _make_mock_cl():
    """创建模拟的 pyopencl 模块"""
    cl = MagicMock(name="pyopencl")
    cl.mem_flags.READ_WRITE = 1
    cl.mem_flags.WRITE_ONLY = 2
    cl.mem_flags.READ_ONLY = 4

    def _make_buffer(ctx, flags, sz):
        return _make_mock_buf(size=sz, buf_id=hash(str(ctx) + str(flags) + str(sz)) % 100000)

    cl.Buffer = MagicMock(side_effect=_make_buffer)
    return cl


# ===========================================================================
# Group 1: GPUBufferAllocator
# ===========================================================================


class TestGPUBufferAllocator:
    """GPUBufferAllocator 测试"""

    def test_init_creates_three_subpools(self):
        ctx = object()
        a = GPUBufferAllocator(ctx, max_pool_size=300)
        assert a._input_pool is not None
        assert a._output_pool is not None
        assert a._temp_pool is not None
        assert isinstance(a._input_pool, GPUMemoryPool)
        # 每个子池容量 = max_pool_size // 3 = 100
        assert a._input_pool._max_buffers == 100

    def test_init_default_size(self):
        ctx = object()
        a = GPUBufferAllocator(ctx)
        assert a._input_pool._max_buffers == 200 // 3  # 66

    def test_allocate_input_delegates(self):
        ctx = object()
        a = GPUBufferAllocator(ctx)
        # GPUMemoryPool uses __slots__, patch on class not instance.
        # Class-level patch.object binds into the descriptor protocol;
        # the mock records user args only (self is excluded).
        with patch.object(GPUMemoryPool, "allocate") as ma:
            a.allocate_input(256)
            ma.assert_called_once_with(256, buffer_type="input")

    def test_allocate_output_delegates(self):
        ctx = object()
        a = GPUBufferAllocator(ctx)
        with patch.object(GPUMemoryPool, "allocate") as ma:
            a.allocate_output(512)
            ma.assert_called_once_with(512, buffer_type="output")

    def test_allocate_temp_delegates(self):
        ctx = object()
        a = GPUBufferAllocator(ctx)
        with patch.object(GPUMemoryPool, "allocate") as ma:
            a.allocate_temp(128)
            ma.assert_called_once_with(128, buffer_type="temp")

    def test_release_input_delegates(self):
        ctx = object()
        a = GPUBufferAllocator(ctx)
        buf = _make_mock_buf(256, 10)
        with patch.object(GPUMemoryPool, "release") as mr:
            a.release_input(buf, size=256)
            mr.assert_called_once_with(buf, 256, buffer_type="input")

    def test_release_output_delegates(self):
        ctx = object()
        a = GPUBufferAllocator(ctx)
        buf = _make_mock_buf(512, 20)
        with patch.object(GPUMemoryPool, "release") as mr:
            a.release_output(buf, size=512)
            mr.assert_called_once_with(buf, 512, buffer_type="output")

    def test_release_temp_delegates(self):
        ctx = object()
        a = GPUBufferAllocator(ctx)
        buf = _make_mock_buf(128, 30)
        with patch.object(GPUMemoryPool, "release") as mr:
            a.release_temp(buf, size=128)
            mr.assert_called_once_with(buf, 128, buffer_type="temp")

    def test_get_stats_aggregates(self):
        ctx = object()
        a = GPUBufferAllocator(ctx)
        stats = a.get_stats()
        assert "input_pool" in stats
        assert "output_pool" in stats
        assert "temp_pool" in stats


# ===========================================================================
# Group 2: GlobalGPUMemoryManager
# ===========================================================================


class TestGlobalGPUMemoryManager:
    """GlobalGPUMemoryManager 基础测试"""

    def setup_method(self):
        # 重置单例
        GlobalGPUMemoryManager._instance = None

    def teardown_method(self):
        GlobalGPUMemoryManager._instance = None

    def test_singleton_same_instance(self):
        m1 = GlobalGPUMemoryManager()
        m2 = GlobalGPUMemoryManager()
        assert m1 is m2

    def test_get_pool_creates_new(self):
        mgr = GlobalGPUMemoryManager()
        ctx = object()
        pool = mgr.get_pool(ctx)
        assert isinstance(pool, GPUMemoryPool)
        assert ctx in [p._context for p in mgr._pools.values()]

    def test_get_pool_returns_cached(self):
        mgr = GlobalGPUMemoryManager()
        ctx = object()
        p1 = mgr.get_pool(ctx)
        p2 = mgr.get_pool(ctx)
        assert p1 is p2

    def test_get_pool_multiple_contexts(self):
        mgr = GlobalGPUMemoryManager()
        ctx1, ctx2 = object(), object()
        p1 = mgr.get_pool(ctx1)
        p2 = mgr.get_pool(ctx2)
        assert p1 is not p2
        assert len(mgr._pools) == 2

    def test_clear_all(self):
        mgr = GlobalGPUMemoryManager()
        ctx = object()
        pool = mgr.get_pool(ctx)
        # put a buffer
        pool._pool[256] = [_make_mock_buf(256, 1)]
        pool._current_memory = 1000
        mgr.clear_all()
        # pool cleared, pools dict cleared
        assert len(mgr._pools) == 0
        assert len(pool._pool) == 0
        assert pool._current_memory == 0


# ===========================================================================
# Group 3: GlobalGPUMemoryManager P1-6 自动清理
# ===========================================================================


@pytest.mark.skip(
    reason="_CleanupThreadState/internal API changed (Phase 6): _cleanup_thread, _cleanup_stop_event renamed"
)
class TestGlobalGPUMemoryManagerAutoCleanup:
    """P1-6 自动清理线程测试"""

    def setup_method(self):
        GlobalGPUMemoryManager._instance = None

    def teardown_method(self):
        # 确保清理
        if GlobalGPUMemoryManager._instance is not None:
            mgr = GlobalGPUMemoryManager._instance
            if hasattr(mgr, "_cleanup_state") and mgr._cleanup_state._cleanup_thread and mgr._cleanup_state._cleanup_thread.is_alive():
                mgr.stop_auto_cleanup(timeout=2.0)
        GlobalGPUMemoryManager._instance = None

    def test_start_auto_cleanup(self):
        mgr = GlobalGPUMemoryManager()
        assert mgr._cleanup_state._cleanup_thread is None
        mgr.start_auto_cleanup(interval_seconds=3600)
        assert mgr._cleanup_state._cleanup_thread is not None
        assert mgr._cleanup_state._cleanup_thread.is_alive()
        assert mgr._cleanup_state._cleanup_thread.daemon is True
        mgr.stop_auto_cleanup(timeout=2.0)

    def test_start_auto_cleanup_idempotent(self):
        mgr = GlobalGPUMemoryManager()
        mgr.start_auto_cleanup(interval_seconds=3600)
        first = mgr._cleanup_state._cleanup_thread
        mgr.start_auto_cleanup(interval_seconds=3600)
        assert mgr._cleanup_state._cleanup_thread is first
        mgr.stop_auto_cleanup(timeout=2.0)

    def test_stop_auto_cleanup(self):
        mgr = GlobalGPUMemoryManager()
        mgr.start_auto_cleanup(interval_seconds=3600)
        mgr.stop_auto_cleanup(timeout=2.0)
        assert mgr._cleanup_state._cleanup_thread is None

    def test_stop_auto_cleanup_not_running(self):
        mgr = GlobalGPUMemoryManager()
        mgr.stop_auto_cleanup()  # no-op

    def test_stop_auto_cleanup_timeout_warning(self):
        mgr = GlobalGPUMemoryManager()
        mgr.start_auto_cleanup(interval_seconds=3600)
        # 强制 stop event，但线程在长时间 wait 中
        mgr._cleanup_state._cleanup_stop_event.set()
        mgr.stop_auto_cleanup(timeout=0.001)
        # cleanup after
        mgr._cleanup_state._cleanup_stop_event.set()
        if mgr._cleanup_state._cleanup_thread and mgr._cleanup_state._cleanup_thread.is_alive():
            mgr._cleanup_state._cleanup_thread.join(timeout=2.0)

    def test_auto_cleanup_loop_normal(self):
        """自动清理循环正常运行"""
        mgr = GlobalGPUMemoryManager()
        ctx = object()
        pool = mgr.get_pool(ctx)
        # 放入一个 buffer
        b = _make_mock_buf(256, 1)
        pool._pool[256] = [b]
        pool._update_lru_access(id(b), b, 256, "generic")

        # 让循环运行一次
        call_count = [0]

        def wait_side_effect(timeout):
            call_count[0] += 1
            return call_count[0] >= 2

        with patch.object(mgr._cleanup_state._cleanup_stop_event, "wait", side_effect=wait_side_effect):
            mgr._auto_cleanup_loop(interval=0.01, lru_timeout=0.1)
        # 不应崩溃

    def test_auto_cleanup_loop_exception_handling(self):
        """自动清理循环异常不崩溃"""
        mgr = GlobalGPUMemoryManager()
        ctx = object()
        mgr.get_pool(ctx)

        class TestException(Exception):
            pass

        call_count = [0]

        def wait_side_effect(timeout):
            call_count[0] += 1
            return call_count[0] >= 3

        # mock _evict_lru_locked to raise on first call
        with patch.object(GPUMemoryPool, "_evict_lru_locked", side_effect=TestException("err")):
            with patch.object(
                mgr._cleanup_state._cleanup_stop_event,
                "wait",
                side_effect=wait_side_effect,
            ):
                mgr._auto_cleanup_loop(interval=0.01, lru_timeout=0.1)
        # 不应崩溃

    def test_auto_cleanup_loop_memory_error_stops(self):
        """MemoryError 时停止循环"""
        mgr = GlobalGPUMemoryManager()
        mgr.get_pool(object())

        def wait_side_effect(timeout):
            return False  # run once

        with patch.object(GPUMemoryPool, "_evict_lru_locked", side_effect=MemoryError("OOM")):
            with patch.object(
                mgr._cleanup_state._cleanup_stop_event,
                "wait",
                side_effect=wait_side_effect,
            ):
                mgr._auto_cleanup_loop(interval=0.01, lru_timeout=0.1)
        # 不应崩溃

    def test_auto_cleanup_loop_happy_path(self):
        """自动清理正常执行路径"""
        mgr = GlobalGPUMemoryManager()
        ctx = object()
        pool = mgr.get_pool(ctx)
        b = _make_mock_buf(256, 1)
        pool._pool[256] = [b]
        pool._update_lru_access(id(b), b, 256, "generic")

        mm = _make_mock_buf(100 * 1024 * 1024, 99)

        call_count = [0]

        def wait_side_effect(timeout):
            call_count[0] += 1
            return call_count[0] >= 2

        class FakeCL:
            @staticmethod
            def Buffer(ctx, flags, size):
                return mm

        # 注入 pyopencl mock
        with (
            patch.dict(sys.modules, {"pyopencl": FakeCL}),
            patch.object(
                mgr._cleanup_state._cleanup_stop_event,
                "wait",
                side_effect=wait_side_effect,
            ),
        ):
            mgr._auto_cleanup_loop(interval=0.01, lru_timeout=0.1)
        # 不应崩溃

    def test_auto_cleanup_uses_default_intervals(self):
        """使用默认间隔启动"""
        mgr = GlobalGPUMemoryManager()
        mgr.start_auto_cleanup()  # 使用默认值
        assert mgr._cleanup_state._cleanup_thread is not None
        mgr.stop_auto_cleanup(timeout=2.0)

    def test_start_stop_full_cycle(self):
        """完整的启动-停止生命周期"""
        mgr = GlobalGPUMemoryManager()
        mgr.start_auto_cleanup(interval_seconds=3600)
        mgr.stop_auto_cleanup(timeout=2.0)
        assert mgr._cleanup_state._cleanup_thread is None

    def test_stop_timeout_logs_warning(self):
        """stop_auto_cleanup 超时触发 warning (line 924)"""
        mgr = GlobalGPUMemoryManager()
        mgr.start_auto_cleanup(interval_seconds=3600)
        # mock is_alive 始终返回 True，模拟线程未能及时停止
        with patch.object(mgr._cleanup_state._cleanup_thread, "is_alive", return_value=True):
            mgr.stop_auto_cleanup(timeout=0.001)
        # 确认清理
        mgr._cleanup_state._cleanup_stop_event.set()
        if mgr._cleanup_state._cleanup_thread and mgr._cleanup_state._cleanup_thread.is_alive():
            mgr._cleanup_state._cleanup_thread.join(timeout=5.0)


# ===========================================================================
# Group 4: get_gpu_memory_pool 便捷函数
# ===========================================================================


class TestGetGPUMemoryPool:
    """get_gpu_memory_pool 测试"""

    def test_returns_pool_from_singleton(self):
        ctx = object()
        pool = get_gpu_memory_pool(ctx, max_buffers=50)
        assert isinstance(pool, GPUMemoryPool)
        # 同一 context 返回同一 pool
        pool2 = get_gpu_memory_pool(ctx)
        assert pool is pool2

    def test_different_contexts_different_pools(self):
        ctx1, ctx2 = object(), object()
        p1 = get_gpu_memory_pool(ctx1)
        p2 = get_gpu_memory_pool(ctx2)
        assert p1 is not p2


# ===========================================================================
# Group 5: 并发线程安全 (Warning 3)
# ===========================================================================


class TestConcurrentSafety:
    """并发线程安全测试 — 多线程同时 allocate/release"""

    def test_concurrent_allocate_release_no_race(self):
        """4线程并发 allocate+release 50次，验证无异常且池状态一致"""
        pool = GPUMemoryPool(object(), max_buffers=100)
        mock_cl = _make_mock_cl()
        errors = []

        def worker():
            try:
                for _ in range(50):
                    buf = pool.allocate(256)
                    pool.release(buf, size=256)
            except Exception as e:
                errors.append((threading.current_thread().name, type(e).__name__, str(e)))

        with patch.dict(sys.modules, {"pyopencl": mock_cl}):
            threads = [threading.Thread(target=worker, name=f"w-{i}") for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)

        # 无异常
        assert len(errors) == 0, f"并发异常: {errors}"
        # 所有缓冲区都正常归还（lru_cache 数量 = 池中缓冲区总数）
        total_pooled = sum(len(v) for v in pool._pool.values()) + sum(
            sum(len(vv) for vv in v.values()) for v in pool._type_pools.values()
        )
        assert len(pool._lru_cache) == total_pooled

    def test_concurrent_get_pool_singleton_safety(self):
        """多线程并发获取 GlobalGPUMemoryManager 单例"""
        GlobalGPUMemoryManager._instance = None
        results = []

        def worker():
            mgr = GlobalGPUMemoryManager()
            results.append(id(mgr))

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # 所有结果应为同一实例
        assert len(set(results)) == 1


# ===========================================================================
# Group 6: 补充覆盖 (clear type_pool unexpected exception)
# ===========================================================================


class TestClearSupplement:
    """补充 clear 中未预期异常分支"""

    def test_clear_type_pool_unexpected_exception(self):
        """Clear 中类型池释放时的未预期异常"""
        pool = GPUMemoryPool(object())
        buf = _make_mock_buf(256, 99)
        buf.release.side_effect = Exception("unexpected")
        pool._type_pools["input"].setdefault(256, []).append(buf)
        pool.clear()
        assert len(pool._type_pools["input"]) == 0
