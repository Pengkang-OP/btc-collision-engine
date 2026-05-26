"""Tests for GPUBatchScheduler."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.collision.gpu._scheduler import GPUBatchScheduler


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine._gpu_kernel = MagicMock()
    engine._device_manager = MagicMock()
    engine._device_manager.target_hash160s = b"\x00" * 20
    engine._device_manager.target_list = ["1ABC"]
    engine._stop_event = MagicMock()
    engine._last_memory_check_time = 0.0
    engine._memory_check_interval = 60
    engine._dynamic_speed_benchmark = 500000.0
    engine._adaptive_batch_enabled = True
    engine._last_batch_adjust_time = 0.0
    engine._batch_adjust_interval = 10.0
    engine._error_rate_threshold = 0.05
    engine._min_batch_size = 262144
    engine._max_batch_size = 2097152
    engine._last_progress_time = 0.0
    engine._progress_interval_sec = 0.5
    engine._consecutive_gpu_errors = 0
    engine._batch_size_lock = MagicMock()
    engine._engine_monitor = MagicMock()
    engine.gpu_performance_monitor = None
    engine.stats = MagicMock()
    engine.stats.snapshot.return_value = {
        "total_keys_checked": 1000,
        "elapsed_seconds": 1.0,
        "throughput": 1000.0,
        "total_matches": 0,
    }
    engine.stats.total_checked = 1000
    engine.stats.matches = []
    engine.stats.gpu_errors = 0
    engine.batch_size = 1000000
    engine.on_progress = None
    engine.event_bus = MagicMock()
    engine.checkpoint_mgr = None
    engine._current_mode = "random"
    engine.targets = {"1ABC"}
    engine._current_position = 0
    engine._range_start = None
    engine._range_end = None
    return engine


class TestGPUBatchScheduler:
    def test_init(self, mock_engine):
        scheduler = GPUBatchScheduler(mock_engine)
        assert scheduler._engine is mock_engine

    def test_calculate_gpu_memory_usage(self, mock_engine):
        scheduler = GPUBatchScheduler(mock_engine)
        usage = scheduler.calculate_gpu_memory_usage(1000000)
        assert isinstance(usage, float)
        assert usage > 0

    def test_calculate_dynamic_benchmark(self, mock_engine):
        scheduler = GPUBatchScheduler(mock_engine)
        scheduler.calculate_dynamic_benchmark()
        assert mock_engine._dynamic_speed_benchmark > 0

    def test_calculate_dynamic_benchmark_fallback(self, mock_engine):
        mock_engine._gpu_kernel.run_batch.side_effect = RuntimeError("GPU error")
        scheduler = GPUBatchScheduler(mock_engine)
        scheduler.calculate_dynamic_benchmark()
        assert mock_engine._dynamic_speed_benchmark == 500000.0

    def test_execute_batch_success(self, mock_engine):
        mock_engine._async_executor = None
        mock_engine._gpu_kernel.run_batch.return_value = []
        scheduler = GPUBatchScheduler(mock_engine)
        matches, exec_time = scheduler.execute_batch(b"seed" * 8, 1000000, 1)
        assert matches == []
        assert exec_time >= 0

    def test_execute_batch_retry_on_transient_error(self, mock_engine):
        mock_engine._async_executor = None
        mock_engine._gpu_kernel.run_batch.side_effect = [
            RuntimeError("out of resources"),
            [],
        ]
        scheduler = GPUBatchScheduler(mock_engine)
        matches, exec_time = scheduler.execute_batch(b"seed" * 8, 1000000, 1)
        assert matches == []

    def test_execute_batch_raises_on_non_transient(self, mock_engine):
        mock_engine._async_executor = None
        mock_engine._gpu_kernel.run_batch.side_effect = ValueError("invalid data")
        scheduler = GPUBatchScheduler(mock_engine)
        with pytest.raises(ValueError):
            scheduler.execute_batch(b"seed" * 8, 1000000, 1)

    def test_execute_batch_raises_on_max_retries(self, mock_engine):
        mock_engine._async_executor = None
        mock_engine._gpu_kernel.run_batch.side_effect = RuntimeError("out of resources")
        scheduler = GPUBatchScheduler(mock_engine)
        with pytest.raises(RuntimeError):
            scheduler.execute_batch(b"seed" * 8, 1000000, 1)

    def test_execute_batch_no_kernel(self, mock_engine):
        mock_engine._async_executor = None
        mock_engine._gpu_kernel = None
        scheduler = GPUBatchScheduler(mock_engine)
        with pytest.raises(RuntimeError, match="GPU内核不可用"):
            scheduler.execute_batch(b"seed" * 8, 1000000, 1)

    def test_check_memory_leaks(self, mock_engine):
        mock_engine._gpu_kernel._buffer_tracker = MagicMock()
        mock_engine._gpu_kernel._buffer_tracker.get_stats.return_value = {
            "count": 5,
            "total_size_mb": 100.0,
        }
        scheduler = GPUBatchScheduler(mock_engine)
        scheduler.check_memory_leaks()

    def test_check_and_report_progress(self, mock_engine):
        mock_engine._last_progress_time = 0.0
        mock_engine.stats.total_checked = 1000
        mock_engine.stats.gpu_errors = 0
        mock_engine.stats.snapshot.return_value = {
            "total_keys_checked": 1000,
            "elapsed_seconds": 1.0,
            "throughput": 1000.0,
            "total_matches": 0,
        }
        # Fix: engine.get_stats() returns self.stats (a MagicMock).
        # Configure get_stats to return a proper object with real int attributes
        # so that maybe_adjust_batch_size() can compare total_checked with int.

        class FakeStats:
            total_checked = 1000
            gpu_errors = 0

        mock_engine.get_stats.return_value = FakeStats()
        scheduler = GPUBatchScheduler(mock_engine)
        scheduler.check_and_report_progress(10, 1000000)
        assert mock_engine.event_bus.publish.called

    def test_save_checkpoint_no_manager(self, mock_engine):
        mock_engine.checkpoint_mgr = None
        scheduler = GPUBatchScheduler(mock_engine)
        scheduler.save_checkpoint(1000)

    def test_save_checkpoint_with_manager(self, mock_engine):
        mock_engine.checkpoint_mgr = MagicMock()
        mock_engine.checkpoint_mgr.should_auto_save = True
        scheduler = GPUBatchScheduler(mock_engine)
        scheduler.save_checkpoint(1000)
        assert mock_engine.checkpoint_mgr.save.called

    def test_maybe_adjust_batch_size_disabled(self, mock_engine):
        mock_engine._adaptive_batch_enabled = False
        scheduler = GPUBatchScheduler(mock_engine)
        scheduler.maybe_adjust_batch_size()

    def test_update_performance_metrics_no_monitor(self, mock_engine):
        mock_engine.gpu_performance_monitor = None
        scheduler = GPUBatchScheduler(mock_engine)
        scheduler.update_performance_metrics(1000000, 50.0)

    def test_resize_gpu_buffers(self, mock_engine):
        scheduler = GPUBatchScheduler(mock_engine)
        scheduler.resize_gpu_buffers(500000)
        assert mock_engine._gpu_kernel._max_batch_size == 500000
