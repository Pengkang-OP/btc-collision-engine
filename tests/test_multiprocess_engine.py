#!/usr/bin/env python3
"""多进程碰撞引擎 (MultiProcessCollisionEngine) 单元测试.

覆盖:
- MultiProcessCollisionEngine 初始化与参数
- start / stop / get_stats
- context manager 支持
- 内部状态管理
"""

import multiprocessing
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestMultiProcessEngineInit:
    """初始化测试."""

    def test_init_defaults(self):
        from src.collision.multiprocess_engine import MultiProcessCollisionEngine

        engine = MultiProcessCollisionEngine()
        assert engine._num_workers == multiprocessing.cpu_count()
        assert engine._running is False
        assert engine._task_queue is None
        assert engine._result_queue is None
        assert engine._processes == []
        assert engine._total_keys == 0
        assert engine._start_time is None

    def test_init_custom_config(self):
        from src.collision.multiprocess_engine import MultiProcessCollisionEngine

        engine = MultiProcessCollisionEngine(config={"max_workers": 4})
        assert engine._num_workers == 4

    def test_init_empty_config(self):
        from src.collision.multiprocess_engine import MultiProcessCollisionEngine

        engine = MultiProcessCollisionEngine(config={})
        assert engine._num_workers == multiprocessing.cpu_count()


@pytest.mark.unit
class TestMultiProcessEngineStart:
    """启动测试."""

    @patch("multiprocessing.Process")
    @patch("multiprocessing.Queue")
    def test_start_normal(self, mock_queue_cls, mock_process_cls):
        from src.collision.multiprocess_engine import MultiProcessCollisionEngine

        mock_queue = MagicMock()
        mock_queue_cls.return_value = mock_queue
        mock_process = MagicMock()
        mock_process_cls.return_value = mock_process

        engine = MultiProcessCollisionEngine(config={"max_workers": 2})
        engine.start()

        assert engine._running is True
        assert engine._task_queue is not None
        assert engine._result_queue is not None
        assert len(engine._processes) == 2
        assert mock_process_cls.call_count == 2
        assert mock_process.start.call_count == 2

    @patch("multiprocessing.Process")
    @patch("multiprocessing.Queue")
    def test_start_sets_start_time(self, mock_queue_cls, mock_process_cls):
        from src.collision.multiprocess_engine import MultiProcessCollisionEngine

        engine = MultiProcessCollisionEngine()
        assert engine._start_time is None
        engine.start()
        assert engine._start_time is not None


@pytest.mark.unit
class TestMultiProcessEngineStop:
    """停止测试."""

    def test_stop_not_started(self):
        from src.collision.multiprocess_engine import MultiProcessCollisionEngine

        engine = MultiProcessCollisionEngine()
        engine.stop()  # Should not crash when not running

    @patch("multiprocessing.Process")
    @patch("multiprocessing.Queue")
    def test_stop_terminates_workers(self, mock_queue_cls, mock_process_cls):
        from src.collision.multiprocess_engine import MultiProcessCollisionEngine

        mock_process = MagicMock()
        mock_process.is_alive.return_value = True
        mock_process_cls.return_value = mock_process

        engine = MultiProcessCollisionEngine(config={"max_workers": 2})
        engine.start()
        engine.stop()

        assert engine._running is False
        assert mock_process.terminate.call_count == 2
        assert mock_process.join.call_count == 2

    @patch("multiprocessing.Process")
    @patch("multiprocessing.Queue")
    def test_stop_already_terminated(self, mock_queue_cls, mock_process_cls):
        from src.collision.multiprocess_engine import MultiProcessCollisionEngine

        mock_process = MagicMock()
        mock_process.is_alive.return_value = False
        mock_process_cls.return_value = mock_process

        engine = MultiProcessCollisionEngine(config={"max_workers": 1})
        engine.start()
        engine.stop()

        assert engine._running is False
        # terminate() should not be called on already-dead processes
        mock_process.terminate.assert_not_called()


@pytest.mark.unit
class TestMultiProcessEngineGetStats:
    """统计信息测试."""

    def test_get_stats_empty(self):
        from src.collision.multiprocess_engine import MultiProcessCollisionEngine

        engine = MultiProcessCollisionEngine()
        stats = engine.get_stats()

        assert isinstance(stats, dict)
        assert stats["total_keys"] == 0
        assert stats["workers"] == multiprocessing.cpu_count()

    def test_get_stats_after_start(self):
        from src.collision.multiprocess_engine import MultiProcessCollisionEngine

        engine = MultiProcessCollisionEngine(config={"max_workers": 4})
        stats = engine.get_stats()

        assert stats["workers"] == 4
        assert isinstance(stats["total_keys"], (int, float))
        assert isinstance(stats["elapsed"], (int, float))


@pytest.mark.unit
class TestMultiProcessEngineWorkerLoop:
    """Worker 循环测试."""

    def test_worker_loop_exists(self):
        from src.collision.multiprocess_engine import MultiProcessCollisionEngine

        engine = MultiProcessCollisionEngine()
        assert hasattr(engine, "_worker_loop")
        assert callable(engine._worker_loop)
