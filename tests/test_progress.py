"""progress.py 单元测试。

覆盖 _format_checked_count、_format_total_count、_compute_eta、
_format_progress_bar 四个私有纯函数，以及 format_progress 的 Mock 测试。
"""

import unittest
from unittest.mock import MagicMock

from src.cli.constants import (
    PROGRESS_BAR_EMPTY,
    PROGRESS_BAR_FILLED,
    PROGRESS_BAR_LENGTH,
    UNIT_BILLION,
    UNIT_MILLION,
    UNIT_THOUSAND,
)
from src.cli.progress import (
    VALID_ENGINE_TYPES,
    _compute_eta,
    _format_checked_count,
    _format_progress_bar,
    _format_total_count,
    format_progress,
)


class TestFormatCheckedCount(unittest.TestCase):
    """测试 _format_checked_count 数值缩写格式化。"""

    def test_billion(self):
        """≥10 亿 → x.xxB。"""
        self.assertEqual(_format_checked_count(UNIT_BILLION), "1.00B")
        self.assertEqual(_format_checked_count(2_500_000_000), "2.50B")

    def test_million(self):
        """≥100 万 → x.xxM。"""
        self.assertEqual(_format_checked_count(UNIT_MILLION), "1.00M")
        self.assertEqual(_format_checked_count(1_500_000), "1.50M")
        self.assertEqual(_format_checked_count(999_000_000), "999.00M")

    def test_thousand(self):
        """≥1000 → x.xK。"""
        self.assertEqual(_format_checked_count(UNIT_THOUSAND), "1.0K")
        self.assertEqual(_format_checked_count(500_000), "500.0K")
        self.assertEqual(_format_checked_count(1500), "1.5K")

    def test_below_thousand(self):
        """<1000 → 原始数字字符串。"""
        self.assertEqual(_format_checked_count(0), "0")
        self.assertEqual(_format_checked_count(42), "42")
        self.assertEqual(_format_checked_count(999), "999")


class TestFormatTotalCount(unittest.TestCase):
    """测试 _format_total_count 总范围格式化。"""

    def test_billion(self):
        """≥10 亿 → x.xxB。"""
        self.assertEqual(_format_total_count(UNIT_BILLION), "1.00B")

    def test_million(self):
        """≥100 万 → x.xxM。"""
        self.assertEqual(_format_total_count(UNIT_MILLION), "1.00M")
        self.assertEqual(_format_total_count(5_000_000), "5.00M")

    def test_below_million_with_comma(self):
        """<100 万 → 逗号分隔的整数。"""
        self.assertEqual(_format_total_count(0), "0")
        self.assertEqual(_format_total_count(999_999), "999,999")
        self.assertEqual(_format_total_count(1000), "1,000")


class TestComputeEta(unittest.TestCase):
    """测试 _compute_eta 预计剩余时间计算。"""

    def test_total_range_none(self):
        """total_range=None → '--'。"""
        self.assertEqual(_compute_eta(10.0, 100, None), "--")

    def test_total_range_zero(self):
        """total_range=0 → '--'。"""
        self.assertEqual(_compute_eta(10.0, 100, 0), "--")

    def test_total_range_negative(self):
        """total_range<=0 → '--'。"""
        self.assertEqual(_compute_eta(10.0, 100, -5), "--")

    def test_checked_zero(self):
        """checked=0 → '--'。"""
        self.assertEqual(_compute_eta(10.0, 0, 1000), "--")

    def test_checked_negative(self):
        """checked<=0 → '--'。"""
        self.assertEqual(_compute_eta(10.0, -1, 1000), "--")

    def test_elapsed_zero(self):
        """elapsed_sec=0 → '--'。"""
        self.assertEqual(_compute_eta(0.0, 500, 1000), "--")

    def test_completed_done(self):
        """checked >= total_range → '[Done] 完成'。"""
        self.assertEqual(_compute_eta(10.0, 1000, 1000), "[Done] 完成")
        self.assertEqual(_compute_eta(10.0, 1500, 1000), "[Done] 完成")

    def test_eta_seconds(self):
        """ETA < 60s → xxs。"""
        # speed=50/s, remaining=500, eta=10s
        result = _compute_eta(10.0, 500, 1000)
        self.assertEqual(result, "10s")

    def test_eta_minutes(self):
        """ETA 在 60s–3600s → x.xm。"""
        # speed=1000/100=10/s, remaining=9000, eta=900s=15.0m
        self.assertEqual(_compute_eta(100.0, 1000, 10000), "15.0m")

    def test_eta_hours(self):
        """ETA ≥ 3600s → x.xh。"""
        # speed=100/100=1/s, remaining=9900, eta=9900s=2.8h (2.75 rounded)
        self.assertEqual(_compute_eta(100.0, 100, 10000), "2.8h")


