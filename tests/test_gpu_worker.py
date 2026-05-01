#!/usr/bin/env python3
"""GPU Worker 单元测试

覆盖 src/gpu/worker.py 中 SingleGPUWorker 的核心功能：
- 初始化与配置解析
- 线程控制 (stop/pause)
- 统计信息管理
- 模式处理 (random/range/brute_force)
- 边界条件与错误处理

不依赖真实 GPU 硬件，使用 Mock 替代。
"""

import pytest
import threading
from unittest.mock import Mock, patch

from src.gpu.gpu_config import WorkerConfig
from src.gpu.worker import SingleGPUWorker


@pytest.fixture
def worker_config():
    """默认测试用的 WorkerConfig"""
    return WorkerConfig(batch_size=65536, work_group_size=256)


@pytest.fixture
def sample_targets():
    """测试用目标地址集合"""
    return {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"}


class TestWorkerInit:
    """初始化测试"""

    def test_init_with_worker_config(self, worker_config, sample_targets):
        """测试使用 WorkerConfig 初始化"""
        worker = SingleGPUWorker(
            device_idx=0,
            key_range=(0, 1000000),
            targets=sample_targets,
            config=worker_config,
        )
        assert worker.device_idx == 0
        assert worker.key_range == (0, 1000000)
        assert worker.targets == sample_targets
        assert worker.config == worker_config
        assert worker.daemon is True
        assert worker._stats["status"] == "initialized"
        assert worker._stats["device_idx"] == 0

    def test_init_with_dict_config(self, sample_targets):
        """测试使用 Dict 初始化（兼容旧接口）"""
        config_dict = {"batch_size": 32768, "work_group_size": 128}
        worker = SingleGPUWorker(
            device_idx=0,
            key_range=(0, 1000000),
            targets=sample_targets,
            config=config_dict,
        )
        assert isinstance(worker.config, WorkerConfig)
        assert worker.config.batch_size == 32768
        assert worker.config.work_group_size == 128

    def test_init_with_result_callback(self, worker_config, sample_targets):
        """测试带回调函数的初始化"""
        callback = Mock()
        worker = SingleGPUWorker(
            device_idx=0,
            key_range=(0, 1000000),
            targets=sample_targets,
            config=worker_config,
            result_callback=callback,
        )
        assert worker.result_callback is callback

    def test_init_with_data_monitor(self, worker_config, sample_targets):
        """测试带数据监控器的初始化"""
        monitor = Mock()
        worker = SingleGPUWorker(
            device_idx=0,
            key_range=(0, 1000000),
            targets=sample_targets,
            config=worker_config,
            data_monitor=monitor,
        )
        assert worker.data_monitor is monitor

    def test_init_with_mode_random(self, worker_config, sample_targets):
        """测试 random 模式初始化"""
        worker = SingleGPUWorker(
            device_idx=0,
            key_range=(0, 1000000),
            targets=sample_targets,
            config=worker_config,
            mode="random",
        )
        assert worker.mode == "random"

    def test_init_with_mode_range(self, worker_config, sample_targets):
        """测试 range 模式初始化（带 range_start/range_end）"""
        worker = SingleGPUWorker(
            device_idx=0,
            key_range=(0, 1000000),
            targets=sample_targets,
            config=worker_config,
            mode="range",
            range_start=1000,
            range_end=9999,
        )
        assert worker.mode == "range"
        assert worker.range_start == 1000
        assert worker.range_end == 9999

    def test_init_with_mode_brute_force(self, worker_config, sample_targets):
        """测试 brute_force 模式初始化"""
        worker = SingleGPUWorker(
            device_idx=1,
            key_range=(0, 2**256 - 1),
            targets=sample_targets,
            config=worker_config,
            mode="brute_force",
            range_start=0,
        )
        assert worker.mode == "brute_force"
        assert worker.range_start == 0
        assert worker.range_end is None

    def test_init_creates_stop_event(self, worker_config, sample_targets):
        """初始化应创建未设置的 stop_event"""
        worker = SingleGPUWorker(
            device_idx=0,
            key_range=(0, 1000000),
            targets=sample_targets,
            config=worker_config,
        )
        assert not worker._stop_event.is_set()

    def test_init_creates_pause_event_set(self, worker_config, sample_targets):
        """初始化应创建已设置的 pause_event（初始为运行状态）"""
        worker = SingleGPUWorker(
            device_idx=0,
            key_range=(0, 1000000),
            targets=sample_targets,
            config=worker_config,
        )
        assert worker._pause_event.is_set()

    def test_init_creates_result_queue(self, worker_config, sample_targets):
        """初始化应创建空的结果队列"""
        worker = SingleGPUWorker(
            device_idx=0,
            key_range=(0, 1000000),
            targets=sample_targets,
            config=worker_config,
        )
        assert worker._result_queue.empty()

    def test_init_stats_have_required_keys(self, worker_config, sample_targets):
        """统计字典应包含所有必要键"""
        worker = SingleGPUWorker(
            device_idx=0,
            key_range=(0, 1000000),
            targets=sample_targets,
            config=worker_config,
        )
        expected_keys = {
            "device_idx",
            "status",
            "keys_checked",
            "matches_found",
            "start_time",
            "elapsed_time",
            "throughput",
            "error_count",
            "last_error",
        }
        assert expected_keys.issubset(worker._stats.keys())

    def test_init_different_device_indices(self, worker_config, sample_targets):
        """不同设备索引应正确存储"""
        for idx in [0, 1, 2, 7]:
            worker = SingleGPUWorker(
                device_idx=idx,
                key_range=(0, 100),
                targets=sample_targets,
                config=worker_config,
            )
            assert worker.device_idx == idx
            assert worker._stats["device_idx"] == idx


class TestThreadControl:
    """线程控制测试"""

    @pytest.fixture
    def worker(self, worker_config, sample_targets):
        return SingleGPUWorker(
            device_idx=0,
            key_range=(0, 1000000),
            targets=sample_targets,
            config=worker_config,
        )

    def test_stop_event_initially_clear(self, worker):
        """stop_event 初始状态为未设置"""
        assert not worker._stop_event.is_set()

    def test_pause_event_initially_set(self, worker):
        """pause_event 初始状态为已设置（允许运行）"""
        assert worker._pause_event.is_set()

    def test_stop_search_sets_event(self, worker):
        """stop_search() 应设置 stop_event"""
        assert not worker._stop_event.is_set()
        worker.stop_search()
        assert worker._stop_event.is_set()

    def test_pause_search_clears_event(self, worker):
        """pause_search() 应清除 pause_event"""
        assert worker._pause_event.is_set()
        worker.pause_search()
        assert not worker._pause_event.is_set()

    def test_resume_search_sets_event(self, worker):
        """resume_search() 应设置 pause_event"""
        worker._pause_event.clear()
        assert not worker._pause_event.is_set()
        worker.resume_search()
        assert worker._pause_event.is_set()

    def test_stop_search_multiple_times(self, worker):
        """多次 stop_search 不应崩溃"""
        worker.stop_search()
        worker.stop_search()
        worker.stop_search()
        assert worker._stop_event.is_set()

    def test_pause_resume_cycle(self, worker):
        """暂停/恢复循环"""
        assert worker._pause_event.is_set()
        worker.pause_search()
        assert not worker._pause_event.is_set()
        worker.resume_search()
        assert worker._pause_event.is_set()
        worker.pause_search()
        assert not worker._pause_event.is_set()
        worker.resume_search()
        assert worker._pause_event.is_set()


class TestStatsManagement:
    """统计管理测试"""

    @pytest.fixture
    def worker(self, worker_config, sample_targets):
        return SingleGPUWorker(
            device_idx=0,
            key_range=(0, 1000000),
            targets=sample_targets,
            config=worker_config,
        )

    def test_get_stats_returns_dict(self, worker):
        """get_stats 应返回字典"""
        stats = worker.get_stats()
        assert isinstance(stats, dict)

    def test_get_stats_includes_device_idx(self, worker):
        """get_stats 应包含 device_idx"""
        stats = worker.get_stats()
        assert stats["device_idx"] == 0

    def test_get_stats_status_initial(self, worker):
        """初始状态应为 'initialized'"""
        stats = worker.get_stats()
        assert stats["status"] == "initialized"

    def test_get_stats_keys_checked_zero(self, worker):
        """初始 keys_checked 应为 0"""
        stats = worker.get_stats()
        assert stats["keys_checked"] == 0

    def test_get_stats_matches_found_zero(self, worker):
        """初始 matches_found 应为 0"""
        stats = worker.get_stats()
        assert stats["matches_found"] == 0

    def test_get_stats_no_start_time(self, worker):
        """未启动时 start_time 应为 None"""
        stats = worker.get_stats()
        assert stats["start_time"] is None

    def test_get_stats_thread_safety(self, worker):
        """并发 get_stats 不应崩溃"""
        errors = []

        def getter():
            try:
                for _ in range(100):
                    worker.get_stats()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=getter) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_get_results_no_results(self, worker):
        """空队列时 get_results 应返回空列表"""
        assert worker.get_results() == []

    def test_worker_daemon_by_default(self, worker):
        """默认创建 daemon 线程"""
        assert worker.daemon is True

    def test_is_alive_before_start(self, worker):
        """启动前 is_alive() 应为 False"""
        assert not worker.is_alive()


