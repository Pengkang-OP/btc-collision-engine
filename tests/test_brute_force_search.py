#!/usr/bin/env python3
"""暴力穷举搜索模式 (BruteForceSearchMode) 单元测试

覆盖：
- execute 执行入口（start 起始值）
- _execute_batch_loop 委托调用
- _range_start 和 _current_position 设置
- gen_keys 闭包逻辑
- 引擎完成回调（on_complete）
- 边界值：start=0, start 大值, start 负值
- 引擎状态清理：_running=False
"""

from unittest.mock import MagicMock, patch

import pytest

from src.gpu.search_modes.brute_force_search import BruteForceSearchMode

# ============================================================================
# 辅助函数
# ============================================================================

def _make_engine_stub(**kwargs):
    """创建 GPUCollisionEngine stub"""
    engine = MagicMock()
    engine._stop_event = MagicMock()
    engine._stop_event.is_set.side_effect = kwargs.get(
        "stop_side_effect", [False, True]
    )
    engine._gpu_kernel = MagicMock()
    engine._gpu_kernel.run_batch.return_value = kwargs.get("run_batch_return", [])
    engine.stats = MagicMock()
    engine.stats.update = MagicMock()
    engine.stats.add_match = MagicMock()
    engine.stats.snapshot = MagicMock(return_value={})
    engine.on_match = kwargs.get("on_match", MagicMock())
    engine.on_progress = kwargs.get("on_progress")
    engine.on_complete = kwargs.get("on_complete")
    engine._target_list = kwargs.get("_target_list", ["target_addr"])
    engine.batch_size = kwargs.get("batch_size", 1000)
    engine._batch_size = kwargs.get("_batch_size", 1000)
    engine._batch_size_lock = MagicMock()
    engine._consecutive_gpu_errors = 0
    engine._max_gpu_error_retries = kwargs.get("_max_gpu_error_retries", 5)
    engine._last_progress_time = 0
    engine._progress_interval_sec = kwargs.get("_progress_interval_sec", 0.5)
    engine._save_checkpoint = MagicMock()
    engine._running = kwargs.get("_running", True)
    # BruteForce 特定属性
    engine._range_start = kwargs.get("_range_start", 0)
    engine._current_position = kwargs.get("_current_position", 0)
    return engine


# ============================================================================
# execute 测试
# ============================================================================

@pytest.mark.unit
@pytest.mark.gpu_kernel
class TestBruteForceExecute:
    """BruteForceSearchMode.execute 测试"""

    def test_execute_sets_range_start(self):
        """测试 execute 设置 _range_start"""
        engine = _make_engine_stub()
        mode = BruteForceSearchMode(engine)
        mode.execute(start=100)

        assert engine._range_start == 100

    def test_execute_sets_current_position(self):
        """测试 execute 设置 _current_position"""
        engine = _make_engine_stub(batch_size=100, stop_side_effect=[False, True])
        mode = BruteForceSearchMode(engine)
        mode.execute(start=42)

        # _current_position 经过一个批次后应被推进 batch_size
        assert engine._current_position == 42 + 100

    def test_execute_delegates_to_batch_loop(self):
        """测试 execute 委托给 _execute_batch_loop"""
        engine = _make_engine_stub(stop_side_effect=[False, True])

        mode = BruteForceSearchMode(engine)
        # Mock _execute_batch_loop 内部被调用
        with patch.object(mode, "_execute_batch_loop", wraps=mode._execute_batch_loop) as mock_loop:
            mode.execute(start=0)

        mock_loop.assert_called_once()

    def test_execute_sets_running_false(self):
        """测试 execute 完成后设置 _running=False"""
        engine = _make_engine_stub()

        mode = BruteForceSearchMode(engine)
        mode.execute(start=0)

        assert engine._running is False

    def test_execute_updates_stats(self):
        """测试 execute 更新统计信息"""
        engine = _make_engine_stub(stop_side_effect=[False, True])

        mode = BruteForceSearchMode(engine)
        mode.execute(start=0)

        engine.stats.update.assert_called()

    def test_execute_calls_on_complete(self):
        """测试 execute 调用 on_complete 回调"""
        engine = _make_engine_stub(on_complete=MagicMock())

        mode = BruteForceSearchMode(engine)
        mode.execute(start=0)

        engine.on_complete.assert_called_once()

    def test_execute_no_on_complete(self):
        """测试无 on_complete 回调时不崩溃"""
        engine = _make_engine_stub(on_complete=None)

        mode = BruteForceSearchMode(engine)
        # 不应抛出异常
        mode.execute(start=0)

    def test_execute_gen_keys_produces_correct_keys(self):
        """测试 gen_keys 闭包生成正确的私钥字节串"""
        engine = _make_engine_stub(
            batch_size=3,
            stop_side_effect=[False, True],
        )

        mode = BruteForceSearchMode(engine)

        # 捕获 gen_keys 的输出
        with patch.object(mode, "_generate_sequential_keys") as mock_gen:
            mock_gen.return_value = b"KEY" * 8  # 24 字节模拟
            mode.execute(start=10)

            # _generate_sequential_keys 用 start=10, batch_size=3 调用
            mock_gen.assert_called_once_with(10, 3)

    def test_execute_advances_current_position(self):
        """测试 gen_keys 闭包推进 _current_position"""
        engine = _make_engine_stub(
            batch_size=100,
            stop_side_effect=[False, True],
        )

        mode = BruteForceSearchMode(engine)
        # 在执行期间 _current_position 应被 gen_keys 推进
        mode.execute(start=0)

        # 执行完一个批次后 _current_position 应等于 batch_size
        assert engine._current_position == engine.batch_size


