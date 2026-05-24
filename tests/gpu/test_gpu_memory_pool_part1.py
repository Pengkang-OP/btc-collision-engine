"""GPU 内存池 (src/gpu/memory_pool.py) 全覆盖测试 — Part 1: GPUMemoryPool 核心

覆盖: __init__, allocate, release, preallocate_buffers, _evict_lru_locked,
      _evict_lru, _adjust_pool_size, _record_*, adapt_capacity, get_stats,
      get_pool_stats, clear, create_proportional_pools
"""

import sys
import time
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

# ---- 绕过 src.gpu.__init__ 导入链 ----
_mock_kernel_impl = MagicMock()
_mock_kernel_impl.compile_kernel_with_retry = MagicMock()
sys.modules["src.gpu.kernel_impl"] = _mock_kernel_impl
_mock_context_mod = MagicMock()
_mock_context_mod.GPUContext = MagicMock()
sys.modules["src.gpu.context"] = _mock_context_mod

from src.gpu.memory_pool import GPUMemoryPool  # noqa: E402
from src.gpu.memory_pool import logger as pool_logger  # noqa: E402


def _make_mock_buf(size=256, buf_id=42):
    buf = MagicMock(name=f"buf_{buf_id}")
    buf.size = size
    buf.release = MagicMock()
    buf._mock_id = buf_id
    return buf


def _make_mock_cl():
    cl = MagicMock(name="pyopencl")
    cl.mem_flags.READ_WRITE = 1
    cl.mem_flags.WRITE_ONLY = 2
    cl.mem_flags.READ_ONLY = 4

    def _make_buffer(ctx, flags, sz):
        return _make_mock_buf(size=sz, buf_id=hash(str(ctx) + str(flags) + str(sz)) % 100000)

    cl.Buffer = MagicMock(side_effect=_make_buffer)
    return cl


# ===========================================================================
# Group 1: __init__
# ===========================================================================


class TestInit:
    """GPUMemoryPool 初始化"""

    def test_basic_init(self):
        ctx = object()
        pool = GPUMemoryPool(ctx, max_buffers=50, max_memory_mb=256)
        assert pool._context is ctx
        assert pool._max_buffers == 50
        assert pool._max_memory_bytes == 256 * 1024 * 1024
        assert pool._enable_dynamic_adjustment is True
        assert pool._total_allocated == 0
        assert pool._current_memory == 0
        assert isinstance(pool._pool, dict)
        assert "input" in pool._type_pools
        assert isinstance(pool._access_times, dict)

    def test_init_dynamic_disabled(self):
        pool = GPUMemoryPool(object(), enable_dynamic_adjustment=False)
        assert pool._enable_dynamic_adjustment is False

    def test_init_max_memory_zero(self):
        pool = GPUMemoryPool(object(), max_memory_mb=0)
        assert pool._max_memory_bytes == 0

    def test_init_lru_tracking_empty(self):
        pool = GPUMemoryPool(object())
        assert len(pool._access_times) == 0
        assert len(pool._buf_by_id) == 0
        assert len(pool._buf_size_by_id) == 0
        assert len(pool._buf_type_by_id) == 0

    def test_preallocated_sizes_initially_empty(self):
        pool = GPUMemoryPool(object())
        assert isinstance(pool._preallocated_sizes, set)
        assert len(pool._preallocated_sizes) == 0


# ===========================================================================
# Group 2: allocate
# ===========================================================================


