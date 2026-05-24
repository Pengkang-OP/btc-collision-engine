#!/usr/bin/env python3
"""多进程碰撞引擎 (MultiprocessCollisionEngine / HybridCollisionEngine) 单元测试

覆盖：
- MultiprocessCollisionEngine 初始化与参数
- start / submit_task / get_results / get_stats / stop / is_running
- cleanup / 上下文管理器
- 加密传输 (enable_encryption)
- _cleanup_queues 内部方法
- create_multiprocess_engine / create_hybrid_engine 工厂函数
- HybridCollisionEngine 初始化/start/stop/get_stats/cleanup
- _worker_process 函数级测试
"""

from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# MultiprocessCollisionEngine 初始化测试
# ============================================================================


@pytest.mark.unit
class TestMultiprocessEngineInit:
    """初始化测试"""

    def test_init_defaults(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        assert engine.num_workers > 0  # defaults to cpu_count
        assert engine.batch_size == 10000
        assert engine.target_addresses == []
        assert engine.task_queue is None
        assert engine.result_queue is None
        assert engine.stats_queue is None
        assert engine.stop_event is None
        assert engine.workers == []
        assert engine.total_checked == 0
        assert engine.total_matches == []
        assert engine._running is False
        assert engine._enable_encryption is False

    def test_init_custom_workers(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine(num_workers=4)
        assert engine.num_workers == 4

    def test_init_custom_batch_size(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine(batch_size=50000)
        assert engine.batch_size == 50000

    def test_init_with_targets(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
        engine = MultiprocessCollisionEngine(target_addresses=targets)
        assert engine.target_addresses == targets

    def test_init_all_params(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "1HLoD9E4SDFFPDiYfNYnkBLQ85Y51J3Zb1"]
        engine = MultiprocessCollisionEngine(num_workers=2, batch_size=20000, target_addresses=targets)
        assert engine.num_workers == 2
        assert engine.batch_size == 20000
        assert len(engine.target_addresses) == 2


# ============================================================================
# MultiprocessCollisionEngine start 测试
# ============================================================================


@pytest.mark.unit
class TestMultiprocessEngineStart:
    """启动测试"""

    def test_start_already_running_returns_false(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        engine._running = True
        result = engine.start()
        assert result is False

    @patch("src.collision.multiprocess_engine.Process")
    @patch("src.collision.multiprocess_engine.mp.Event")
    @patch("src.collision.multiprocess_engine.Queue")
    def test_start_normal(self, mock_queue_cls, mock_event_cls, mock_process_cls):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        mock_queue = MagicMock()
        mock_queue_cls.return_value = mock_queue
        mock_event = MagicMock()
        mock_event_cls.return_value = mock_event
        mock_process = MagicMock()
        mock_process_cls.return_value = mock_process

        engine = MultiprocessCollisionEngine(num_workers=2)
        result = engine.start()

        assert result is True
        assert engine._running is True
        assert engine.task_queue is not None
        assert engine.result_queue is not None
        assert engine.stats_queue is not None
        assert engine.stop_event is not None
        assert len(engine.workers) == 2
        assert mock_process_cls.call_count == 2
        assert mock_process.start.call_count == 2

    @patch("src.collision.multiprocess_engine.Process")
    @patch("src.collision.multiprocess_engine.mp.Event")
    @patch("src.collision.multiprocess_engine.Queue")
    def test_start_with_encryption(self, mock_queue_cls, mock_event_cls, mock_process_cls):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        mock_queue = MagicMock()
        mock_queue_cls.return_value = mock_queue
        mock_event = MagicMock()
        mock_event_cls.return_value = mock_event
        mock_process = MagicMock()
        mock_process_cls.return_value = mock_process

        engine = MultiprocessCollisionEngine(num_workers=1)
        result = engine.start(enable_encryption=True)

        assert result is True
        assert engine._enable_encryption is True
        assert engine._encryption_key is not None

    @patch("src.collision.multiprocess_engine.Process")
    @patch("src.collision.multiprocess_engine.mp.Event")
    @patch("src.collision.multiprocess_engine.Queue")
    def test_start_encryption_no_cryptography(self, mock_queue_cls, mock_event_cls, mock_process_cls):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        mock_queue = MagicMock()
        mock_queue_cls.return_value = mock_queue
        mock_event = MagicMock()
        mock_event_cls.return_value = mock_event
        mock_process = MagicMock()
        mock_process_cls.return_value = mock_process

        engine = MultiprocessCollisionEngine(num_workers=1)
        # Block cryptography.fernet import inside start() to trigger ImportError path
        import sys

        with patch.dict(sys.modules, {"cryptography.fernet": None}):
            result = engine.start(enable_encryption=True)

        assert result is True
        assert engine._enable_encryption is False  # fallback to disabled

    @patch("src.collision.multiprocess_engine.Process")
    @patch("src.collision.multiprocess_engine.mp.Event")
    @patch("src.collision.multiprocess_engine.Queue")
    def test_start_with_sequential_generator(self, mock_queue_cls, mock_event_cls, mock_process_cls):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        mock_queue = MagicMock()
        mock_queue_cls.return_value = mock_queue
        mock_event = MagicMock()
        mock_event_cls.return_value = mock_event
        mock_process = MagicMock()
        mock_process_cls.return_value = mock_process

        engine = MultiprocessCollisionEngine(num_workers=1)
        result = engine.start(generator_func_name="sequential")
        assert result is True


# ============================================================================
# MultiprocessCollisionEngine submit_task 测试
# ============================================================================


@pytest.mark.unit
class TestSubmitTask:
    """任务提交测试"""

    def test_submit_not_running(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        engine.submit_task()
        # Should log warning but not crash

    def test_submit_with_default_batch_size(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine(batch_size=50000)
        engine._running = True
        engine.task_queue = MagicMock()

        engine.submit_task()

        engine.task_queue.put.assert_called_once()
        task = engine.task_queue.put.call_args[0][0]
        assert task["batch_size"] == 50000

    def test_submit_with_custom_batch_size(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine(batch_size=50000)
        engine._running = True
        engine.task_queue = MagicMock()

        engine.submit_task(batch_size=100000)

        task = engine.task_queue.put.call_args[0][0]
        assert task["batch_size"] == 100000

    def test_submit_queue_exception(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        engine._running = True
        engine.task_queue = MagicMock()
        engine.task_queue.put.side_effect = RuntimeError("queue full")

        # Should not raise
        engine.submit_task()


# ============================================================================
# MultiprocessCollisionEngine get_results 测试
# ============================================================================


@pytest.mark.unit
class TestGetResults:
    """结果收集测试"""

    def test_get_results_empty_queue(self):
        from multiprocessing.queues import Empty

        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        engine._running = True
        engine.result_queue = MagicMock()
        engine.result_queue.qsize.return_value = 0
        engine.result_queue.get.side_effect = Empty

        results = engine.get_results()
        assert results == []

    def test_get_results_with_matches(self):
        from multiprocessing.queues import Empty

        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        engine._running = True
        engine.result_queue = MagicMock()
        engine.result_queue.qsize.return_value = 0

        match_data = [{"private_key_hash": "abc123", "address": "1A...", "worker_id": 0}]
        engine.result_queue.get.side_effect = [match_data, Empty]

        results = engine.get_results()
        assert len(results) == 1
        assert results[0]["worker_id"] == 0
        assert len(engine.total_matches) == 1

    def test_get_results_encrypted_batch(self):
        from multiprocessing.queues import Empty

        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        engine._running = True
        engine._enable_encryption = True
        engine._encryption_key = b"a" * 32  # dummy key
        engine.result_queue = MagicMock()
        engine.result_queue.qsize.return_value = 0

        # Encrypted data should be bytes - decryption will fail with dummy key
        engine.result_queue.get.side_effect = [b"encrypted_data", Empty]

        # Should handle decryption error gracefully
        results = engine.get_results()
        assert results == []

    def test_get_results_queue_overflow_warning(self):
        from multiprocessing.queues import Empty

        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        engine._running = True
        engine.result_queue = MagicMock()
        engine.result_queue.qsize.return_value = 900  # > 800
        engine.result_queue.get.side_effect = Empty

        results = engine.get_results()
        assert results == []
        assert engine._queue_overflow_warnings == 1


# ============================================================================
# MultiprocessCollisionEngine get_stats 测试
# ============================================================================


@pytest.mark.unit
class TestGetStats:
    """统计信息测试"""

    def test_get_stats_empty(self):
        from multiprocessing.queues import Empty

        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine(num_workers=2)
        engine.stats_queue = MagicMock()
        engine.stats_queue.get_nowait.side_effect = Empty

        stats = engine.get_stats()
        assert stats["total_checked"] == 0
        assert stats["total_matches"] == 0
        assert stats["total_speed"] == 0
        assert stats["num_workers"] == 2
        assert isinstance(stats["worker_stats"], dict)
        assert isinstance(stats["matches"], list)

    def test_get_stats_with_worker_data(self):
        from multiprocessing.queues import Empty

        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine(num_workers=2)
        engine.stats_queue = MagicMock()

        worker_stats = [
            {
                "worker_id": 0,
                "total_checked": 50000,
                "matches_found": 2,
                "speed": 10000,
                "elapsed": 5.0,
            },
            {
                "worker_id": 1,
                "total_checked": 45000,
                "matches_found": 1,
                "speed": 9000,
                "elapsed": 5.0,
            },
        ]
        engine.stats_queue.get_nowait.side_effect = [worker_stats[0], worker_stats[1], Empty]

        stats = engine.get_stats()
        assert stats["total_checked"] == 95000
        assert stats["total_matches"] == 3
        assert stats["total_speed"] == 19000

    def test_get_stats_matches_returned_as_copy(self):
        from multiprocessing.queues import Empty

        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        engine.stats_queue = MagicMock()
        engine.stats_queue.get_nowait.side_effect = Empty
        engine.total_matches = [{"pk": "hash1"}]

        stats = engine.get_stats()
        # Should be a copy, not the same reference
        assert stats["matches"] is not engine.total_matches


# ============================================================================
# MultiprocessCollisionEngine stop 测试
# ============================================================================


@pytest.mark.unit
class TestStop:
    """停止测试"""

    def test_stop_not_running(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        engine.stop()  # Should do nothing, not crash

    def test_stop_sends_poison_pills(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine(num_workers=2)
        engine._running = True
        engine.stop_event = MagicMock()
        engine.task_queue = MagicMock()

        # Create mock workers that are not alive
        mock_worker = MagicMock()
        mock_worker.is_alive.return_value = False
        engine.workers = [mock_worker, mock_worker]

        engine.stop()

        engine.stop_event.set.assert_called_once()
        assert engine.task_queue.put.call_count >= 2  # poison pills
        assert engine._running is False

    def test_stop_zombie_processes(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine(num_workers=1)
        engine._running = True
        engine.stop_event = MagicMock()
        engine.task_queue = MagicMock()

        # Create a zombie worker
        mock_worker = MagicMock()
        mock_worker.is_alive.return_value = True
        mock_worker.exitcode = None
        mock_worker.pid = 12345
        engine.workers = [mock_worker]

        engine.stop()

        mock_worker.terminate.assert_called_once()
        assert engine._running is False


# ============================================================================
# is_running / cleanup / context manager 测试
# ============================================================================


@pytest.mark.unit
class TestIsRunning:
    """状态检查测试"""

    def test_not_running_initially(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        assert engine.is_running() is False

    def test_running_after_start(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        engine._running = True
        assert engine.is_running() is True


@pytest.mark.unit
class TestCleanup:
    """资源清理测试"""

    def test_cleanup_not_running(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        engine.cleanup()  # Should not crash

    @patch("src.collision.multiprocess_engine.Process")
    @patch("src.collision.multiprocess_engine.mp.Event")
    @patch("src.collision.multiprocess_engine.Queue")
    def test_cleanup_after_start(self, mock_q, mock_e, mock_p):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        mock_q.return_value = MagicMock()
        mock_e.return_value = MagicMock()

        mock_worker = MagicMock()
        mock_worker.is_alive.return_value = False
        mock_p.return_value = mock_worker

        engine = MultiprocessCollisionEngine(num_workers=1)
        engine.start()

        engine.cleanup()

        assert engine._running is False
        assert engine.workers == []
        assert engine.worker_stats == {}


@pytest.mark.unit
class TestContextManager:
    """上下文管理器测试"""

    def test_enter_returns_self(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        with engine as e:
            assert e is engine

    def test_exit_calls_cleanup(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        engine.cleanup = MagicMock()

        engine.__exit__(None, None, None)

        engine.cleanup.assert_called_once()

    def test_exit_does_not_suppress_exceptions(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        result = engine.__exit__(None, None, None)
        assert not result  # None/False both mean 'do not suppress exceptions'


# ============================================================================
# _cleanup_queues 内部方法测试
# ============================================================================


@pytest.mark.unit
class TestCleanupQueues:
    """队列清理内部方法测试"""

    def test_cleanup_empty_queues(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        mock_q = MagicMock()
        mock_q.empty.return_value = True
        engine.task_queue = mock_q
        engine.result_queue = mock_q
        engine.stats_queue = mock_q

        engine._cleanup_queues()
        # Should not raise

    def test_cleanup_queues_with_items(self):
        from src.collision.multiprocess_engine import MultiprocessCollisionEngine

        engine = MultiprocessCollisionEngine()
        mock_q = MagicMock()
        mock_q.empty.side_effect = [False, True]  # one item then empty
        engine.task_queue = mock_q
        engine.result_queue = mock_q
        engine.stats_queue = mock_q

        engine._cleanup_queues()
        # Should drain queues without error


# ============================================================================
# 工厂函数测试
# ============================================================================


@pytest.mark.unit
class TestFactoryFunctions:
    """工厂函数测试"""

    def test_create_multiprocess_engine(self):
        from src.collision.multiprocess_engine import (
            MultiprocessCollisionEngine,
            create_multiprocess_engine,
        )

        engine = create_multiprocess_engine(num_workers=4, batch_size=20000)
        assert isinstance(engine, MultiprocessCollisionEngine)
        assert engine.num_workers == 4
        assert engine.batch_size == 20000

    def test_create_multiprocess_engine_with_targets(self):
        from src.collision.multiprocess_engine import create_multiprocess_engine

        targets = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
        engine = create_multiprocess_engine(targets=targets)
        assert engine.target_addresses == targets

    def test_create_hybrid_engine_defaults(self):
        from src.collision.multiprocess_engine import (
            HybridCollisionEngine,
            create_hybrid_engine,
        )

        engine = create_hybrid_engine()
        assert isinstance(engine, HybridCollisionEngine)
        assert engine.use_multiprocess is True

    def test_create_hybrid_engine_with_params(self):
        from src.collision.multiprocess_engine import create_hybrid_engine

        engine = create_hybrid_engine(use_multiprocess=False, num_workers=8, batch_size=50000)
        assert engine.use_multiprocess is False
        assert engine.num_workers == 8
        assert engine.batch_size == 50000


# ============================================================================
# HybridCollisionEngine 测试
# ============================================================================


@pytest.mark.unit
class TestHybridEngineInit:
    """混合引擎初始化测试"""

    def test_init_defaults(self):
        from src.collision.multiprocess_engine import HybridCollisionEngine

        engine = HybridCollisionEngine()
        assert engine.use_multiprocess is True
        assert engine.num_workers is not None
        assert engine.batch_size == 10000
        assert engine.mp_engine is None
        assert engine.thread_engine is None

    def test_init_thread_mode(self):
        from src.collision.multiprocess_engine import HybridCollisionEngine

        engine = HybridCollisionEngine(use_multiprocess=False)
        assert engine.use_multiprocess is False


@pytest.mark.unit
class TestHybridEngineStart:
    """混合引擎启动测试"""

    @patch("src.collision.multiprocess_engine.Process")
    @patch("src.collision.multiprocess_engine.mp.Event")
    @patch("src.collision.multiprocess_engine.Queue")
    def test_start_multiprocess(self, mock_q, mock_e, mock_p):
        from src.collision.multiprocess_engine import HybridCollisionEngine

        mock_q.return_value = MagicMock()
        mock_e.return_value = MagicMock()
        mock_worker = MagicMock()
        mock_worker.is_alive.return_value = False
        mock_p.return_value = mock_worker

        engine = HybridCollisionEngine(use_multiprocess=True, num_workers=1)
        result = engine.start()

        assert result is True
        assert engine.mp_engine is not None

    def test_start_thread_mode(self):
        """线程模式启动：若 KeyCollisionEngine 可导入则验证 start 返回布尔值"""
        from src.collision.multiprocess_engine import HybridCollisionEngine

        # 显式跳过不可导入的模块，而非静默吞掉异常
        pytest.importorskip(
            "src.collision.key_collision",
            reason="KeyCollisionEngine 在当前环境不可导入",
        )
        engine = HybridCollisionEngine(use_multiprocess=False, num_workers=2)
        result = engine.start(targets=["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])
        assert isinstance(result, bool)


@pytest.mark.unit
class TestHybridEngineStop:
    """混合引擎停止测试"""

    def test_stop_both_engines(self):
        from src.collision.multiprocess_engine import HybridCollisionEngine

        engine = HybridCollisionEngine()
        engine.mp_engine = MagicMock()
        engine.thread_engine = MagicMock()

        engine.stop()

        engine.mp_engine.stop.assert_called_once()
        engine.thread_engine.stop.assert_called_once()

    def test_stop_only_mp_engine(self):
        from src.collision.multiprocess_engine import HybridCollisionEngine

        engine = HybridCollisionEngine()
        engine.mp_engine = MagicMock()
        engine.thread_engine = None

        engine.stop()

        engine.mp_engine.stop.assert_called_once()


@pytest.mark.unit
class TestHybridEngineGetStats:
    """混合引擎统计获取测试"""

    def test_get_stats_from_mp_engine(self):
        from src.collision.multiprocess_engine import HybridCollisionEngine

        engine = HybridCollisionEngine()
        engine.mp_engine = MagicMock()
        engine.mp_engine.get_stats.return_value = {"total_checked": 1000}

        stats = engine.get_stats()
        assert stats["total_checked"] == 1000

    def test_get_stats_from_thread_engine(self):
        from src.collision.multiprocess_engine import HybridCollisionEngine

        engine = HybridCollisionEngine()
        engine.mp_engine = None
        engine.thread_engine = MagicMock()
        engine.thread_engine.get_stats.return_value = {"total": 500}

        stats = engine.get_stats()
        assert stats["total"] == 500

    def test_get_stats_empty(self):
        from src.collision.multiprocess_engine import HybridCollisionEngine

        engine = HybridCollisionEngine()
        stats = engine.get_stats()
        assert stats == {}


@pytest.mark.unit
class TestHybridEngineCleanup:
    """混合引擎清理测试"""

    def test_cleanup_both(self):
        from src.collision.multiprocess_engine import HybridCollisionEngine

        engine = HybridCollisionEngine()
        engine.mp_engine = MagicMock()
        engine.thread_engine = MagicMock()

        engine.cleanup()

        engine.mp_engine.cleanup.assert_called_once()
        engine.thread_engine.stop.assert_called_once()

    def test_cleanup_none_set(self):
        from src.collision.multiprocess_engine import HybridCollisionEngine

        engine = HybridCollisionEngine()
        engine.cleanup()  # Should not crash


# ============================================================================
# _worker_process 函数级测试
# ============================================================================


@pytest.mark.unit
class TestWorkerProcessFunc:
    """_worker_process 函数测试"""

    def test_worker_function_exists(self):
        """验证 _worker_process 函数存在且可导入"""
        from src.collision.multiprocess_engine import _worker_process

        assert callable(_worker_process)