# ============================================================================
# 多批次执行
# ============================================================================

@pytest.mark.unit
@pytest.mark.gpu_kernel
class TestBruteForceMultiBatch:
    """多批次执行测试"""

    def test_multiple_batches(self):
        """测试多个批次执行"""
        engine = _make_engine_stub(
            batch_size=100,
            # 允许 3 个批次
            stop_side_effect=[False, False, False, True],
        )

        mode = BruteForceSearchMode(engine)
        mode.execute(start=0)

        # 3 个批次 * 100 = 300
        assert engine._current_position == 300
        assert engine._running is False

    def test_batches_advance_correctly(self):
        """测试每个批次后位置正确推进"""
        engine = _make_engine_stub(
            batch_size=50,
            stop_side_effect=[False, False, False, True],
        )

        mode = BruteForceSearchMode(engine)
        mode.execute(start=1000)

        # 从 1000 开始，3 个批次 * 50 = 150
        assert engine._current_position == 1150


# ============================================================================
# 边界值测试
# ============================================================================

@pytest.mark.unit
@pytest.mark.gpu_kernel
class TestBruteForceBoundary:
    """BroForceSearchMode 边界值测试"""

    def test_start_zero(self):
        """测试 start=0"""
        engine = _make_engine_stub()

        mode = BruteForceSearchMode(engine)
        mode.execute(start=0)

        assert engine._range_start == 0
        assert engine._current_position > 0
        assert engine._running is False

    def test_start_large_value(self):
        """测试大起始值"""
        engine = _make_engine_stub(
            batch_size=10,
            stop_side_effect=[False, True],
        )

        mode = BruteForceSearchMode(engine)
        mode.execute(start=2**250)

        assert engine._range_start == 2**250
        assert engine._current_position == 2**250 + 10

    def test_start_negative_raises(self):
        """测试负起始值抛出 struct.error（Q 格式不支持负数）"""
        import struct
        engine = _make_engine_stub(
            batch_size=10,
            stop_side_effect=[False, True],
        )

        mode = BruteForceSearchMode(engine)
        with pytest.raises(struct.error):
            mode.execute(start=-5)

    def test_zero_batch_size(self):
        """测试 batch_size=0（不应发生，但需处理）"""
        engine = _make_engine_stub(batch_size=0)

        mode = BruteForceSearchMode(engine)
        # _generate_sequential_keys(start, 0) 返回空 → gen_keys 返回 (b"", 0)
        # → _execute_batch_loop 检测空数据 → 跳出
        mode.execute(start=0)

        assert engine._running is False

    def test_single_element_batch(self):
        """测试 batch_size=1"""
        engine = _make_engine_stub(
            batch_size=1,
            stop_side_effect=[False, True],
        )

        mode = BruteForceSearchMode(engine)
        mode.execute(start=0)

        assert engine._current_position == 1
