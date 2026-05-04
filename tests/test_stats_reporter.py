"""CLI 统计报告 (src/cli/stats_reporter.py) 单元测试。

覆盖: _print_detailed_stats, _print_final_summary
"""

import unittest
from unittest.mock import MagicMock, patch

from src.cli.output import CLIOutput
from src.cli.stats_reporter import _print_detailed_stats, _print_final_summary


# ── 辅助工具 ────────────────────────────────────────────────────

def _mock_cli_output():
    """创建 mock CLIOutput 并 patch get_instance。"""
    CLIOutput.reset_instance()
    out = CLIOutput()
    out.console = MagicMock()
    out.err_console = MagicMock()
    out.final_summary = MagicMock()
    out.stats_panel = MagicMock()
    return out


def _make_engine(engine_type="cpu", **kwargs):
    """创建模拟 engine 对象。"""
    defaults = {
        "get_stats": MagicMock(),
        "get_combined_stats": MagicMock(),
        "cleanup": MagicMock(),
    }
    defaults.update(kwargs)
    engine = MagicMock(**defaults)
    if engine_type == "cpu":
        stats = MagicMock()
        stats.total_checked = 100000
        stats.format_elapsed.return_value = "00:05:00"
        stats.format_speed.return_value = "333/s"
        stats.matches = []
        engine.get_stats.return_value = stats
    elif engine_type == "gpu":
        stats = MagicMock()
        stats.total_checked = 500000
        stats.format_elapsed.return_value = "00:02:00"
        stats.format_speed.return_value = "4167/s"
        stats.matches = [{"address": "1A...", "private_key": "abc"}]
        engine.get_stats.return_value = stats
    elif engine_type == "multi_gpu":
        engine.get_combined_stats.return_value = {
            "elapsed_time": 3600,
            "total_keys_checked": 1000000,
            "combined_throughput": 500,
            "total_matches": 3,
            "device_count": 2,
            "per_device": {
                0: {"keys_checked": 500000, "throughput": 250},
                1: {"keys_checked": 500000, "throughput": 250},
            },
        }
    return engine


# ── _print_detailed_stats ───────────────────────────────────────

class TestPrintDetailedStats(unittest.TestCase):
    """_print_detailed_stats() 单元测试。"""

    def setUp(self):
        self.out = _mock_cli_output()

    def tearDown(self):
        CLIOutput.reset_instance()

    def _call(self, stats):
        with patch.object(CLIOutput, "get_instance", return_value=self.out):
            _print_detailed_stats(stats)

    def test_normal_stats_all_fields(self):
        """正常 stats → 输出 4 行统计。"""
        stats = MagicMock()
        stats.total_checked = 50000
        stats.matches = ["a", "b"]
        stats.format_elapsed.return_value = "01:23:45"
        stats.format_speed.return_value = "100/s"
        stats.gpu_info = None

        self._call(stats)

        self.out.stats_panel.assert_called_once()
        rows = self.out.stats_panel.call_args[0][1]
        self.assertEqual(len(rows), 4)
        self.assertIn(("已检查", "50,000"), rows)
        self.assertIn(("运行时间", "01:23:45"), rows)
        self.assertIn(("平均速度", "100/s"), rows)
        self.assertIn(("发现匹配", "2"), rows)

    def test_with_gpu_info_adds_row(self):
        """stats 有 gpu_info → 追加 GPU 行 (共 5 行)。"""
        stats = MagicMock()
        stats.total_checked = 100
        stats.matches = []
        stats.format_elapsed.return_value = "00:00:01"
        stats.format_speed.return_value = "100/s"
        stats.gpu_info = "NVIDIA RTX 4090"

        self._call(stats)

        rows = self.out.stats_panel.call_args[0][1]
        self.assertEqual(len(rows), 5)
        self.assertIn(("GPU设备", "NVIDIA RTX 4090"), rows)

    def test_missing_format_elapsed_fallback(self):
        """stats 无 format_elapsed → 回退到 str(elapsed)。"""
        stats = MagicMock()
        stats.total_checked = 50
        stats.matches = []
        stats.elapsed = 42.5
        # 删除 hasattr 对 format_elapsed 的支持
        del stats.format_elapsed
        stats.format_speed.return_value = "10/s"
        stats.gpu_info = None

        self._call(stats)

        rows = self.out.stats_panel.call_args[0][1]
        self.assertIn(("运行时间", "42.5"), rows)

    def test_missing_format_speed_fallback_to_dash(self):
        """stats 无 format_speed → 回退为 '--'。"""
        stats = MagicMock()
        stats.total_checked = 50
        stats.matches = []
        stats.format_elapsed.return_value = "00:01"
        del stats.format_speed
        stats.gpu_info = None

        self._call(stats)

        rows = self.out.stats_panel.call_args[0][1]
        self.assertIn(("平均速度", "--"), rows)

    def test_exception_during_access_shows_fallback(self):
        """stats 属性访问抛异常 → 显示 '统计信息暂不可用'。"""
        stats = MagicMock()
        del stats.total_checked  # 触发 getattr 默认值 0
        # 让 format_elapsed() 抛异常
        stats.format_elapsed.side_effect = AttributeError("boom")
        stats.matches = []
        stats.format_speed.return_value = "100/s"

        self._call(stats)

        rows = self.out.stats_panel.call_args[0][1]
        self.assertEqual(rows, [("状态", "统计信息暂不可用")])

    def test_matches_as_int_triggers_except_fallback(self):
        """stats.matches 是整数 → len(int) 抛 TypeError → 回退。"""
        stats = MagicMock()
        stats.total_checked = 100
        stats.matches = 5  # int, not list → len(5) → TypeError
        stats.format_elapsed.return_value = "00:01"
        stats.format_speed.return_value = "10/s"
        stats.gpu_info = None

        self._call(stats)

        rows = self.out.stats_panel.call_args[0][1]
        self.assertEqual(rows, [("状态", "统计信息暂不可用")])

    def test_no_matches_attr_fallback_to_zero(self):
        """stats 无 matches 属性 → 回退 0。"""
        stats = MagicMock()
        stats.total_checked = 100
        del stats.matches
        stats.format_elapsed.return_value = "00:01"
        stats.format_speed.return_value = "10/s"
        stats.gpu_info = None

        self._call(stats)

        rows = self.out.stats_panel.call_args[0][1]
        self.assertIn(("发现匹配", "0"), rows)


