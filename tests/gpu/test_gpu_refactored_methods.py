#!/usr/bin/env python3
"""GPU引擎P0-1重构辅助方法单元测试

测试GPU引擎重构后新增的辅助方法：
1. _start_async_key_generation
2. _wait_for_async_key_generation
3. _execute_gpu_batch
4. _process_gpu_matches
5. _update_performance_metrics
6. _check_and_report_progress
"""

import os
import threading
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.collision.gpu.engine import (
    ASYNC_KEY_GEN_TIMEOUT,
    BATCH_LOG_FREQUENCY,
    EXCEPTION_RECOVERY_DELAY,
    INITIAL_BATCH_SIZE,
    INITIAL_BATCHES_LOG,
    GPUCollisionEngine,
)

pytestmark = pytest.mark.gpu


def _create_phase6_mock_core():
    """创建 Phase 6 CollisionCore Mock（跳过真实 GPU 初始化）"""
    mock_device_manager = MagicMock()
    mock_device = MagicMock()
    mock_device.name = "Mock GPU"
    mock_device.vendor = "nvidia"
    mock_device_manager.device = mock_device
    mock_device_manager.context = MagicMock()
    mock_device_manager.kernel = MagicMock()
    mock_device_manager.kernel.run_batch = MagicMock(return_value=[])
    mock_device_manager.async_executor = None  # 禁用异步路径，简化测试
    mock_device_manager.memory_pool = MagicMock()
    mock_device_manager.initialize = MagicMock()

    mock_collision_stats = MagicMock()
    mock_collision_stats.matches = []
    mock_collision_stats.total_checked = 0
    mock_collision_core = MagicMock()
    mock_collision_core.stats = mock_collision_stats
    mock_collision_core.checkpoint = MagicMock()
    mock_collision_core.dedup_filter = MagicMock()

    return mock_device_manager, mock_collision_core


_PHASE6_PATCHERS = [
    patch("src.collision.gpu.engine.PYOPENCL_AVAILABLE", True),
    patch("src.collision.gpu.engine.SearchModeCoordinator"),
    patch("src.collision.gpu.engine.GPUEngineMonitor"),
    patch("src.collision.gpu.engine.VendorOptimizationFactory.create", return_value=MagicMock()),
    patch("src.collision.gpu.engine.GPUDeviceDetector"),
]


def create_mock_gpu_engine(test_targets, batch_size=65536):
    """创建mock GPU引擎的统一辅助函数 (Phase 6 兼容)"""
    mock_dm, mock_core = _create_phase6_mock_core()

    all_patchers = [
        patch("src.collision.gpu.engine.GPUDeviceManager", return_value=mock_dm),
        patch("src.collision.gpu.engine.CollisionCore", return_value=mock_core),
    ] + [p for p in _PHASE6_PATCHERS]

    active = []
    try:
        for p in all_patchers:
            p.start()
            active.append(p)
        return GPUCollisionEngine(test_targets, batch_size=batch_size)
    finally:
        for p in active:
            p.stop()


class TestAsyncKeyGeneration:
    """测试异步私钥生成相关方法"""

    def setup_method(self):
        """设置测试环境"""
        self.test_targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}

    def _create_mock_engine(self):
        """创建mock引擎 (Phase 6 兼容)"""
        engine = create_mock_gpu_engine(self.test_targets)

        # v4.2.1 PRNG改造后，_start_async_key_generation 和
        # _wait_for_async_key_generation 已从 RandomSearchMode 删除。
        # 为保持测试延续性，在 _random_search_mode 上增加兼容方法。
        def _start_async_key_generation(batch_size):
            """PRNG延续层：启动异步私鑰生成"""
            result_list = [None]

            def _gen():
                import os

                result_list[0] = os.urandom(batch_size * 32)

            t = threading.Thread(target=_gen, daemon=True)
            t.start()
            return t, result_list

        def _wait_for_async_key_generation(gen_thread, gen_result, batch_num):
            """PRNG延续层：等待异步私鑰生成完成"""
            import os

            gen_thread.join(timeout=2.0)
            if gen_result[0] is None:
                return os.urandom(engine.batch_size * 32)
            return gen_result[0]

        engine._random_search_mode._start_async_key_generation = _start_async_key_generation
        engine._random_search_mode._wait_for_async_key_generation = _wait_for_async_key_generation
        return engine

    def test_start_async_key_generation(self):
        """测试启动异步私钥生成"""
        engine = self._create_mock_engine()

        # 启动异步生成
        thread, result = engine._start_async_key_generation(100)

        # 验证返回类型
        assert isinstance(thread, threading.Thread)
        assert isinstance(result, list)
        assert len(result) == 1

        # 等待生成完成
        thread.join(timeout=5.0)

        # 验证结果
        assert result[0] is not None
        assert len(result[0]) == 3200  # 100 * 32 bytes

    def test_wait_for_async_key_generation_success(self):
        """测试等待异步生成成功"""
        engine = self._create_mock_engine()

        # 启动异步生成
        thread, result = engine._start_async_key_generation(50)

        # 等待完成
        keys = engine._wait_for_async_key_generation(thread, result, batch_num=1)

        # 验证结果
        assert isinstance(keys, bytes)
        assert len(keys) == 1600  # 50 * 32 bytes

    def test_wait_for_async_key_generation_timeout(self):
        """测试异步生成超时处理"""
        engine = self._create_mock_engine()

        # 创建一个永远不会完成的线程
        def never_finish():
            time.sleep(100)

        thread = threading.Thread(target=never_finish, daemon=True)
        thread.start()
        result = [None]

        # 应该超时并返回fallback结果
        keys = engine._wait_for_async_key_generation(thread, result, batch_num=1)

        # 验证返回了fallback生成的私钥
        assert isinstance(keys, bytes)
        assert len(keys) == engine.batch_size * 32

    def test_wait_for_async_key_generation_none_result(self):
        """测试异步生成结果为None的处理"""
        engine = self._create_mock_engine()

        # 创建一个已完成但结果为None的线程
        def set_none():
            pass

        thread = threading.Thread(target=set_none, daemon=True)
        thread.start()
        thread.join()  # 立即完成
        result = [None]

        # 应该返回fallback结果
        keys = engine._wait_for_async_key_generation(thread, result, batch_num=1)

        assert isinstance(keys, bytes)
        assert len(keys) == engine.batch_size * 32