class TestDeltaStatsIntegration:
    """增量统计集成测试"""

    def test_delta_stats_not_created_when_disabled(self, sample_targets):
        """当 delta_stats 功能禁用时不应创建 ThreadLocalDeltaStats"""
        with patch("src.gpu.worker._delta_stats_available", False):
            worker = SingleGPUWorker(
                device_idx=0,
                key_range=(0, 1000000),
                targets=sample_targets,
                config=WorkerConfig(),
            )
            assert worker._delta_stats is None

    def test_delta_stats_created_when_enabled(self, sample_targets):
        """当 delta_stats 功能启用时应创建 ThreadLocalDeltaStats"""
        with (
            patch("src.gpu.worker._delta_stats_available", True),
            patch("src.gpu.worker.ThreadLocalDeltaStats") as mock_stats_cls,
        ):
            mock_stats = Mock()
            mock_stats_cls.return_value = mock_stats
            worker = SingleGPUWorker(
                device_idx=0,
                key_range=(0, 1000000),
                targets=sample_targets,
                config=WorkerConfig(),
            )
            mock_stats_cls.assert_called_once()
            assert worker._delta_stats is mock_stats


class TestWorkerEdgeCases:
    """边界情况测试"""

    def test_zero_key_range(self, worker_config, sample_targets):
        """零长度 key_range"""
        worker = SingleGPUWorker(
            device_idx=0,
            key_range=(100, 100),  # start == end
            targets=sample_targets,
            config=worker_config,
        )
        assert worker.key_range == (100, 100)
        assert worker.device_idx == 0

    def test_max_device_index(self, worker_config, sample_targets):
        """大设备索引"""
        worker = SingleGPUWorker(
            device_idx=999,
            key_range=(0, 1000),
            targets=sample_targets,
            config=worker_config,
        )
        assert worker.device_idx == 999

    def test_empty_targets(self, worker_config):
        """空目标集合"""
        worker = SingleGPUWorker(
            device_idx=0,
            key_range=(0, 1000),
            targets=set(),
            config=worker_config,
        )
        assert len(worker.targets) == 0

    def test_no_result_callback(self, worker_config, sample_targets):
        """无回调函数时的初始化"""
        worker = SingleGPUWorker(
            device_idx=0,
            key_range=(0, 1000000),
            targets=sample_targets,
            config=worker_config,
        )
        assert worker.result_callback is None

    def test_very_large_key_range(self, worker_config, sample_targets):
        """极大 key_range（brute_force 全范围）"""
        full_range = 2**256 - 1
        worker = SingleGPUWorker(
            device_idx=0,
            key_range=(0, full_range),
            targets=sample_targets,
            config=worker_config,
            mode="brute_force",
        )
        assert worker.key_range == (0, full_range)