# ── _print_final_summary ───────────────────────────────────────

class TestPrintFinalSummary(unittest.TestCase):
    """_print_final_summary() 单元测试。"""

    def setUp(self):
        self.out = _mock_cli_output()

    def tearDown(self):
        CLIOutput.reset_instance()

    def _make_args(self, **kwargs):
        defaults = {
            "export_progress": None,
            "export_matches": None,
            "mode": "random",
        }
        defaults.update(kwargs)
        return MagicMock(**defaults)

    def _call(self, engine, engine_type, args=None):
        if args is None:
            args = self._make_args()
        with patch.object(CLIOutput, "get_instance", return_value=self.out):
            with patch("src.cli.pagination.display_paginated_results") as self._pag_mock:
                _print_final_summary(engine, engine_type, args)

    def test_cpu_engine_summary(self):
        """CPU 引擎 → final_summary 含 CPU 模式标签 + 统计数据。"""
        engine = _make_engine("cpu")
        self._call(engine, "cpu")

        self.out.final_summary.assert_called_once()
        stats_dict = self.out.final_summary.call_args[0][1]
        self.assertEqual(len(stats_dict), 5)
        self.assertIn("100,000", list(stats_dict.values()))

    def test_gpu_engine_summary(self):
        """GPU 引擎 → final_summary 含 GPU 标签 (mock input 避免 pagination 阻塞)。"""
        engine = _make_engine("gpu")
        with patch("builtins.input", return_value="q"):
            self._call(engine, "gpu")

        self.out.final_summary.assert_called_once()
        stats_dict = self.out.final_summary.call_args[0][1]
        self.assertEqual(len(stats_dict), 5)
        # i18n 无关断言：验证值中包含 GPU 引擎统计关键数据
        self.assertIn("500,000", list(stats_dict.values()))

    def test_multi_gpu_engine_summary(self):
        """多GPU 引擎 → 含设备数 + per-device 统计。"""
        engine = _make_engine("multi_gpu")
        self._call(engine, "multi_gpu")

        self.out.final_summary.assert_called_once()
        stats_dict = self.out.final_summary.call_args[0][1]
        # 5 个基础字段 + 2 个 per-device 字段 = 7
        self.assertEqual(len(stats_dict), 7)
        # i18n 无关断言：值中包含设备数和总检查数
        values_str = " ".join(str(v) for v in stats_dict.values())
        self.assertIn("2", values_str)  # device_count
        self.assertIn("1,000,000", values_str)  # total_keys_checked
        engine.cleanup.assert_called_once()

    def test_multi_gpu_no_per_device(self):
        """多GPU 但无 per_device 键 → 不崩溃。"""
        engine = _make_engine("multi_gpu")
        engine.get_combined_stats.return_value = {
            "elapsed_time": 60,
            "total_keys_checked": 1000,
            "combined_throughput": 100,
            "total_matches": 0,
            "device_count": 1,
            # 无 per_device
        }
        self._call(engine, "multi_gpu")
        self.out.final_summary.assert_called_once()

    def test_cpu_with_matches_calls_pagination(self):
        """CPU 引擎有匹配 → 调用 display_paginated_results。"""
        engine = _make_engine("cpu")
        engine.get_stats.return_value.matches = [{"address": "1A...", "private_key": "ab"}]
        self._call(engine, "cpu")
        self._pag_mock.assert_called_once()

    def test_gpu_with_matches_calls_pagination(self):
        """GPU 引擎有匹配 → 调用分页显示。"""
        engine = _make_engine("gpu")
        engine.get_stats.return_value.matches = [{"address": "1B...", "private_key": "cd"}]
        self._call(engine, "gpu")
        self._pag_mock.assert_called_once()

    def test_export_progress_called_when_flag_set(self):
        """args.export_progress 设置 → 调用 export_progress_data。"""
        engine = _make_engine("cpu")
        args = self._make_args(export_progress="out.json")

        with patch("src.cli.stats_reporter.export_progress_data") as mock_exp:
            with patch("builtins.print"):
                self._call(engine, "cpu", args)
                mock_exp.assert_called_once()

    def test_export_matches_called_when_flag_set(self):
        """args.export_matches 设置 → 调用 export_matches。"""
        engine = _make_engine("cpu")
        # 空 matches 避免触发 pagination 路径
        engine.get_stats.return_value.matches = []
        args = self._make_args(export_matches="matches.json")

        with patch("src.cli.stats_reporter.export_matches") as mock_exp:
            with patch("builtins.print"):
                self._call(engine, "cpu", args)
                mock_exp.assert_called_once()

    def test_export_progress_exception_prints_error(self):
        """export_progress 抛异常 → 打印错误信息并继续输出 final_summary。"""
        engine = _make_engine("cpu")
        args = self._make_args(export_progress="out.json")

        with patch("src.cli.stats_reporter.export_progress_data",
                   side_effect=RuntimeError("disk full")):
            with patch("builtins.print") as mock_print:
                self._call(engine, "cpu", args)
                mock_print.assert_called_once()
                self.out.final_summary.assert_called_once()

    def test_export_matches_exception_prints_error(self):
        """export_matches 抛异常 → 错误被 except 捕获，final_summary 仍输出。"""
        engine = _make_engine("cpu")
        args = self._make_args(export_matches="matches.json")

        with patch("src.cli.stats_reporter.export_matches",
                   side_effect=OSError("permission denied")):
            with patch("builtins.print") as mock_print:
                self._call(engine, "cpu", args)
                mock_print.assert_called_once()
                self.out.final_summary.assert_called_once()

    def test_export_matches_dict_stats(self):
        """engine.get_stats 返回 dict 含 matches → export_matches 提取列表。"""
        engine = _make_engine("cpu")
        # 第1次调用(供 summary): MagicMock; 第2次(供 export): dict
        stats_first = engine.get_stats.return_value
        engine.get_stats.side_effect = [
            stats_first,
            {"matches": [{"a": 1}]},
        ]
        args = self._make_args(export_matches="matches.json")

        with patch("src.cli.stats_reporter.export_matches") as mock_exp:
            with patch("builtins.print"):
                self._call(engine, "cpu", args)
                mock_exp.assert_called_once_with([{"a": 1}], "matches.json")

    def test_export_progress_dict_stats(self):
        """engine.get_stats 返回 dict → export 仍正常工作。"""
        engine = _make_engine("cpu")
        # 第1次调用(供 summary): MagicMock; 第2次(供 export): dict
        stats_first = engine.get_stats.return_value
        engine.get_stats.side_effect = [
            stats_first,
            {"matches": []},
        ]
        args = self._make_args(export_progress="out.json")

        with patch("src.cli.stats_reporter.export_progress_data") as mock_exp:
            with patch("builtins.print"):
                self._call(engine, "cpu", args)
                mock_exp.assert_called_once()


if __name__ == "__main__":
    unittest.main()
