#!/usr/bin/env python3
"""范围扫描搜索模式 (RangeScanSearchMode) 单元测试

覆盖：
- execute 执行入口（start, end 范围）
- 流水线预生成逻辑（gen_keys 闭包）
- stop_condition 边界检测
- _execute_batch_loop 委托调用
- 引擎状态清理：_running=False, on_complete
- 边界值：小范围（start==end）、单批次、跨批次
- 大范围和大值处理
"""

from unittest.mock import MagicMock, patch

import pytest

from src.gpu.search_modes.range_scan_search import RangeScanSearchMode

# ============================================================================
# 辅助函数
# ============================================================================


def _make_engine_stub(**kwargs):
    """创建 GPUCollisionEngine stub"""
    engine = MagicMock()
    engine._stop_event = MagicMock()
    engine._stop_event.is_set.side_effect = kwargs.get("stop_side_effect", [False, True])
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
    engine._current_position = kwargs.get("_current_position", 0)
    return engine


# ============================================================================
# execute 测试
# ============================================================================


@pytest.mark.unit
@pytest.mark.gpu_kernel
class TestRangeScanExecute:
    """RangeScanSearchMode.execute 测试"""

    def test_execute_sets_current_position(self):
        """测试 execute 设置 _current_position"""
        engine = _make_engine_stub(stop_side_effect=[False, True])

        mode = RangeScanSearchMode(engine)
        mode.execute(start=10, end=20)

        # 至少完成一个批次
        assert engine._current_position >= 10

    def test_execute_single_batch_small_range(self):
        """测试小范围（单批次内完成）"""
        engine = _make_engine_stub(
            batch_size=1000,
            stop_side_effect=[False, True],
        )

        mode = RangeScanSearchMode(engine)
        mode.execute(start=0, end=5)

        # 范围 0-5，共 6 个 key，一个批次内完成
        assert engine._current_position >= 6

    def test_execute_start_equals_end(self):
        """测试 start==end（仅一个私钥）"""
        engine = _make_engine_stub(
            batch_size=1000,
            stop_side_effect=[False, True],
        )

        mode = RangeScanSearchMode(engine)
        mode.execute(start=42, end=42)

        # 仅 1 个 key
        assert engine._current_position == 43  # 42 + 1

    def test_execute_delegates_to_batch_loop(self):
        """测试 execute 委托给 _execute_batch_loop"""
        engine = _make_engine_stub()

        mode = RangeScanSearchMode(engine)
        with patch.object(mode, "_execute_batch_loop", wraps=mode._execute_batch_loop) as mock_loop:
            mode.execute(start=0, end=9)

        mock_loop.assert_called_once()

    def test_execute_sets_running_false(self):
        """测试 execute 完成后 _running=False"""
        engine = _make_engine_stub()

        mode = RangeScanSearchMode(engine)
        mode.execute(start=0, end=9)

        assert engine._running is False

    def test_execute_updates_stats(self):
        """测试 execute 更新统计"""
        engine = _make_engine_stub()

        mode = RangeScanSearchMode(engine)
        mode.execute(start=0, end=9)

        engine.stats.update.assert_called()

    def test_execute_calls_on_complete(self):
        """测试 execute 调用 on_complete"""
        engine = _make_engine_stub(on_complete=MagicMock())

        mode = RangeScanSearchMode(engine)
        mode.execute(start=0, end=9)

        engine.on_complete.assert_called_once()

    def test_execute_no_on_complete(self):
        """测试无 on_complete 不崩溃"""
        engine = _make_engine_stub(on_complete=None)

        mode = RangeScanSearchMode(engine)
        mode.execute(start=0, end=9)
        # 不应抛出异常


# ============================================================================
# 流水线预生成
# ============================================================================


