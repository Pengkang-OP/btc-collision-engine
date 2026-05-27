"""Tests for GPU search modes (BruteForce, RangeScan, Random)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.gpu.search_modes.base_search import BaseSearchMode
from src.gpu.search_modes.brute_force_search import BruteForceSearchMode
from src.gpu.search_modes.random_search import RandomSearchMode
from src.gpu.search_modes.range_scan_search import RangeScanSearchMode


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine._device_manager = MagicMock()
    engine._device_manager.target_list = ["1ABC"]
    engine._device_manager.target_hash160s = b"\x00" * 20
    engine.stats = MagicMock()
    engine.stats.total_checked = 0
    engine.stats.matches = []
    engine.event_bus = MagicMock()
    engine._stop_event = MagicMock()
    engine._stop_event.is_set.return_value = False
    engine.batch_size = 1000000
    engine._batch_size = 1000000
    engine._batch_size_lock = MagicMock()
    engine._gpu_kernel = MagicMock()
    engine._gpu_kernel.run_batch.return_value = ([], 10.0)
    engine._scheduler = MagicMock()
    engine._scheduler.execute_batch.return_value = ([], 10.0)
    engine._result_processor = MagicMock()
    engine._current_position = 0
    engine._range_start = None
    engine._range_end = None
    engine._last_progress_time = 0.0
    engine._progress_interval_sec = 0.5
    engine._dynamic_speed_benchmark = 500000.0
    engine._consecutive_gpu_errors = 0
    engine._max_gpu_error_retries = 100
    engine._adaptive_batch_enabled = True
    engine._adaptive_error_count = 0
    engine._adaptive_batch_size = 1000000
    engine._min_batch_size = 262144
    engine._max_batch_size = 2097152
    engine._last_batch_adjust_time = 0.0
    engine._batch_adjust_interval = 10.0
    engine._error_rate_threshold = 0.05
    engine._engine_monitor = MagicMock()
    engine.gpu_performance_monitor = None
    engine.checkpoint_mgr = None
    engine.on_progress = None
    engine.on_match = None
    engine.on_complete = None
    engine.targets = {"1ABC"}
    engine._check_uncompressed = 0
    engine._core = MagicMock()
    engine._core.config = {}
    engine._search_coordinator = MagicMock()
    engine._perf_pipeline = None
    engine._random_search_mode = None
    engine._range_scan_mode = None
    engine._brute_force_mode = None
    engine._async_executor = None
    engine._gpu_device = MagicMock()
    engine._gpu_context = MagicMock()
    engine._gpu_memory_pool = None
    engine._current_mode = ""
    engine._running = False
    engine._thread = None
    engine.enhanced_monitoring = None
    engine.data_logger = None
    engine.dedup_filter = None
    return engine


class TestBaseSearchMode:
    def test_init(self, mock_engine):
        mode = BaseSearchMode(mock_engine)
        assert mode.engine is mock_engine

    def test_generate_sequential_keys(self, mock_engine):
        mode = BaseSearchMode(mock_engine)
        start_key = 12345
        keys = mode._generate_sequential_keys(start_key, 10)
        assert len(keys) == 10 * 32  # 每个私钥32字节
        # 验证第一个私钥
        first_key = int.from_bytes(keys[:32], "big")
        assert first_key == start_key

    def test_process_batch_matches_empty(self, mock_engine):
        mode = BaseSearchMode(mock_engine)
        mode._process_batch_matches([], b"\x01" * 32, None, "test")

    def test_process_batch_matches_with_matches(self, mock_engine):
        mode = BaseSearchMode(mock_engine)
        private_keys = b"\x01" * 64
        matches = [{"key_index": 0, "target_index": 0}]
        mode._process_batch_matches(matches, private_keys, None, "test")

    def test_handle_batch_error_oom(self, mock_engine):
        mode = BaseSearchMode(mock_engine)
        error = RuntimeError("out of memory")
        result = mode._handle_batch_error(error, "test")
        assert result is None

    def test_handle_batch_error_non_recoverable(self, mock_engine):
        mode = BaseSearchMode(mock_engine)
        error = ValueError("invalid data")
        result = mode._handle_batch_error(error, "test")
        assert result is None


class TestBruteForceSearchMode:
    def test_init(self, mock_engine):
        mode = BruteForceSearchMode(mock_engine)
        assert mode.engine is mock_engine


class TestRangeScanSearchMode:
    def test_init(self, mock_engine):
        mode = RangeScanSearchMode(mock_engine)
        assert mode.engine is mock_engine

    def test_execute_with_range(self, mock_engine):
        mode = RangeScanSearchMode(mock_engine)
        mode.execute(start=1000, end=2000)


class TestRandomSearchMode:
    def test_init(self, mock_engine):
        mode = RandomSearchMode(mock_engine)
        assert mode.engine is mock_engine

    def test_detect_gpu_model(self, mock_engine):
        mode = RandomSearchMode(mock_engine)
        model = mode._detect_gpu_model(mock_engine)
        assert model is not None

    def test_check_engine_availability(self, mock_engine):
        mock_engine._gpu_kernel = None
        mode = RandomSearchMode(mock_engine)
        available = mode._check_engine_availability(mock_engine)
        assert available is False