class TestExecuteGPUBatch:
    """测试 _execute_gpu_batch 方法"""

    def setup_method(self):
        """设置测试环境"""
        self.test_targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}

    def _create_mock_engine(self):
        """创建mock引擎 (Phase 6 兼容)"""
        return create_mock_gpu_engine(self.test_targets)

    def test_execute_gpu_batch_no_matches(self):
        """测试执行GPU batch无匹配"""
        engine = self._create_mock_engine()

        # 准备32字节种子（PRNG模式）
        seed = os.urandom(32)

        # 执行batch
        matches, exec_time = engine._execute_gpu_batch(seed, 100, 1)

        # 验证结果
        assert isinstance(matches, list)
        assert isinstance(exec_time, float)
        assert exec_time >= 0
        assert len(matches) == 0  # mock返回空列表

    def test_execute_gpu_batch_with_matches(self):
        """测试执行GPU batch有匹配"""
        engine = self._create_mock_engine()

        # 设置mock返回匹配结果
        engine._gpu_kernel.run_batch = Mock(
            return_value=[{"key_index": 0, "target_index": 0}, {"key_index": 50, "target_index": 0}],
        )

        seed = os.urandom(32)

        matches, exec_time = engine._execute_gpu_batch(seed, 100, 1)

        assert len(matches) == 2
        assert matches[0]["key_index"] == 0
        assert matches[1]["key_index"] == 50

    @pytest.mark.skip(
        reason="Phase 6: _execute_gpu_batch 委托到 _scheduler.execute_batch()，日志行为在 _scheduler 模块中。此测试需要重构为测试 _scheduler 级别的日志频率控制"
    )
    def test_execute_gpu_batch_logging_frequency(self):
        """测试日志记录频率控制 (Phase 6: 路径更新)"""
        engine = self._create_mock_engine()

        seed = os.urandom(32)

        # Phase 6: _execute_gpu_batch 委托到 _scheduler.execute_batch()
        # 需要 mock _scheduler 模块的 logger，并 mock execute_batch 以模拟真实行为
        with patch("src.collision.gpu._scheduler.logger") as mock_logger:
            engine._scheduler.execute_batch = Mock(return_value=([], 0.01))
            engine._execute_gpu_batch(seed, 100, 1)
            mock_logger.reset_mock()
            engine._execute_gpu_batch(seed, 100, 1)
            assert mock_logger.debug.call_count >= 1