class TestFormatProgressBar(unittest.TestCase):
    """测试 _format_progress_bar Unicode 进度条渲染。"""

    def test_zero_percent(self):
        """0% 进度条全空。"""
        bar = _format_progress_bar(0.0)
        expected = f" {PROGRESS_BAR_EMPTY * PROGRESS_BAR_LENGTH}   0.0%"
        self.assertEqual(bar, expected)

    def test_fifty_percent(self):
        """50% 进度条一半填充一半空。"""
        filled_count = 10  # 20 * 50 / 100
        empty_count = PROGRESS_BAR_LENGTH - filled_count
        expected_bar = PROGRESS_BAR_FILLED * filled_count + PROGRESS_BAR_EMPTY * empty_count
        expected = f" {expected_bar}  50.0%"
        self.assertEqual(_format_progress_bar(50.0), expected)

    def test_hundred_percent(self):
        """100% 进度条全满。"""
        expected = f" {PROGRESS_BAR_FILLED * PROGRESS_BAR_LENGTH} 100.0%"
        self.assertEqual(_format_progress_bar(100.0), expected)

    def test_low_percent_no_bar(self):
        """< 2.5% 时因 int() 截断进度条全空。"""
        expected = f" {PROGRESS_BAR_EMPTY * PROGRESS_BAR_LENGTH}   2.0%"
        self.assertEqual(_format_progress_bar(2.0), expected)

    def test_over_hundred_percent(self):
        """超过 100% 时进度条溢出（by design：filled 超过 BAR_LENGTH）。"""
        bar = _format_progress_bar(150.0)
        expected_filled = int(PROGRESS_BAR_LENGTH * 150 / 100)
        self.assertIn(PROGRESS_BAR_FILLED * expected_filled, bar)
        self.assertIn("150.0%", bar)


class TestFormatProgress(unittest.TestCase):
    """测试 format_progress 主函数（Mock CollisionStats）。"""

    def _make_mock_stats(self, **kwargs):
        """创建 Mock CollisionStats。"""
        stats = MagicMock()
        stats.format_elapsed.return_value = "00:00:10"
        stats.total_checked = 1000
        stats.format_speed.return_value = "100/s"
        stats.matches = []
        stats.elapsed = 20.0  # > INIT_CHECK_THRESHOLD
        stats.start_time = 1000.0
        for k, v in kwargs.items():
            setattr(stats, k, v)
        return stats

    def test_random_mode_no_total(self):
        """random 模式无 total_range 时不显示进度条和百分比。"""
        stats = self._make_mock_stats()
        result = format_progress(stats, "random")
        self.assertIn("100/s", result)
        self.assertNotIn("%", result)
        self.assertIn("1.0K", result)

    def test_range_mode_with_total(self):
        """range 模式有 total_range 时显示进度条和百分比。"""
        stats = self._make_mock_stats(total_checked=500)
        result = format_progress(stats, "range", total_range=1000)
        self.assertIn("50.0%", result)
        self.assertIn("500/", result)

    def test_initializing_state(self):
        """checked=0 且运行时间不足 → 显示初始化。"""
        stats = self._make_mock_stats(total_checked=0, elapsed=2.0, start_time=1000.0)
        result = format_progress(stats, "random")
        self.assertIn("Initializing", result)
        self.assertIn("初始化中", result)

    def test_initializing_not_triggered_when_checked_nonzero(self):
        """checked>0 不进入初始化状态。"""
        stats = self._make_mock_stats(total_checked=1, elapsed=2.0, start_time=1000.0)
        result = format_progress(stats, "random")
        self.assertNotIn("Initializing", result)

    def test_initializing_not_triggered_after_threshold(self):
        """checked=0 但 elapsed >= INIT_CHECK_THRESHOLD → 不显示初始化。"""
        stats = self._make_mock_stats(total_checked=0, elapsed=20.0, start_time=1000.0)
        result = format_progress(stats, "random")
        self.assertNotIn("Initializing", result)

    def test_engine_type_cpu(self):
        """engine_type='cpu' → [CPU] 标签。"""
        stats = self._make_mock_stats()
        result = format_progress(stats, "random", engine_type="cpu")
        self.assertIn("[CPU]", result)

    def test_engine_type_gpu(self):
        """engine_type='gpu' → [GPU] 标签。"""
        stats = self._make_mock_stats()
        result = format_progress(stats, "random", engine_type="gpu")
        self.assertIn("[GPU]", result)

    def test_engine_type_multi_gpu(self):
        """engine_type='multi-gpu' → [MULTI-GPU] 标签。"""
        stats = self._make_mock_stats()
        result = format_progress(stats, "random", engine_type="multi-gpu")
        self.assertIn("[MULTI-GPU]", result)

    def test_engine_type_invalid_falls_back_cpu(self):
        """无效 engine_type 降级为 [CPU]。"""
        stats = self._make_mock_stats()
        result = format_progress(stats, "random", engine_type="nonexistent")
        self.assertIn("[CPU]", result)

    def test_total_range_zero_treated_as_none(self):
        """total_range=0 时不显示进度条。"""
        stats = self._make_mock_stats()
        result = format_progress(stats, "range", total_range=0)
        self.assertNotIn("%", result)

    def test_checked_exceeds_total(self):
        """checked >= total_range → ETA 显示完成。"""
        stats = self._make_mock_stats(total_checked=1000)
        result = format_progress(stats, "range", total_range=1000)
        self.assertIn("完成", result)

    def test_no_total_range_shows_checked_only(self):
        """无 total_range 时仅显示已检查数量，无 '/' 分隔符。"""
        stats = self._make_mock_stats(total_checked=500)
        result = format_progress(stats, "random")
        self.assertIn("500", result)
        # 没有 "/" 因为无 total_range
        self.assertNotIn("500/", result)

    def test_eta_shown_when_available(self):
        """有 total_range 时 ETA 区域存在。"""
        stats = self._make_mock_stats(total_checked=500)
        result = format_progress(stats, "range", total_range=10000)
        self.assertIn("ETA:", result)

    def test_all_engine_types_in_valid_set(self):
        """VALID_ENGINE_TYPES 包含预期值。"""
        self.assertEqual(VALID_ENGINE_TYPES, {"cpu", "gpu", "multi-gpu"})


if __name__ == "__main__":
    unittest.main()