class TestAllocate:
    """allocate 测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.mock_cl = _make_mock_cl()
        self.ctx = object()

    def _pool(self, **kw):
        return GPUMemoryPool(self.ctx, **kw)

    def test_new_allocation(self):
        pool = self._pool()
        with patch.dict(sys.modules, {"pyopencl": self.mock_cl}):
            buf = pool.allocate(512)
        assert buf is not None
        assert pool._total_allocated == 1
        assert pool._allocation_count == 1

    def test_aligned_size_rounds_up(self):
        pool = self._pool()
        with patch.dict(sys.modules, {"pyopencl": self.mock_cl}):
            pool.allocate(500)
        # aligned to 512
        assert pool._allocation_patterns.get(512, 0) > 0

    def test_reuse_from_generic_pool(self):
        pool = self._pool()
        buf1 = _make_mock_buf(256, 100)
        pool._pool[256] = [buf1]
        pool._access_times[id(buf1)] = time.monotonic()
        pool._buf_by_id[id(buf1)] = buf1
        pool._buf_size_by_id[id(buf1)] = 256
        pool._buf_type_by_id[id(buf1)] = "generic"
        with patch.dict(sys.modules, {"pyopencl": self.mock_cl}):
            buf = pool.allocate(200)
        assert buf is buf1
        assert pool._total_reused == 1
        assert id(buf1) not in pool._access_times

    def test_reuse_from_type_pool(self):
        pool = self._pool()
        buf1 = _make_mock_buf(512, 200)
        pool._type_pools["input"][512] = [buf1]
        pool._access_times[id(buf1)] = time.monotonic()
        pool._buf_by_id[id(buf1)] = buf1
        pool._buf_size_by_id[id(buf1)] = 512
        pool._buf_type_by_id[id(buf1)] = "input"
        with patch.dict(sys.modules, {"pyopencl": self.mock_cl}):
            buf = pool.allocate(500, buffer_type="input")
        assert buf is buf1
        assert pool._total_reused == 1

    def test_flags_default_read_write(self):
        pool = self._pool()
        mc = _make_mock_cl()
        with patch.dict(sys.modules, {"pyopencl": mc}):
            pool.allocate(256)
        args, _ = mc.Buffer.call_args
        assert args[1] == 1

    def test_dynamic_adjustment_called_on_new(self):
        pool = self._pool(enable_dynamic_adjustment=True)
        with patch.dict(sys.modules, {"pyopencl": self.mock_cl}):
            with patch.object(type(pool), "_adjust_pool_size") as ma:
                pool.allocate(256)
                ma.assert_called_once()

    def test_dynamic_skipped_when_disabled(self):
        pool = self._pool(enable_dynamic_adjustment=False)
        with patch.dict(sys.modules, {"pyopencl": self.mock_cl}):
            with patch.object(type(pool), "_adjust_pool_size") as ma:
                pool.allocate(256)
                ma.assert_not_called()

    def test_record_memory_usage(self):
        pool = self._pool()
        with patch.dict(sys.modules, {"pyopencl": self.mock_cl}):
            pool.allocate(256)
        assert len(pool._memory_usage_history) >= 1

    def test_allocation_pattern_recorded(self):
        pool = self._pool()
        with patch.dict(sys.modules, {"pyopencl": self.mock_cl}):
            pool.allocate(300)  # aligned=512
        assert 512 in pool._allocation_patterns

    def test_type_pool_miss_then_generic_hit(self):
        """类型池未命中再查通用池"""
        pool = self._pool()
        buf1 = _make_mock_buf(256, 300)
        pool._pool[256] = [buf1]
        pool._access_times[id(buf1)] = time.monotonic()
        pool._buf_by_id[id(buf1)] = buf1
        pool._buf_size_by_id[id(buf1)] = 256
        pool._buf_type_by_id[id(buf1)] = "generic"
        # input 类型池无 256
        with patch.dict(sys.modules, {"pyopencl": self.mock_cl}):
            buf = pool.allocate(200, buffer_type="input")
        assert buf is buf1
        assert pool._total_reused == 1

    def test_pool_key_exists_but_empty_list_generic(self):
        """通用池键存在但列表为空 → fallthrough 到新建"""
        pool = self._pool()
        pool._pool[256] = []  # key exists, list empty
        mc = _make_mock_cl()
        with patch.dict(sys.modules, {"pyopencl": mc}):
            pool.allocate(250)  # aligned=256
        assert pool._total_allocated == 1
        assert pool._total_reused == 0

    def test_pool_key_exists_but_empty_list_type(self):
        """类型池键存在但列表为空 → fallthrough 到通用池/新建"""
        pool = self._pool()
        pool._type_pools["input"][256] = []  # key exists, list empty
        mc = _make_mock_cl()
        with patch.dict(sys.modules, {"pyopencl": mc}):
            pool.allocate(250, buffer_type="input")
        # 类型池空 → 查通用池空 → 新建
        assert pool._total_allocated == 1
        assert pool._total_reused == 0

    def test_allocate_with_explicit_flags(self):
        """allocate() 传入显式 flags，验证透传到 cl.Buffer"""
        pool = self._pool()
        mc = _make_mock_cl()
        with patch.dict(sys.modules, {"pyopencl": mc}):
            pool.allocate(256, flags=mc.mem_flags.READ_ONLY)
        args, _ = mc.Buffer.call_args
        assert args[1] == 4  # READ_ONLY


# ===========================================================================
# Group 3: release
# ===========================================================================


class TestRelease:
    """release 测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ctx = object()

    def _pool(self, **kw):
        return GPUMemoryPool(self.ctx, **kw)

    def test_release_with_size_generic(self):
        pool = self._pool()
        buf = _make_mock_buf(300, 42)
        pool.release(buf, size=300)
        aligned = 512
        assert aligned in pool._pool
        assert id(buf) in pool._access_times

    def test_release_with_size_type_pool(self):
        pool = self._pool()
        buf = _make_mock_buf(256, 55)
        pool.release(buf, size=256, buffer_type="input")
        assert 256 in pool._type_pools["input"]
        assert pool._buf_type_by_id[id(buf)] == "input"

    def test_release_size_none_from_buf_size(self):
        pool = self._pool()
        buf = _make_mock_buf(size=512, buf_id=77)
        pool.release(buf)
        assert 512 in pool._pool

    def test_release_size_none_from_underscore_size(self):
        pool = self._pool()
        buf = MagicMock(spec=[], name="buf_no_size")
        buf._size = 1024
        pool.release(buf)
        assert 1024 in pool._pool

    def test_release_size_none_no_size_attr_default_1024(self):
        pool = self._pool()
        buf = MagicMock(spec=[], name="buf_no_attrs")
        pool.release(buf)
        assert 1024 in pool._pool

    def test_release_size_none_exception_fallback_generic(self):
        pool = self._pool()
        buf = _make_mock_buf(buf_id=111)
        type(buf).size = PropertyMock(side_effect=ValueError("boom"))
        # 确保 _size 也抛异常
        type(buf)._size = PropertyMock(side_effect=AttributeError)
        pool.release(buf)
        assert "generic" in pool._pool

    def test_release_capacity_lru_eviction(self):
        pool = self._pool(max_buffers=5)
        for i in range(5):
            b = _make_mock_buf(256, 3000 + i)
            pool._pool.setdefault(256, []).append(b)
            pool._access_times[id(b)] = time.monotonic() - (5 - i) * 10
            pool._buf_by_id[id(b)] = b
            pool._buf_size_by_id[id(b)] = 256
            pool._buf_type_by_id[id(b)] = "generic"
        buf_new = _make_mock_buf(512, 4000)
        pool.release(buf_new, size=512)
        total = sum(len(v) for v in pool._pool.values())
        assert total <= 5

    def test_release_records_memory_usage(self):
        pool = self._pool()
        buf = _make_mock_buf(256, 66)
        old_len = len(pool._memory_usage_history)
        pool.release(buf, size=256)
        assert len(pool._memory_usage_history) > old_len

    def test_release_capacity_warning_logged(self):
        """S8: 池容量 ≥ 90% 时记录 warning 日志"""
        pool = self._pool(max_buffers=10)
        # 填充 9 个 → 90%
        for i in range(9):
            b = _make_mock_buf(256, 5000 + i)
            pool._pool.setdefault(256, []).append(b)
            pool._access_times[id(b)] = time.monotonic()
            pool._buf_by_id[id(b)] = b
            pool._buf_size_by_id[id(b)] = 256
            pool._buf_type_by_id[id(b)] = "generic"
        buf = _make_mock_buf(256, 6000)
        with patch.object(pool_logger, "warning") as mw:
            pool.release(buf, size=256)
            mw.assert_called_once()
            assert "90%" in mw.call_args[0][0] or "接近容量限制" in mw.call_args[0][0]


