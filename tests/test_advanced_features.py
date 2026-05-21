"""CLI 高级功能 (src/cli/advanced_features.py) 单元测试。

覆盖: deep_merge, apply_template, recommend_parameters,
       export_progress_data, export_matches, GPUErrorHandler
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.cli.advanced_features import (
    GPUErrorHandler,
    apply_template,
    deep_merge,
    export_matches,
    export_progress_data,
    recommend_parameters,
)

# ── deep_merge ───────────────────────────────────────────────────


class TestDeepMerge(unittest.TestCase):
    """deep_merge() 纯函数测试。"""

    def test_adds_new_keys(self):
        """override 有新键 → 合并到 base。"""
        base = {"a": 1}
        deep_merge(base, {"b": 2})
        self.assertEqual(base, {"a": 1, "b": 2})

    def test_overwrites_non_dict_values(self):
        """override 的同名键不是 dict → 直接覆盖。"""
        base = {"a": 1, "c": {"x": 0}}
        deep_merge(base, {"a": 99, "c": 42})
        self.assertEqual(base, {"a": 99, "c": 42})

    def test_recursive_merge_nested_dicts(self):
        """双方同名键都是 dict → 递归深度合并。"""
        base = {"s": {"x": 1, "y": 2}}
        deep_merge(base, {"s": {"y": 99, "z": 3}})
        self.assertEqual(base, {"s": {"x": 1, "y": 99, "z": 3}})

    def test_empty_override_no_change(self):
        """空 override → base 不变。"""
        base = {"a": 1}
        deep_merge(base, {})
        self.assertEqual(base, {"a": 1})

    def test_empty_base(self):
        """空 base + override → 直接复制。"""
        base = {}
        deep_merge(base, {"a": {"b": 2}})
        self.assertEqual(base, {"a": {"b": 2}})

    def test_deeply_nested_merge(self):
        """三层嵌套 dict 递归合并。"""
        base = {"a": {"b": {"c": 1, "d": 2}}}
        deep_merge(base, {"a": {"b": {"d": 99, "e": 3}}})
        self.assertEqual(base, {"a": {"b": {"c": 1, "d": 99, "e": 3}}})

    def test_override_dict_overwrites_base_scalar(self):
        """base 标量被 override dict 覆盖 (不递归)。"""
        base = {"a": 1, "b": "keep"}
        deep_merge(base, {"a": {"nested": 99}})
        self.assertEqual(base, {"a": {"nested": 99}, "b": "keep"})


# ── apply_template ──────────────────────────────────────────────


class TestApplyTemplate(unittest.TestCase):
    """apply_template() 文件 I/O 测试。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_unknown_template_returns_false(self):
        """未知模板名 → 返回 False。"""
        with patch("builtins.print") as mock_print:
            result = apply_template("nonexistent")
            self.assertFalse(result)
            mock_print.assert_called()

    def test_config_not_exists_creates_new(self):
        """配置文件不存在 → 创建新文件并返回 True。"""
        config_path = self.tmp_path / "new_config.json"
        with patch("builtins.print") as mock_print:
            result = apply_template("quick-test", str(config_path))
        self.assertTrue(result)
        self.assertTrue(config_path.exists())
        content = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertIn("collision", content)
        self.assertIn("logging", content)
        mock_print.assert_called()

    def test_existing_config_merges(self):
        """已有配置文件 → 加载、合并、保存。"""
        config_path = self.tmp_path / "existing.json"
        config_path.write_text('{"my_key": "keep_me", "collision": {"x": 1}}', encoding="utf-8")
        with patch("builtins.print"):
            result = apply_template("quick-test", str(config_path))
        self.assertTrue(result)
        content = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(content["my_key"], "keep_me")
        self.assertIn("checkpoint_interval", content["collision"])

    def test_corrupted_config_fallback_to_empty(self):
        """损坏的 JSON → 回退为空配置，仍成功应用模板。"""
        config_path = self.tmp_path / "bad.json"
        config_path.write_text("not valid json{{{", encoding="utf-8")
        with patch("builtins.print"):
            result = apply_template("quick-test", str(config_path))
        self.assertTrue(result)
        content = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertIn("collision", content)

    def test_io_failure_returns_false(self):
        """所有 I/O 失败 (读+写均 PermissionError) → 返回 False。"""
        config_path = self.tmp_path / "ro.json"
        config_path.write_text("{}", encoding="utf-8")
        with patch("builtins.open", side_effect=PermissionError("mock")):
            with patch("builtins.print"):
                result = apply_template("quick-test", str(config_path))
        self.assertFalse(result)

    def test_write_failure_after_successful_read(self):
        """读取成功但写入失败 → 返回 False (精准模拟写权限不足)。"""
        config_path = self.tmp_path / "wo.json"
        config_path.write_text("{}", encoding="utf-8")
        import builtins as _bi

        _real_open = _bi.open

        def _conditional_open(file, mode="r", *a, **kw):
            if "w" in mode:
                raise PermissionError("mock write failure")
            return _real_open(file, mode, *a, **kw)

        with patch("builtins.open", side_effect=_conditional_open), patch("builtins.print"):
            result = apply_template("quick-test", str(config_path))
        self.assertFalse(result)


