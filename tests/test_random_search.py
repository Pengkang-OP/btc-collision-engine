#!/usr/bin/env python3
"""随机搜索模式 (RandomSearchMode) 单元测试

覆盖：
- RandomSearchMode 初始化与种子预生成线程
- _generate_seed 种子获取（缓存命中/fallback）
- _seed_prefetch_worker 后台线程
- stop 停止线程与引擎
- _process_matches 匹配结果处理
- execute 模式分发
- 常量验证
"""

import pytest
from unittest.mock import patch, MagicMock

# ============================================================================
# 常量验证测试
# ============================================================================


@pytest.mark.unit
class TestConstants:
    """常量值验证测试"""

    def test_initial_batch_size(self):
        from src.gpu.search_modes.random_search import INITIAL_BATCH_SIZE

        assert INITIAL_BATCH_SIZE == 1_000_000

    def test_cpu_overload_threshold(self):
        from src.gpu.search_modes.random_search import CPU_OVERLOAD_THRESHOLD

        assert CPU_OVERLOAD_THRESHOLD == 90.0

    def test_cpu_throttle_sleep(self):
        from src.gpu.search_modes.random_search import CPU_THROTTLE_SLEEP

        assert CPU_THROTTLE_SLEEP == 0.02

    def test_min_batch_interval(self):
        from src.gpu.search_modes.random_search import MIN_BATCH_INTERVAL_SEC

        assert MIN_BATCH_INTERVAL_SEC == 0.001

    def test_exp_backoff_constants(self):
        from src.gpu.search_modes.random_search import EXP_BACKOFF_BASE, EXP_BACKOFF_MAX

        assert EXP_BACKOFF_BASE == 0.1
        assert EXP_BACKOFF_MAX == 30.0

    def test_seed_prefetch_size(self):
        from src.gpu.search_modes.random_search import SEED_PREFETCH_SIZE

        assert SEED_PREFETCH_SIZE == 5

    def test_exception_recovery_delay(self):
        from src.gpu.search_modes.random_search import EXCEPTION_RECOVERY_DELAY

        assert EXCEPTION_RECOVERY_DELAY == 0.1


# ============================================================================
# 辅助：创建 engine mock
# ============================================================================


def _make_engine_stub(**kwargs):
    """创建 GPUCollisionEngine stub，支持 __getattr__ 避免 MagicMock 无限递归"""
    engine = MagicMock()
    engine.targets = kwargs.get("targets", set())
    engine.batch_size = kwargs.get("batch_size", 1000000)
    engine._stop_event = threading_mock() if kwargs.get("has_stop_event", True) else None
    engine._running = kwargs.get("_running", True)
    engine._async_executor = kwargs.get("_async_executor", None)
    engine._gpu_kernel = kwargs.get("_gpu_kernel", None)
    engine._gpu_device = kwargs.get("_gpu_device", None)
    engine.stats = MagicMock()
    engine.stats.update = MagicMock()
    engine.stats.snapshot = MagicMock(return_value={})
    engine._execute_gpu_batch = kwargs.get("_execute_gpu_batch", MagicMock(return_value=([], 1.0)))
    engine._process_gpu_matches_prng = MagicMock()
    engine._update_performance_metrics = MagicMock()
    engine._check_and_report_progress = MagicMock()
    engine.on_complete = kwargs.get("on_complete", None)
    engine.on_match = kwargs.get("on_match", None)
    engine._on_match_found = kwargs.get("_on_match_found", None)
    return engine


def threading_mock():
    """创建支持 is_set() 的 Mock Event"""
    m = MagicMock()
    m.is_set.return_value = False
    return m


# ============================================================================
# RandomSearchMode 初始化测试
# ============================================================================