# ===========================================================================
# Group 4: preallocate_buffers
# ===========================================================================


class TestPreallocate:
    """preallocate_buffers 测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.mock_cl = _make_mock_cl()
        self.ctx = object()

    def _pool(self, **kw):
        return GPUMemoryPool(self.ctx, **kw)

    def test_preallocate_generic(self):
        pool = self._pool()
        with patch.dict(sys.modules, {"pyopencl": self.mock_cl}):
            pool.preallocate_buffers([256, 512], count_per_size=2)
        assert 256 in pool._preallocated_sizes
        assert pool._total_allocated == 4

    def test_preallocate_type_pool(self):
        pool = self._pool()
        with patch.dict(sys.modules, {"pyopencl": self.mock_cl}):
            pool.preallocate_buffers([1024], buffer_type="input")
        assert 1024 in pool._type_pools["input"]

    def test_preallocate_skip_duplicate(self):
        pool = self._pool()
        pool._preallocated_sizes.add(256)
        with patch.dict(sys.modules, {"pyopencl": self.mock_cl}):
            pool.preallocate_buffers([256])
        assert pool._total_allocated == 0

    def test_preallocate_exception_handling(self):
        pool = self._pool()
        mc = _make_mock_cl()
        mc.Buffer.side_effect = MemoryError("OOM")
        with patch.dict(sys.modules, {"pyopencl": mc}):
            pool.preallocate_buffers([512])
        assert pool._total_allocated == 0

    def test_preallocate_flags_custom(self):
        pool = self._pool()
        mc = _make_mock_cl()
        with patch.dict(sys.modules, {"pyopencl": mc}):
            pool.preallocate_buffers([256], flags=4)
        args, _ = mc.Buffer.call_args
        assert args[1] == 4


# ===========================================================================
# Group 5: _evict_lru_locked / _evict_lru
# ===========================================================================


class TestEvictLRU:
    """LRU 淘汰测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ctx = object()

    def _pool(self, **kw):
        return GPUMemoryPool(self.ctx, **kw)

    def test_evict_from_generic_pool(self):
        pool = self._pool()
        buf1, buf2 = _make_mock_buf(256, 10), _make_mock_buf(256, 20)
        pool._pool[256] = [buf1, buf2]
        pool._access_times[id(buf1)] = 100.0
        pool._access_times[id(buf2)] = 200.0
        pool._buf_by_id[id(buf1)] = buf1
        pool._buf_by_id[id(buf2)] = buf2
        pool._buf_size_by_id[id(buf1)] = 256
        pool._buf_size_by_id[id(buf2)] = 256
        pool._buf_type_by_id[id(buf1)] = "generic"
        pool._buf_type_by_id[id(buf2)] = "generic"
        evicted = pool._evict_lru_locked(count=1)
        assert evicted == 1
        assert id(buf1) not in pool._access_times
        assert id(buf2) in pool._access_times

    def test_evict_from_type_pool(self):
        pool = self._pool()
        buf1, buf2 = _make_mock_buf(512, 30), _make_mock_buf(512, 40)
        pool._type_pools["input"][512] = [buf1, buf2]
        pool._access_times[id(buf1)] = 50.0
        pool._access_times[id(buf2)] = 150.0
        pool._buf_by_id[id(buf1)] = buf1
        pool._buf_by_id[id(buf2)] = buf2
        pool._buf_size_by_id[id(buf1)] = 512
        pool._buf_size_by_id[id(buf2)] = 512
        pool._buf_type_by_id[id(buf1)] = "input"
        pool._buf_type_by_id[id(buf2)] = "input"
        evicted = pool._evict_lru_locked(count=1)
        assert evicted == 1
        assert id(buf1) not in pool._access_times
        assert id(buf2) in pool._access_times

    def test_evict_min_idle_seconds_filter(self):
        pool = self._pool()
        buf1, buf2 = _make_mock_buf(256, 50), _make_mock_buf(256, 60)
        now = time.monotonic()
        pool._pool[256] = [buf1, buf2]
        pool._access_times[id(buf1)] = now
        pool._access_times[id(buf2)] = now - 999
        pool._buf_by_id[id(buf1)] = buf1
        pool._buf_by_id[id(buf2)] = buf2
        pool._buf_size_by_id[id(buf1)] = 256
        pool._buf_size_by_id[id(buf2)] = 256
        pool._buf_type_by_id[id(buf1)] = "generic"
        pool._buf_type_by_id[id(buf2)] = "generic"
        evicted = pool._evict_lru_locked(count=2, min_idle_seconds=60)
        assert evicted == 1
        assert id(buf1) in pool._access_times
        assert id(buf2) not in pool._access_times

    def test_evict_min_idle_seconds_skip_in_type_pool(self):
        """min_idle_seconds 在类型池扫描中跳过符合条件的缓冲区 (line 408)"""
        pool = self._pool()
        now = time.monotonic()
        buf_recent = _make_mock_buf(256, 80)
        buf_old = _make_mock_buf(256, 81)
        # 类型池中有两个 buffer，generic 池为空
        pool._type_pools["input"][256] = [buf_recent, buf_old]
        pool._access_times[id(buf_recent)] = now  # 刚使用，应跳过
        pool._access_times[id(buf_old)] = now - 999  # 空闲很久
        pool._buf_by_id[id(buf_recent)] = buf_recent
        pool._buf_by_id[id(buf_old)] = buf_old
        pool._buf_size_by_id[id(buf_recent)] = 256
        pool._buf_size_by_id[id(buf_old)] = 256
        pool._buf_type_by_id[id(buf_recent)] = "input"
        pool._buf_type_by_id[id(buf_old)] = "input"
        evicted = pool._evict_lru_locked(count=2, min_idle_seconds=60)
        assert evicted == 1
        assert id(buf_recent) in pool._access_times  # 跳过
        assert id(buf_old) not in pool._access_times  # 淘汰

    def test_evict_untracked_buffer_with_min_idle(self):
        """S6: 池中缓冲区缺 _access_times 记录 + min_idle_seconds>0 → 仍被淘汰"""
        pool = self._pool()
        now = time.monotonic()
        buf_tracked = _make_mock_buf(256, 90)
        buf_untracked = _make_mock_buf(256, 91)
        # buf_untracked 在池中但 _access_times 无记录 (ts=0, 视为最旧)
        pool._pool[256] = [buf_tracked, buf_untracked]
        pool._access_times[id(buf_tracked)] = now  # 近期使用
        # buf_untracked 不加入 _access_times
        pool._buf_by_id[id(buf_tracked)] = buf_tracked
        pool._buf_by_id[id(buf_untracked)] = buf_untracked
        pool._buf_size_by_id[id(buf_tracked)] = 256
        pool._buf_size_by_id[id(buf_untracked)] = 256
        pool._buf_type_by_id[id(buf_tracked)] = "generic"
        pool._buf_type_by_id[id(buf_untracked)] = "generic"
        # min_idle_seconds=60: buf_tracked 在 60s 内应跳过, buf_untracked (ts=0) 被淘汰
        evicted = pool._evict_lru_locked(count=2, min_idle_seconds=60)
        assert evicted == 1
        assert id(buf_tracked) in pool._access_times
        # buf_untracked 不在 _access_times 记录中，应由 _buf_by_id 验证已清除
        assert id(buf_untracked) not in pool._buf_by_id

    def test_evict_no_candidates(self):
        pool = self._pool()
        assert pool._evict_lru_locked(count=5) == 0

    def test_evict_buffer_with_release(self):
        pool = self._pool()
        buf = _make_mock_buf(256, 70)
        pool._pool[256] = [buf]
        pool._access_times[id(buf)] = 0.0
        pool._buf_by_id[id(buf)] = buf
        pool._buf_size_by_id[id(buf)] = 256
        pool._buf_type_by_id[id(buf)] = "generic"
        pool._evict_lru_locked()
        buf.release.assert_called_once()

    def test_evict_buffer_without_release(self):
        pool = self._pool()
        buf = _make_mock_buf(256, 71)
        del buf.release
        pool._pool[256] = [buf]
        pool._access_times[id(buf)] = 0.0
        pool._buf_by_id[id(buf)] = buf
        pool._buf_size_by_id[id(buf)] = 256
        pool._buf_type_by_id[id(buf)] = "generic"
        pool._evict_lru_locked()
        assert id(buf) not in pool._access_times

    def test_evict_release_exception_handled(self):
        pool = self._pool()
        buf = _make_mock_buf(256, 72)
        buf.release.side_effect = RuntimeError("fail")
        pool._pool[256] = [buf]
        pool._access_times[id(buf)] = 0.0
        pool._buf_by_id[id(buf)] = buf
        pool._buf_size_by_id[id(buf)] = 256
        pool._buf_type_by_id[id(buf)] = "generic"
        assert pool._evict_lru_locked() == 1

    def test_evict_lru_thread_safe_wrapper(self):
        pool = self._pool()
        buf = _make_mock_buf(256, 73)
        pool._pool[256] = [buf]
        pool._access_times[id(buf)] = 0.0
        pool._buf_by_id[id(buf)] = buf
        pool._buf_size_by_id[id(buf)] = 256
        pool._buf_type_by_id[id(buf)] = "generic"
        pool._evict_lru()  # public wrapper
        assert id(buf) not in pool._access_times

    def test_evict_multiple_iterations(self):
        pool = self._pool()
        bufs = [None, None, None]
        for i in range(3):
            b = _make_mock_buf(256, i)
            bufs[i] = b
            pool._pool.setdefault(256, []).append(b)
            pool._access_times[id(b)] = float(i)
            pool._buf_by_id[id(b)] = b
            pool._buf_size_by_id[id(b)] = 256
            pool._buf_type_by_id[id(b)] = "generic"
        evicted = pool._evict_lru_locked(count=2)
        assert evicted == 2
        assert len(pool._access_times) == 1