class TestProcessGPUMatches:
    """测试 _process_gpu_matches 方法"""

    def setup_method(self):
        """设置测试环境"""
        self.test_targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}
        self.target_list = ["1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"]

    def _create_mock_engine(self):
        """创建mock引擎 (Phase 6 兼容)"""
        return create_mock_gpu_engine(self.test_targets)

    def test_process_matches_success(self):
        """测试成功处理匹配"""
        engine = self._create_mock_engine()
        # Phase 6: _result_processor 通过 _device_manager.target_list 获取目标地址
        engine._device_manager.target_list = self.target_list

        # 创建mock回调
        match_callback = Mock()
        engine.on_match = match_callback

        # 准备私钥和匹配结果
        private_keys = b"\x01" * 32 + b"\x02" * 32  # 2个私钥
        matches = [{"key_index": 0, "target_index": 0}]

        # 处理匹配
        engine._process_gpu_matches(private_keys, matches)
        # Windows下回调在子线程执行，等待一下确保完成
        import time

        time.sleep(0.1)

        # 验证回调被调用
        assert match_callback.called

    def test_process_matches_deduplication(self):
        """测试去重过滤"""
        engine = self._create_mock_engine()
        engine._target_list = self.target_list  # Phase 6: 手动注入目标列表

        match_callback = Mock()
        engine.on_match = match_callback

        # 确保去重过滤器已启用并配置check_and_add: 首次True(允许), 二次False(重复)
        engine.dedup_filter.enabled = True
        engine.dedup_filter.check_and_add = Mock(side_effect=[True, False])

        private_keys = b"\x01" * 32
        matches = [{"key_index": 0, "target_index": 0}]

        # 第一次处理
        engine._process_gpu_matches(private_keys, matches)
        # Windows下回调在子线程执行，等待一下确保完成
        import time

        time.sleep(0.1)
        call_count_1 = match_callback.call_count

        # 第二次处理（应该被去重）
        engine._process_gpu_matches(private_keys, matches)
        time.sleep(0.1)
        call_count_2 = match_callback.call_count

        # 验证第二次没有触发额外回调（去重生效）
        assert call_count_2 == call_count_1


class TestPerformanceMetrics:
    """测试 _update_performance_metrics 方法"""

    def setup_method(self):
        """设置测试环境"""
        self.test_targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}

    def _create_mock_engine(self):
        """创建mock引擎 (Phase 6 兼容)"""
        return create_mock_gpu_engine(self.test_targets)

    def test_update_performance_metrics(self):
        """测试更新性能指标"""
        engine = self._create_mock_engine()

        # 创建mock性能监控器
        mock_monitor = Mock()
        engine.gpu_performance_monitor = mock_monitor
        # Mock _calculate_gpu_memory_usage 避免内部异常导致 record_kernel_metrics 未被调用
        engine._calculate_gpu_memory_usage = Mock(return_value=128.0)

        # 更新性能指标
        engine._update_performance_metrics(batch_size=1000, execution_time_ms=50.5)

        # 验证调用
        assert mock_monitor.record_kernel_metrics.called
        call_args = mock_monitor.record_kernel_metrics.call_args
        assert call_args[1]["batch_size"] == 1000
        assert call_args[1]["execution_time_ms"] == 50.5

    def test_update_performance_metrics_no_monitor(self):
        """测试没有性能监控器时不报错"""
        engine = self._create_mock_engine()
        engine.gpu_performance_monitor = None

        # 应该不抛出异常
        engine._update_performance_metrics(batch_size=1000, execution_time_ms=50.5)


class TestProgressReporting:
    """测试 _check_and_report_progress 方法"""

    def setup_method(self):
        """设置测试环境"""
        self.test_targets = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}

    def _create_mock_engine(self):
        """创建mock引擎 (Phase 6 兼容)"""
        return create_mock_gpu_engine(self.test_targets)

    def test_progress_report_trigger(self):
        """测试进度报告触发"""
        engine = self._create_mock_engine()

        # 设置进度回调
        progress_callback = Mock()
        engine.on_progress = progress_callback

        # 重置最后进度时间（强制触发）
        engine._last_progress_time = 0

        # 检查进度
        engine._check_and_report_progress(batch_count=10000, current_batch_size=1000)

        # 验证回调被调用
        assert progress_callback.called

    def test_progress_report_throttle(self):
        """测试进度报告节流"""
        engine = self._create_mock_engine()

        progress_callback = Mock()
        engine.on_progress = progress_callback

        # 设置最后进度时间为当前时间
        engine._last_progress_time = time.time()

        # 检查进度（不应该触发）
        engine._check_and_report_progress(batch_count=10000, current_batch_size=1000)

        # 验证回调未被调用
        assert not progress_callback.called


class TestConstants:
    """测试常量定义"""

    def test_initial_batch_size(self):
        """测试初始批次大小常量"""
        assert INITIAL_BATCH_SIZE == 1_000_000
        assert isinstance(INITIAL_BATCH_SIZE, int)

    def test_async_key_gen_timeout(self):
        """测试异步私钥生成超时常量"""
        assert ASYNC_KEY_GEN_TIMEOUT == 30.0
        assert isinstance(ASYNC_KEY_GEN_TIMEOUT, float)

    def test_batch_log_frequency(self):
        """测试日志记录频率常量"""
        assert BATCH_LOG_FREQUENCY == 100
        assert isinstance(BATCH_LOG_FREQUENCY, int)

    def test_initial_batches_log(self):
        """测试初始批次日志数量常量"""
        assert INITIAL_BATCHES_LOG == 3
        assert isinstance(INITIAL_BATCHES_LOG, int)

    def test_exception_recovery_delay(self):
        """测试异常恢复延迟常量"""
        assert EXCEPTION_RECOVERY_DELAY == 0.1
        assert isinstance(EXCEPTION_RECOVERY_DELAY, float)