# ── recommend_parameters ────────────────────────────────────────


class TestRecommendParameters(unittest.TestCase):
    """recommend_parameters() 推荐逻辑测试。"""

    def _make_args(self, **kwargs):
        """创建模拟 args 对象。"""
        defaults = {
            "targets": None,
            "file": None,
            "mode": "random",
            "start": None,
            "end": None,
        }
        defaults.update(kwargs)
        return MagicMock(**defaults)

    def test_many_targets_recommends_dedup(self):
        """targets > 10 → 推荐 --dedup。"""
        args = self._make_args(targets=[f"addr{i}" for i in range(20)])
        result = recommend_parameters(args)
        self.assertIn("--dedup", result["recommendations"])
        self.assertGreater(result["target_count"], 10)

    def test_few_targets_no_dedup(self):
        """targets ≤ 10 + 非随机模式 → 不推荐 --dedup。"""
        args = self._make_args(targets=["a1", "a2", "a3"], mode="sequential")
        result = recommend_parameters(args)
        self.assertNotIn("--dedup", result["recommendations"])

    def test_random_mode_recommends_checkpoint_and_dedup(self):
        """mode=random → 推荐 --checkpoint + --dedup。"""
        args = self._make_args(mode="random", targets=["t1", "t2"])
        result = recommend_parameters(args)
        recs = result["recommendations"]
        self.assertIn("--checkpoint", recs)
        self.assertIn("--dedup", recs)

    def test_range_mode_large_range_recommends_checkpoint(self):
        """mode=range + 范围 ≥ 2^32 → 推荐断点续传。"""
        args = self._make_args(
            mode="range",
            start="0x0",
            end="0x100000001",  # > 2^32
        )
        result = recommend_parameters(args)
        self.assertIn("--checkpoint", result["recommendations"])

    def test_range_mode_small_range_no_checkpoint(self):
        """mode=range + 小范围 → 不推荐断点续传。"""
        args = self._make_args(
            mode="range",
            start="0x0",
            end="0x100",  # 256, < 2^32
        )
        result = recommend_parameters(args)
        self.assertNotIn("--checkpoint", result["recommendations"])

    def test_gpu_available_recommends_use_gpu(self):
        """pyopencl 可用 → 推荐 --use-gpu。"""
        import src.cli.advanced_features as af

        original = sys.modules["src.cli.advanced_features"]
        try:
            with patch.dict("sys.modules", {"pyopencl": MagicMock()}):
                import importlib

                importlib.reload(af)
                # 使用 af.recommend_parameters (重载后的引用),
                # 而非模块级 recommend_parameters, 以确保
                # reloaded 模块中的 pyopencl mock 生效
                args = self._make_args(mode="random")
                result = af.recommend_parameters(args)
                self.assertIn("--use-gpu", result["recommendations"])
        finally:
            if original:
                sys.modules["src.cli.advanced_features"] = original

    def test_gpu_unavailable_adds_cpu_note(self):
        """pyopencl 不可用 → reasons 包含 CPU 模式说明。"""
        import builtins

        _orig_import = builtins.__import__

        def _mock_import(name, *a, **kw):
            if name == "pyopencl":
                raise ImportError("No module named 'pyopencl'")
            return _orig_import(name, *a, **kw)

        with patch("builtins.__import__", side_effect=_mock_import):
            args = self._make_args(mode="random")
            result = recommend_parameters(args)
        reasons_text = " ".join(result["reasons"])
        self.assertIn("CPU", reasons_text)

    def test_file_based_targets_counts_lines(self):
        """通过 --file 指定目标文件 → 正确计数行数。"""
        import tempfile as _tmp_mod

        with _tmp_mod.TemporaryDirectory() as td:
            targets_file = Path(td) / "targets.txt"
            targets_file.write_text("addr1\naddr2\n# comment\n\naddr3\n", encoding="utf-8")
            args = self._make_args(targets=None, file=str(targets_file))
            result = recommend_parameters(args)
            self.assertEqual(result["target_count"], 3)

    def test_file_read_error_graceful(self):
        """目标文件读取异常 → 静默处理，target_count=0。"""
        args = self._make_args(targets=None, file="/nonexistent/file.txt")
        with patch("builtins.open", side_effect=OSError("mock")):
            result = recommend_parameters(args)
        self.assertEqual(result["target_count"], 0)