# ===========================================================================
# Group 6: _adjust_pool_size
# ===========================================================================


class TestAdjustPoolSize:
    """动态调整测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ctx = object()

    def _pool(self, **kw):
        return GPUMemoryPool(self.ctx, max_memory_mb=256, **kw)

    def test_skip_if_not_enough_history(self):
        pool = self._pool()
        old_max = pool._max_memory_bytes
        pool._adjust_pool_size()
        assert pool._max_memory_bytes == old_max  # 未变化

    def test_skip_if_too_soon(self):
        pool = self._pool()
        pool._last_adjustment_time = time.monotonic() + 999  # 未来
        old_max = pool._max_memory_bytes
        pool._adjust_pool_size()
        assert pool._max_memory_bytes == old_max

    def test_expand_on_high_memory_usage(self):
        pool = self._pool()
        # 填充历史：平均内存 > 70%
        for _ in range(10):
            pool._memory_usage_history.append(
                {
                    "timestamp": time.monotonic(),
                    "current_memory_mb": pool._max_memory_bytes / (1024 * 1024) * 0.8,
                    "allocation_count": 1,
                    "reuse_rate": 0.5,
                },
            )
        pool._last_adjustment_time = 0  # 允许调整
        pool._adjust_pool_size()
        assert pool._max_memory_bytes > 256 * 1024 * 1024

    def test_no_expand_if_exceeds_2gb(self):
        pool = GPUMemoryPool(self.ctx, max_memory_mb=1500)
        for _ in range(10):
            pool._memory_usage_history.append(
                {
                    "timestamp": time.monotonic(),
                    "current_memory_mb": pool._max_memory_bytes / (1024 * 1024) * 0.8,
                    "allocation_count": 1,
                    "reuse_rate": 0.5,
                },
            )
        pool._last_adjustment_time = 0
        pool._adjust_pool_size()
        # 不应超过 2GB
        assert pool._max_memory_bytes <= 2 * 1024 * 1024 * 1024

    def test_low_usage_no_expand(self):
        pool = self._pool()
        for _ in range(10):
            pool._memory_usage_history.append(
                {
                    "timestamp": time.monotonic(),
                    "current_memory_mb": pool._max_memory_bytes / (1024 * 1024) * 0.3,
                    "allocation_count": 1,
                    "reuse_rate": 0.5,
                },
            )
        pool._last_adjustment_time = 0
        old_max = pool._max_memory_bytes
        pool._adjust_pool_size()
        assert pool._max_memory_bytes == old_max

    def test_allocation_pattern_logging(self):
        pool = self._pool()
        pool._allocation_count = 200
        pool._allocation_patterns = {512: 50, 1024: 30}
        for _ in range(10):
            pool._memory_usage_history.append(
                {
                    "timestamp": time.monotonic(),
                    "current_memory_mb": 10,
                    "allocation_count": 1,
                    "reuse_rate": 0.5,
                },
            )
        pool._last_adjustment_time = 0
        pool._adjust_pool_size()  # 不抛异常


# ===========================================================================
# Group 7: _record_*
# ===========================================================================


class TestRecordPatterns:
    """_record_allocation_pattern / _record_memory_usage"""

    def _pool(self):
        return GPUMemoryPool(object())

    def test_record_new_pattern(self):
        pool = self._pool()
        pool._record_allocation_pattern(512)
        assert pool._allocation_patterns[512] == 1

    def test_record_existing_pattern(self):
        pool = self._pool()
        pool._allocation_patterns[512] = 5
        pool._record_allocation_pattern(512)
        assert pool._allocation_patterns[512] == 6

    def test_record_memory_usage_basic(self):
        pool = self._pool()
        pool._current_memory = 1024 * 1024
        pool._total_allocated = 10
        pool._total_reused = 3
        pool._record_memory_usage()
        h = pool._memory_usage_history[-1]
        assert h["current_memory_mb"] == 1.0
        assert h["reuse_rate"] == 0.3

    def test_record_memory_trims_history(self):
        pool = self._pool()
        pool._memory_usage_history = [{}] * 100
        pool._record_memory_usage()
        assert len(pool._memory_usage_history) == 100


# ===========================================================================
# Group 8: adapt_capacity
# ===========================================================================


class TestAdaptCapacity:
    """adapt_capacity 测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.mock_cl = _make_mock_cl()

    def _pool(self, **kw):
        return GPUMemoryPool(object(), **kw)

    def test_skip_if_context_none(self):
        pool = self._pool()
        old_max = pool._max_buffers
        pool.adapt_capacity(context=None)
        assert pool._max_buffers == old_max

    def test_expand_on_successful_allocation(self):
        pool = self._pool(max_buffers=100)
        with patch.dict(sys.modules, {"pyopencl": self.mock_cl}):
            pool.adapt_capacity(context=object())
        assert pool._max_buffers == 200  # doubled, min(200, 500)

    def test_expand_capped_at_500(self):
        pool = self._pool(max_buffers=300)
        with patch.dict(sys.modules, {"pyopencl": self.mock_cl}):
            pool.adapt_capacity(context=object())
        assert pool._max_buffers == 500

    def test_shrink_on_allocation_failure(self):
        pool = self._pool(max_buffers=100)
        mc = _make_mock_cl()
        mc.Buffer.side_effect = MemoryError("OOM")
        with patch.dict(sys.modules, {"pyopencl": mc}):
            pool.adapt_capacity(context=object())
        assert pool._max_buffers == 50  # halved

    def test_shrink_minimum_20(self):
        pool = self._pool(max_buffers=30)
        mc = _make_mock_cl()
        mc.Buffer.side_effect = MemoryError("OOM")
        with patch.dict(sys.modules, {"pyopencl": mc}):
            pool.adapt_capacity(context=object())
        assert pool._max_buffers == 20  # max(15, 20)

    def test_shrink_calls_evict_lru(self):
        pool = self._pool(max_buffers=50)
        mc = _make_mock_cl()
        mc.Buffer.side_effect = MemoryError("OOM")
        with patch.dict(sys.modules, {"pyopencl": mc}), patch.object(type(pool), "_evict_lru") as mev:
            pool.adapt_capacity(context=object())
            mev.assert_called_once()

    def test_expand_noop_at_max_500(self):
        """S5: 已在 max_buffers=500 时扩展为无操作"""
        pool = self._pool(max_buffers=500)
        with patch.dict(sys.modules, {"pyopencl": self.mock_cl}):
            pool.adapt_capacity(context=object())
        # new_max = min(1000,500) = 500, == 当前 → 无变化
        assert pool._max_buffers == 500

    def test_shrink_noop_at_min_20(self):
        """S5: 已在 max_buffers=20 时收缩为无操作"""
        pool = self._pool(max_buffers=20)
        mc = _make_mock_cl()
        mc.Buffer.side_effect = MemoryError("OOM")
        with patch.dict(sys.modules, {"pyopencl": mc}):
            pool.adapt_capacity(context=object())
        # new_max = max(10,20) = 20, == 当前 → 无变化
        assert pool._max_buffers == 20