@pytest.mark.unit
class TestRandomSearchModeInit:
    """初始化测试"""

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_init_creates_seed_queue(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        mode = RandomSearchMode(engine)
        assert mode._seed_queue is not None
        assert mode._seed_queue.maxsize == 5  # SEED_PREFETCH_SIZE

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_init_starts_prefetch_thread(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        RandomSearchMode(engine)
        assert mock_thread.called
        # Thread started with daemon=True
        call_kwargs = mock_thread.call_args[1]
        assert call_kwargs.get("daemon") is True

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_init_custom_seed_prefetch_size(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        mode = RandomSearchMode(engine, seed_prefetch_size=10)
        assert mode._seed_prefetch_size == 10
        assert mode._seed_queue.maxsize == 10

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_init_stop_event_clear(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        mode = RandomSearchMode(engine)
        assert not mode._seed_stop_event.is_set()


# ============================================================================
# _generate_seed 测试
# ============================================================================


@pytest.mark.unit
class TestGenerateSeed:
    """种子生成测试"""

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_generate_from_cache(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        mode = RandomSearchMode(engine)
        # Put a seed in the queue
        expected_seed = b"cached_seed_32_bytes_long!!"
        mode._seed_queue.put(expected_seed)

        seed = mode._generate_seed()
        assert seed == expected_seed

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_generate_fallback_when_empty(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        mode = RandomSearchMode(engine)
        # Queue is empty → fallback to os.urandom()
        seed = mode._generate_seed()
        assert isinstance(seed, bytes)
        assert len(seed) == 32

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_generate_multiple_consume_cache(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        mode = RandomSearchMode(engine)
        # Fill with 3 seeds
        seeds = [f"seed_{i:0>27}".encode() for i in range(3)]
        for s in seeds:
            mode._seed_queue.put(s)

        # Should consume all 3 then fallback
        for i in range(3):
            seed = mode._generate_seed()
            assert seed == seeds[i]
        # 4th call falls back
        seed4 = mode._generate_seed()
        assert len(seed4) == 32


# ============================================================================
# _seed_prefetch_worker 测试
# ============================================================================


@pytest.mark.unit
class TestSeedPrefetchWorker:
    """后台预生成线程测试"""

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_worker_stops_on_stop_event(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        mode = RandomSearchMode(engine)
        # Simulate stop event already set
        mode._seed_stop_event.set()
        # Call worker directly - should exit immediately
        mode._seed_prefetch_worker()
        # Should not crash

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    @patch("src.gpu.search_modes.random_search.os.urandom")
    def test_worker_fills_queue(self, mock_urandom, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        mode = RandomSearchMode(engine)
        mock_urandom.return_value = b"A" * 32

        # Let worker run once then stop
        def stop_after_one():
            mode._seed_stop_event.set()

        mode._seed_stop_event = MagicMock()
        mode._seed_stop_event.is_set.side_effect = [False, True]

        mode._seed_prefetch_worker()

        # Seed should be in queue
        seed = mode._seed_queue.get_nowait()
        assert seed == b"A" * 32

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    @patch("src.gpu.search_modes.random_search.os.urandom")
    def test_worker_handles_oserror(self, mock_urandom, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        mode = RandomSearchMode(engine)
        mock_urandom.side_effect = [OSError("no entropy"), b"B" * 32]

        # Run two iterations
        mode._seed_stop_event = MagicMock()
        mode._seed_stop_event.is_set.side_effect = [False, False, True]

        mode._seed_prefetch_worker()

        # Second seed should be in queue (first errored)
        seed = mode._seed_queue.get_nowait()
        assert seed == b"B" * 32

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_worker_queue_full_no_block(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        mode = RandomSearchMode(engine, seed_prefetch_size=2)
        # Fill the queue
        mode._seed_queue.put(b"1" * 32)
        mode._seed_queue.put(b"2" * 32)

        # Run one iteration - queue is full, should skip
        mode._seed_stop_event = MagicMock()
        mode._seed_stop_event.is_set.side_effect = [False, True]

        mode._seed_prefetch_worker()
        # Worker should not crash when queue full


# ============================================================================
# stop 测试
# ============================================================================


@pytest.mark.unit
class TestStop:
    """停止测试"""

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_stop_sets_stop_event(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        mode = RandomSearchMode(engine)
        mode.stop()
        assert mode._seed_stop_event.is_set()

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_stop_joins_thread(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        mode = RandomSearchMode(engine)
        mock_thread_instance = mock_thread.return_value
        mock_thread_instance.is_alive.return_value = True

        mode.stop()

        mock_thread_instance.join.assert_called_once_with(timeout=2.0)

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_stop_thread_not_alive(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        mode = RandomSearchMode(engine)
        mock_thread_instance = mock_thread.return_value
        mock_thread_instance.is_alive.return_value = False

        mode.stop()

        assert mode._seed_thread is None

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_stop_sets_engine_stop_event(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        mode = RandomSearchMode(engine)
        mock_thread.return_value.is_alive.return_value = False

        mode.stop()

        engine._stop_event.set.assert_called_once()

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_stop_sets_engine_running_false(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        mode = RandomSearchMode(engine)
        mock_thread.return_value.is_alive.return_value = False

        mode.stop()

        assert engine._running is False


# ============================================================================
# _process_matches 测试
# ============================================================================


@pytest.mark.unit
class TestProcessMatches:
    """匹配结果处理测试"""

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_process_empty_matches(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        mode = RandomSearchMode(engine)
        mode._process_matches([], b"seed", 1000)  # Should not crash

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_process_match_with_private_key(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        engine._on_match_found = MagicMock()
        engine.stats.add_match = MagicMock()
        engine.on_match = MagicMock()

        mode = RandomSearchMode(engine)
        match = {"private_key": "abc123", "address": "1A1z..."}
        mode._process_matches([match], b"seed", 1000)

        engine._on_match_found.assert_called_once()
        engine.stats.add_match.assert_called_once_with("abc123", "1A1z...")
        engine.on_match.assert_called_once()

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_process_match_missing_key(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        engine._on_match_found = MagicMock()
        engine.stats.add_match = MagicMock()

        mode = RandomSearchMode(engine)
        match = {"private_key": None, "address": "1A1z..."}
        mode._process_matches([match], b"seed", 1000)

        engine._on_match_found.assert_not_called()

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_process_match_callback_exception(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        engine._on_match_found = MagicMock()
        engine.stats.add_match = MagicMock()
        engine.on_match = MagicMock(side_effect=RuntimeError("callback error"))

        mode = RandomSearchMode(engine)
        match = {"private_key": "key", "address": "addr"}
        mode._process_matches([match], b"seed", 1000)

        # Should not raise, just log error
        engine.on_match.assert_called_once()

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_process_matches_no_on_match(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        engine.on_match = None
        engine._on_match_found = MagicMock()

        mode = RandomSearchMode(engine)
        match = {"private_key": "key", "address": "addr"}
        mode._process_matches([match], b"seed", 1000)

        # Should not crash when on_match is None


# ============================================================================
# execute 分发测试
# ============================================================================


@pytest.mark.unit
class TestExecute:
    """执行模式分发测试"""

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_execute_async_when_executor_available(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub(
            _async_executor=MagicMock(),
            _gpu_kernel=MagicMock(),
        )
        mode = RandomSearchMode(engine)
        # Mock _execute_async to avoid actual execution
        mode._execute_async = MagicMock()
        mode.execute()
        mode._execute_async.assert_called_once()

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_execute_sync_when_no_executor(self, mock_thread):
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub(_async_executor=None)
        mode = RandomSearchMode(engine)
        mode._execute_sync = MagicMock()
        mode.execute()
        mode._execute_sync.assert_called_once()


# ============================================================================
# _execute_sync 部分逻辑测试
# ============================================================================


@pytest.mark.unit
class TestExecuteSyncPartial:
    """同步执行部分逻辑测试（不运行完整循环）"""

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_sync_cpu_overload_throttle(self, mock_thread):
        """验证 CPU 过载时节流逻辑被触发"""
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        # is_set calls: while-check, after batch_num, after seed_gen, while-check-exit
        engine._stop_event.is_set.side_effect = [False, False, False, True]
        engine._execute_gpu_batch.return_value = ([], 0.5)

        mode = RandomSearchMode(engine)

        with patch("psutil.cpu_percent", return_value=95.0):
            with patch("time.sleep") as mock_sleep:
                with patch("time.monotonic", side_effect=[0, 0.001, 0.002, 0.003]):
                    mode._execute_sync()

        # 验证节流生效：sleep 被调用过，且至少有一次参数为 0.02 (CPU_THROTTLE_SLEEP)
        assert mock_sleep.call_count >= 1, "Throttle should trigger at least one sleep"
        throttle_values = [c[0][0] for c in mock_sleep.call_args_list]
        assert 0.02 in throttle_values, "CPU throttle sleep should include 0.02s"

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_sync_stop_event_checked(self, mock_thread):
        """验证 _stop_event 被检查"""
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        engine._stop_event.is_set.return_value = True  # already stopped

        mode = RandomSearchMode(engine)
        mode._execute_sync()

        # Should exit immediately, not call batch
        engine._execute_gpu_batch.assert_not_called()

    @patch("src.gpu.search_modes.random_search.threading.Thread")
    def test_sync_exception_recovery(self, mock_thread):
        """验证异常恢复与退避"""
        from src.gpu.search_modes.random_search import RandomSearchMode

        engine = _make_engine_stub()
        # Need enough False to get past multiple is_set checks inside the loop
        # Before _execute_gpu_batch: while check, after batch_num++, after seed gen = at least 3
        # Then after exception, while check again → True to exit
        engine._stop_event.is_set.side_effect = [False, False, False, False, True]
        engine._execute_gpu_batch.side_effect = RuntimeError("GPU error")

        mode = RandomSearchMode(engine)

        with patch("time.sleep") as mock_sleep:
            mode._execute_sync()

        # Should have called sleep for backoff (at least once)
        assert mock_sleep.call_count >= 1