# ── export_progress_data ────────────────────────────────────────


class TestExportProgressData(unittest.TestCase):
    """export_progress_data() 文件导出测试。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _make_stats(self):
        """创建模拟 stats 对象。"""
        stats = MagicMock()
        stats.total_checked = 50000
        stats.elapsed = 120.5
        stats.format_elapsed.return_value = "00:02:00"
        stats.format_speed.return_value = "416/s"
        stats.matches = ["match1", "match2"]
        return stats

    def test_basic_export_success(self):
        """基本导出 → 返回 True，文件包含正确字段。"""
        output = self.tmp_path / "progress.json"
        stats = self._make_stats()
        with patch("builtins.print"):
            result = export_progress_data(stats, "random", "gpu", str(output))
        self.assertTrue(result)
        self.assertTrue(output.exists())
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["mode"], "random")
        self.assertEqual(data["engine_type"], "gpu")
        self.assertEqual(data["total_checked"], 50000)
        self.assertEqual(data["matches_count"], 2)
        self.assertNotIn("progress_percent", data)

    def test_export_with_total_range_includes_percent(self):
        """提供 total_range → 包含进度百分比。"""
        output = self.tmp_path / "progress2.json"
        stats = self._make_stats()
        stats.total_checked = 25000
        with patch("builtins.print"):
            result = export_progress_data(stats, "random", "cpu", str(output), total_range=100000)
        self.assertTrue(result)
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["total_range"], 100000)
        self.assertAlmostEqual(data["progress_percent"], 25.0)

    def test_export_total_range_zero_skipped(self):
        """total_range=0 → 不在输出中 (falsy 跳过)。"""
        output = self.tmp_path / "pz.json"
        stats = self._make_stats()
        with patch("builtins.print"):
            result = export_progress_data(stats, "r", "cpu", str(output), total_range=0)
        self.assertTrue(result)
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertNotIn("progress_percent", data)

    def test_export_progress_capped_at_100(self):
        """total_checked > total_range → 进度钳位在 100%。"""
        output = self.tmp_path / "pc.json"
        stats = self._make_stats()
        stats.total_checked = 200000
        with patch("builtins.print"):
            result = export_progress_data(stats, "r", "cpu", str(output), total_range=100000)
        self.assertTrue(result)
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["progress_percent"], 100.0)

    def test_export_exception_returns_false(self):
        """写入异常 → 返回 False。"""
        stats = self._make_stats()
        with patch("builtins.open", side_effect=OSError("mock")), patch("builtins.print"):
            result = export_progress_data(stats, "r", "cpu", "/fake/path.json")
        self.assertFalse(result)


# ── export_matches ──────────────────────────────────────────────


class TestExportMatches(unittest.TestCase):
    """export_matches() 文件导出测试。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_basic_export_success(self):
        """导出匹配列表 → 返回 True。"""
        output = self.tmp_path / "matches.json"
        matches = [{"priv": "abc", "addr": "1A..."}, {"priv": "def", "addr": "1B..."}]
        with patch("builtins.print"):
            result = export_matches(matches, str(output))
        self.assertTrue(result)
        self.assertTrue(output.exists())
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["total_matches"], 2)
        self.assertEqual(len(data["matches"]), 2)

    def test_empty_matches(self):
        """空匹配列表 → 正常导出。"""
        output = self.tmp_path / "empty.json"
        with patch("builtins.print"):
            result = export_matches([], str(output))
        self.assertTrue(result)
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["total_matches"], 0)

    def test_export_exception_returns_false(self):
        """写入异常 → 返回 False。"""
        with patch("builtins.open", side_effect=OSError("mock")), patch("builtins.print"):
            result = export_matches([{"a": 1}], "/fake/path.json")
        self.assertFalse(result)