# ===========================================================================
# Group 9: get_stats / get_pool_stats
# ===========================================================================


class TestStats:
    """统计方法测试"""

    def _pool(self, **kw):
        return GPUMemoryPool(object(), **kw)

    def test_get_stats_basic(self):
        pool = self._pool()
        pool._total_allocated = 10
        pool._total_reused = 5
        pool._current_memory = 1024 * 1024
        stats = pool.get_stats()
        assert stats["total_allocated"] == 10
        assert stats["reuse_rate"] == 0.5
        assert stats["current_memory_mb"] == 1.0
        assert stats["pooled_buffers"] == 0

    def test_get_stats_reuse_rate_zero_division(self):
        pool = self._pool()
        stats = pool.get_stats()
        assert stats["reuse_rate"] == 0.0  # 0/1

    def test_get_stats_type_breakdown(self):
        pool = self._pool()
        buf = _make_mock_buf(256, 99)
        pool._type_pools["input"].setdefault(256, []).append(buf)
        stats = pool.get_stats()
        assert stats["type_stats"]["input"] == 1

    def test_get_pool_stats_basic(self):
        pool = self._pool()
        pool._max_memory_bytes = 512 * 1024 * 1024
        s = pool.get_pool_stats()
        assert s["max_memory_mb"] == 512.0
        assert "type_stats" in s
        assert "memory_usage_history" in s
        assert "allocation_patterns" in s

    def test_get_pool_stats_with_type_data(self):
        pool = self._pool()
        buf = _make_mock_buf(256, 88)
        pool._type_pools["temp"].setdefault(256, []).append(buf)
        pool._access_times[88] = time.monotonic()
        pool._buf_by_id[88] = buf
        pool._buf_size_by_id[88] = 256
        pool._buf_type_by_id[88] = "temp"
        s = pool.get_pool_stats()
        assert s["total_buffers"] == 1
        assert s["type_stats"]["temp"] == 1

    def test_get_pool_stats_allocation_patterns_sorted(self):
        pool = self._pool()
        pool._allocation_patterns = {256: 5, 512: 10, 1024: 3}
        s = pool.get_pool_stats()
        patterns = s["allocation_patterns"]
        first_key = next(iter(patterns))
        assert first_key == 512  # 最大 count

    def test_get_pool_stats_truncates_top_10(self):
        """S7: allocation_patterns > 10 时截断为 top 10"""
        pool = self._pool()
        # 创建 15 个不同大小的 pattern
        for i in range(15):
            pool._allocation_patterns[(i + 1) * 256] = i + 1
        s = pool.get_pool_stats()
        patterns = s["allocation_patterns"]
        assert len(patterns) == 10  # 截断为 10
        # 最大 count 应是 15 (size 3840 = 15*256)
        first_key = next(iter(patterns))
        assert first_key == 3840