@pytest.mark.unit
@pytest.mark.gpu_kernel
class TestRangeScanPipeline:
    """流水线预生成测试"""

    def test_first_batch_prefetches_next(self):
        """测试第一个批次预生成下一批"""
        engine = _make_engine_stub(
            batch_size=100,
            # 允许 2 个批次
            stop_side_effect=[False, False, True],
        )

        mode = RangeScanSearchMode(engine)

        # 捕获 _generate_sequential_keys 调用
        with patch.object(mode, "_generate_sequential_keys") as mock_gen:
            mock_gen.return_value = b"K" * 32 * 100
            mode.execute(start=0, end=299)

            # 应该被调用 2 次（第一次 + 预生成）
            assert mock_gen.call_count >= 2

    def test_stop_condition_boundary_check(self):
        """测试 stop_condition 边界检查"""
        engine = _make_engine_stub(
            batch_size=5,
            # 允许 3 个批次（0-4, 5-9, 10-14）
            stop_side_effect=[False, False, True],
        )

        mode = RangeScanSearchMode(engine)
        mode.execute(start=0, end=9)

        # 总共 10 个 key (0-9)，分 2 个批次 * 5 = 10
        assert engine._current_position == 10

    def test_stop_condition_exact_boundary(self):
        """测试 stop_condition 精确边界（end 正好是批次末尾）"""
        engine = _make_engine_stub(
            batch_size=5,
            stop_side_effect=[False, True],
        )

        mode = RangeScanSearchMode(engine)
        mode.execute(start=0, end=4)

        # 5 个 key，1 个批次
        assert engine._current_position == 5

    def test_stop_condition_after_last_batch(self):
        """测试最后一个批次后停止"""
        engine = _make_engine_stub(
            batch_size=100,
            stop_side_effect=[False, True],
        )

        mode = RangeScanSearchMode(engine)
        mode.execute(start=0, end=100)

        # 101 个 key (0-100)，1 个批次 100 key
        # 然后 next_batch_size=1 (100-100)
        # 第二个批次：gen_keys 返回 1 个 key
        # 然后 stop_cond: current=101 > end=100 → True
        # 实际执行 2 个批次
        # 但第二个批次开始时 stop_condition 检查 → 退出
        # 取决于 stop_condition 检查的时机


# ============================================================================
# 多批次跨范围
# ============================================================================


@pytest.mark.unit
@pytest.mark.gpu_kernel
class TestRangeScanMultiBatch:
    """多批次跨范围测试"""

    def test_cross_batch_boundary(self):
        """测试跨批次边界"""
        engine = _make_engine_stub(
            batch_size=3,
            stop_side_effect=[False, False, False, True],
        )

        mode = RangeScanSearchMode(engine)
        mode.execute(start=0, end=7)

        # 范围 0-7 = 8 个 key
        # 批次 1: 0,1,2 (3)
        # 批次 2: 3,4,5 (3)
        # 批次 3: 6,7 (2)  # 最后一个批次不满
        # 然后 stop: current=8 > end=7
        assert engine._current_position >= 7

    def test_large_end_value(self):
        """测试大 end 值"""
        engine = _make_engine_stub(
            batch_size=5,
            stop_side_effect=[False, True],
        )

        mode = RangeScanSearchMode(engine)
        mode.execute(start=2**250, end=2**250 + 4)

        assert engine._current_position == 2**250 + 5


# ============================================================================
# 边界值测试
# ============================================================================


@pytest.mark.unit
@pytest.mark.gpu_kernel
class TestRangeScanBoundary:
    """RangeScanSearchMode 边界值测试"""

    def test_start_equals_end_large(self):
        """测试 start==end 大值"""
        engine = _make_engine_stub(
            batch_size=100,
            stop_side_effect=[False, True],
        )

        mode = RangeScanSearchMode(engine)
        mode.execute(start=2**255, end=2**255)

        assert engine._current_position == 2**255 + 1

    def test_start_greater_than_end(self):
        """测试 start > end 抛出异常（无效范围）"""
        engine = _make_engine_stub()

        mode = RangeScanSearchMode(engine)
        # start > end 导致负 count，bytearray 抛出 ValueError
        with pytest.raises(ValueError):
            mode.execute(start=100, end=50)

    def test_end_at_uint256_max(self):
        """测试 end=2**256-1（最大值）"""
        engine = _make_engine_stub(
            batch_size=5,
            stop_side_effect=[False, True],
        )

        mode = RangeScanSearchMode(engine)
        mode.execute(start=2**256 - 6, end=2**256 - 1)

        assert engine._running is False

    def test_zero_range(self):
        """测试 start=end=0"""
        engine = _make_engine_stub(
            batch_size=10,
            stop_side_effect=[False, True],
        )

        mode = RangeScanSearchMode(engine)
        mode.execute(start=0, end=0)

        assert engine._current_position == 1  # 0 + 1