# ── GPUErrorHandler ─────────────────────────────────────────────


class TestGPUErrorHandlerInitError(unittest.TestCase):
    """GPUErrorHandler.handle_initialization_error() 纯逻辑测试。"""

    def test_no_platform_error(self):
        """'no platform' → type=no_gpu, recoverable=False。"""
        result = GPUErrorHandler.handle_initialization_error(Exception("No platform found"))
        self.assertEqual(result["type"], "no_gpu")
        self.assertFalse(result["recoverable"])
        self.assertIn("GPU", result["solution"])

    def test_no_gpu_error(self):
        """'no gpu' → type=no_gpu。"""
        result = GPUErrorHandler.handle_initialization_error(Exception("no GPU detected"))
        self.assertEqual(result["type"], "no_gpu")

    def test_out_of_memory_error(self):
        """'out of memory' → type=out_of_memory, recoverable=True。"""
        result = GPUErrorHandler.handle_initialization_error(
            Exception("CL_OUT_OF_MEMORY: out of memory")
        )
        self.assertEqual(result["type"], "out_of_memory")
        self.assertTrue(result["recoverable"])
        self.assertIn("显存不足", result["solution"])

    def test_generic_memory_error(self):
        """generic 'memory' → type=out_of_memory。"""
        result = GPUErrorHandler.handle_initialization_error(Exception("memory allocation failed"))
        self.assertEqual(result["type"], "out_of_memory")
        self.assertTrue(result["recoverable"])

    def test_driver_error(self):
        """'driver' → type=driver_issue, recoverable=False。"""
        result = GPUErrorHandler.handle_initialization_error(Exception("driver not compatible"))
        self.assertEqual(result["type"], "driver_issue")
        self.assertFalse(result["recoverable"])

    def test_version_error(self):
        """'version' → type=driver_issue。"""
        result = GPUErrorHandler.handle_initialization_error(Exception("unsupported version"))
        self.assertEqual(result["type"], "driver_issue")

    def test_unknown_error(self):
        """未知错误 → type=unknown, 含通用建议。"""
        result = GPUErrorHandler.handle_initialization_error(Exception("some random failure"))
        self.assertEqual(result["type"], "unknown")
        self.assertFalse(result["recoverable"])
        self.assertIn("GPU初始化失败", result["solution"])


class TestGPUErrorHandlerBatchSize(unittest.TestCase):
    """GPUErrorHandler.suggest_batch_size_adjustment() 纯逻辑测试。"""

    def test_oom_halves_batch_size(self):
        """OOM → 减半 (最小 1024)。"""
        result = GPUErrorHandler.suggest_batch_size_adjustment(65536, Exception("out of memory"))
        self.assertEqual(result, 32768)

    def test_oom_floor_at_1024(self):
        """OOM 减半不低过 1024。"""
        result = GPUErrorHandler.suggest_batch_size_adjustment(1500, Exception("out of memory"))
        self.assertEqual(result, 1024)

    def test_non_oom_keeps_current_size(self):
        """非 OOM → 返回原值。"""
        result = GPUErrorHandler.suggest_batch_size_adjustment(65536, Exception("driver error"))
        self.assertEqual(result, 65536)


if __name__ == "__main__":
    unittest.main()