# ===========================================================================
# Group 10: clear
# ===========================================================================


class TestClear:
    """clear 测试"""

    def _pool(self, **kw):
        return GPUMemoryPool(object(), **kw)

    def test_clear_empties_pools(self):
        pool = self._pool()
        buf1, buf2 = _make_mock_buf(256, 1), _make_mock_buf(512, 2)
        pool._pool[256] = [buf1]
        pool._pool[512] = [buf2]
        pool._type_pools["input"].setdefault(256, []).append(_make_mock_buf(256, 3))
        pool._current_memory = 1000
        pool._memory_usage_history = [{"a": 1}]
        pool._allocation_patterns = {256: 5}
        pool.clear()
        assert len(pool._pool) == 0
        assert len(pool._type_pools["input"]) == 0
        assert pool._current_memory == 0
        assert len(pool._memory_usage_history) == 0
        assert len(pool._allocation_patterns) == 0
        assert len(pool._access_times) == 0

    def test_clear_release_exception_handled(self):
        pool = self._pool()
        buf = _make_mock_buf(256, 5)
        buf.release.side_effect = RuntimeError("release err")
        pool._pool[256] = [buf]
        pool.clear()  # 不应抛出
        assert len(pool._pool) == 0

    def test_clear_release_unexpected_exception_handled(self):
        pool = self._pool()
        buf = _make_mock_buf(256, 6)
        buf.release.side_effect = Exception("unknown err")
        pool._pool[256] = [buf]
        pool.clear()
        assert len(pool._pool) == 0

    def test_clear_type_pool_release_exception(self):
        pool = self._pool()
        buf = _make_mock_buf(256, 7)
        buf.release.side_effect = RuntimeError("type err")
        pool._type_pools["input"].setdefault(256, []).append(buf)
        pool.clear()
        assert len(pool._type_pools["input"]) == 0


# ===========================================================================
# Group 11: create_proportional_pools (classmethod)
# ===========================================================================


class TestProportionalPools:
    """create_proportional_pools 类方法测试"""

    def test_empty_devices_returns_empty(self):
        pools = GPUMemoryPool.create_proportional_pools([])
        assert pools == {}

    def test_zero_total_vram_equal_split(self):
        devices = [
            {"name": "GPU0", "global_mem_size": 0},
            {"name": "GPU1", "global_mem_size": 0},
        ]
        pools = GPUMemoryPool.create_proportional_pools(devices, total_pool_mb=512)
        assert len(pools) == 2
        # 均分: 512/2 = 256MB each
        assert pools[0]._max_memory_bytes == 256 * 1024 * 1024
        assert pools[1]._max_memory_bytes == 256 * 1024 * 1024

    def test_proportional_by_vram(self):
        devices = [
            {"name": "GPU0", "global_mem_size": 4 * 1024**3},
            {"name": "GPU1", "global_mem_size": 1 * 1024**3},
        ]
        pools = GPUMemoryPool.create_proportional_pools(devices, total_pool_mb=500)
        assert len(pools) == 2
        # GPU0: 80%, GPU1: 20%
        assert pools[0]._max_memory_bytes > pools[1]._max_memory_bytes

    def test_minimum_64mb_per_device(self):
        devices = [
            {"name": "GPU0", "global_mem_size": 100 * 1024**3},
            {"name": "GPU1", "global_mem_size": 1},  # 极小显存
        ]
        pools = GPUMemoryPool.create_proportional_pools(devices, total_pool_mb=100)
        assert pools[1]._max_memory_bytes >= 64 * 1024 * 1024

    def test_with_contexts(self):
        ctx0, ctx1 = object(), object()
        devices = [
            {"name": "GPU0", "global_mem_size": 2 * 1024**3},
            {"name": "GPU1", "global_mem_size": 2 * 1024**3},
        ]
        pools = GPUMemoryPool.create_proportional_pools(
            devices, contexts=[ctx0, ctx1], total_pool_mb=256,
        )
        assert pools[0]._context is ctx0
        assert pools[1]._context is ctx1

    def test_contexts_shorter_than_devices(self):
        """Contexts 列表比 devices 短时，多余的用 None"""
        devices = [{"global_mem_size": 2 * 1024**3}, {"global_mem_size": 2 * 1024**3}]
        pools = GPUMemoryPool.create_proportional_pools(devices, contexts=[object()])
        assert pools[0]._context is not None
        assert pools[1]._context is None
