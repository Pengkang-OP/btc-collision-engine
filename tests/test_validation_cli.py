"""CLI 参数验证模块 (src/cli/validation.py) 单元测试"""

import argparse
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.cli.constants import (
    DEFAULT_CHECKPOINT_INTERVAL,
    DEFAULT_DEDUP_MAX_SIZE,
    DEFAULT_WINDOW_SIZE,
)
from src.cli.validation import (
    _DURATION_WARN_THRESHOLD,
    _get_output,
    validate_args,
    validate_file_path,
)

# ── helpers ────────────────────────────────────────────────────


def _make_mock_output():
    """创建模拟 CLIOutput，记录所有输出调用。"""
    output = MagicMock()
    output.error = MagicMock()
    output.warning = MagicMock()
    output.print = MagicMock()
    return output


def _make_args(**overrides):
    """创建模拟 argparse.Namespace，填充合理默认值。"""
    defaults = {
        "targets": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
        "file": None,
        "mode": "random",
        "health_check": False,
        "platform_check": False,
        "cleanup": False,
        "validate_addresses": None,
        "examples": False,
        "config_check": False,
        "quick_start": False,
        "start": None,
        "end": None,
        "duration": 0,
        "checkpoint_interval": DEFAULT_CHECKPOINT_INTERVAL,
        "checkpoint": False,
        "dedup_max_size": DEFAULT_DEDUP_MAX_SIZE,
        "dedup": False,
        "window_size": DEFAULT_WINDOW_SIZE,
        "workers": None,
        "use_gpu": False,
        "multi_gpu": False,
        "no_optimize": False,
        "no_simd": False,
        "no_memory_pool": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ── TestValidateArgs ───────────────────────────────────────────


class TestValidateArgs(unittest.TestCase):
    """validate_args() 各分支全覆盖。"""

    def setUp(self):
        self.mock_output = _make_mock_output()
        patcher = patch(
            "src.cli.validation._get_output", return_value=self.mock_output
        )
        self.addCleanup(patcher.stop)
        patcher.start()

    # ── 1. 无目标 / 无文件 且非工具命令 → False ──

    def test_no_target_no_file_not_util(self):
        """无 -t/-f 且非工具命令 → False。"""
        args = _make_args(targets=None, file=None)
        self.assertFalse(validate_args(args))
        self.mock_output.error.assert_called()

    # ── 2. 工具命令可绕过 targets/file 要求 ──

    def test_util_cmd_health_check_bypass(self):
        """--health-check 绕过 targets 检查。"""
        args = _make_args(targets=None, file=None, health_check=True, mode="random")
        self.assertTrue(validate_args(args))

    def test_util_cmd_platform_check_bypass(self):
        """--platform-check 绕过 targets 检查。"""
        args = _make_args(targets=None, file=None, platform_check=True)
        self.assertTrue(validate_args(args))

    def test_util_cmd_cleanup_bypass(self):
        """--cleanup 绕过 targets 检查。"""
        args = _make_args(targets=None, file=None, cleanup=True)
        self.assertTrue(validate_args(args))

    def test_util_cmd_validate_addresses_bypass(self):
        """--validate-addresses 绕过 targets 检查。"""
        args = _make_args(
            targets=None, file=None, validate_addresses="some_file.txt"
        )
        self.assertTrue(validate_args(args))

    def test_util_cmd_examples_bypass(self):
        """--examples 绕过 targets 检查。"""
        args = _make_args(targets=None, file=None, examples=True)
        self.assertTrue(validate_args(args))

    def test_util_cmd_config_check_bypass(self):
        """--config-check 绕过 targets 检查。"""
        args = _make_args(targets=None, file=None, config_check=True)
        self.assertTrue(validate_args(args))

    def test_util_cmd_quick_start_bypass(self):
        """--quick-start 绕过 targets 检查。"""
        args = _make_args(targets=None, file=None, quick_start=True)
        self.assertTrue(validate_args(args))

    # ── 3. -f 文件路径验证 ──

    @patch("src.cli.validation.validate_file_path", return_value=False)
    def test_file_path_invalid(self, _mock_vfp):
        """-f 指定文件但路径无效 → False。"""
        args = _make_args(file="nonexistent.txt")
        self.assertFalse(validate_args(args))

    @patch("src.cli.validation.validate_file_path", return_value=True)
    def test_file_path_valid_continues(self, _mock_vfp):
        """-f 指定文件且路径有效 → 继续后续验证。"""
        args = _make_args(targets=None, file="valid.txt")
        self.assertTrue(validate_args(args))

    # ── 4. range / brute_force 模式 start 检查 ──

    def test_range_mode_no_start(self):
        """range 模式缺少 --start → False。"""
        args = _make_args(mode="range", start=None)
        self.assertFalse(validate_args(args))
        self.mock_output.error.assert_called()

    def test_brute_force_mode_no_start(self):
        """brute_force 模式缺少 --start → False。"""
        args = _make_args(mode="brute_force", start=None)
        self.assertFalse(validate_args(args))

    def test_range_mode_start_hex_invalid(self):
        """range 模式 --start 非十六进制 → False。"""
        args = _make_args(mode="range", start="GHIJKL", end="FFFFFF")
        self.assertFalse(validate_args(args))
        self.mock_output.error.assert_called()

    def test_brute_force_mode_start_valid_hex(self):
        """brute_force 模式 --start 有效十六进制 → True。"""
        args = _make_args(mode="brute_force", start="1A2B3C")
        self.assertTrue(validate_args(args))

    def test_brute_force_mode_start_hex_invalid(self):
        """brute_force 模式 --start 非十六进制 → False。"""
        args = _make_args(mode="brute_force", start="GHIJKL")
        self.assertFalse(validate_args(args))
        self.mock_output.error.assert_called()

    # ── 5. range 模式 end 检查 ──

    def test_range_mode_no_end(self):
        """range 模式缺少 --end → False。"""
        args = _make_args(mode="range", start="1", end=None)
        self.assertFalse(validate_args(args))

    def test_range_mode_end_hex_invalid(self):
        """range 模式 --end 非十六进制 → False。"""
        args = _make_args(mode="range", start="1", end="XYZ")
        self.assertFalse(validate_args(args))

    def test_range_mode_start_ge_end(self):
        """--start >= --end → False。"""
        args = _make_args(mode="range", start="100", end="100")
        self.assertFalse(validate_args(args))

    def test_range_mode_start_lt_1(self):
        """--start < 1 → False。"""
        args = _make_args(mode="range", start="0", end="100")
        self.assertFalse(validate_args(args))

    def test_range_mode_valid(self):
        """range 模式合法参数 → True。"""
        args = _make_args(mode="range", start="1", end="100")
        self.assertTrue(validate_args(args))

    def test_range_too_large_warning(self):
        """range 模式总范围 > 2^64 → 警告但不阻止 (仍返回 True)。"""
        huge_start = "1"
        huge_end = hex(2**65)[2:]  # > 2^64
        args = _make_args(mode="range", start=huge_start, end=huge_end)
        result = validate_args(args)
        self.assertTrue(result)
        self.mock_output.warning.assert_called()

    # ── 6. duration 超长警告 ──

    def test_duration_over_threshold_warning(self):
        """--duration > 7 天 → 警告但不阻止。"""
        args = _make_args(duration=_DURATION_WARN_THRESHOLD + 1)
        self.assertTrue(validate_args(args))
        self.mock_output.warning.assert_called()

    # ── 7. checkpoint-interval 范围检查 ──

    def test_checkpoint_interval_below_min(self):
        """checkpoint-interval < 5 → False。"""
        args = _make_args(checkpoint_interval=4)
        self.assertFalse(validate_args(args))

    def test_checkpoint_interval_above_max(self):
        """checkpoint-interval > 3600 → False。"""
        args = _make_args(checkpoint_interval=3601)
        self.assertFalse(validate_args(args))

    def test_checkpoint_interval_valid(self):
        """checkpoint-interval 在合法范围 → True。"""
        args = _make_args(checkpoint_interval=60)
        self.assertTrue(validate_args(args))

    def test_checkpoint_interval_lower_bound(self):
        """checkpoint-interval = 5 (合法下界) → True。"""
        args = _make_args(checkpoint_interval=5)
        self.assertTrue(validate_args(args))

    def test_checkpoint_interval_upper_bound(self):
        """checkpoint-interval = 3600 (合法上界) → True。"""
        args = _make_args(checkpoint_interval=3600)
        self.assertTrue(validate_args(args))

    # ── 8. GPU 模式 CPU 参数警告 ──

    @patch("src.cli.validation.logging")
    def test_gpu_mode_cpu_params_warning(self, mock_logging):
        """GPU 模式 + CPU 专用参数 → 日志警告，验证通过。"""
        args = _make_args(use_gpu=True, no_optimize=True, no_simd=True)
        self.assertTrue(validate_args(args))
        mock_logging.getLogger.return_value.warning.assert_called()

    @patch("src.cli.validation.logging")
    def test_multi_gpu_mode_cpu_params_warning(self, mock_logging):
        """multi-gpu 模式 + CPU 专用参数 → 日志警告。"""
        args = _make_args(multi_gpu=True, no_memory_pool=True)
        self.assertTrue(validate_args(args))
        mock_logging.getLogger.return_value.warning.assert_called()

    @patch("src.cli.validation.logging")
    def test_gpu_mode_no_cpu_params_no_warning(self, mock_logging):
        """GPU 模式但未使用 CPU 专用参数 → 无日志警告。"""
        args = _make_args(use_gpu=True)
        self.assertTrue(validate_args(args))
        mock_logging.getLogger.return_value.warning.assert_not_called()

    @patch("src.cli.validation.logging")
    def test_gpu_mode_window_size_custom_warning(self, mock_logging):
        """GPU 模式 + --window-size 非默认 → 警告。"""
        args = _make_args(use_gpu=True, window_size=7)
        self.assertTrue(validate_args(args))
        mock_logging.getLogger.return_value.warning.assert_called()

    @patch("src.cli.validation.logging")
    def test_gpu_mode_no_simd_warning(self, mock_logging):
        """GPU 模式 + --no-simd → 日志警告。"""
        args = _make_args(use_gpu=True, no_simd=True)
        self.assertTrue(validate_args(args))
        mock_logging.getLogger.return_value.warning.assert_called()

    @patch("src.cli.validation.logging")
    def test_gpu_mode_no_memory_pool_warning(self, mock_logging):
        """GPU 模式 + --no-memory-pool → 日志警告。"""
        args = _make_args(use_gpu=True, no_memory_pool=True)
        self.assertTrue(validate_args(args))
        mock_logging.getLogger.return_value.warning.assert_called()

    # ── 9. checkpoint-interval 自动启用 checkpoint ──

    def test_checkpoint_interval_auto_enable(self):
        """指定 --checkpoint-interval 但未启 --checkpoint → 自动启用。"""
        args = _make_args(checkpoint_interval=60, checkpoint=False)
        self.assertTrue(validate_args(args))
        self.assertTrue(args.checkpoint)

    def test_checkpoint_interval_default_no_auto_enable(self):
        """checkpoint-interval 为默认值时不自动启用 checkpoint。"""
        args = _make_args(
            checkpoint_interval=DEFAULT_CHECKPOINT_INTERVAL, checkpoint=False
        )
        validate_args(args)
        self.assertFalse(args.checkpoint)

    # ── 10. dedup-max-size 自动启用 dedup ──

    def test_dedup_max_size_auto_enable(self):
        """指定 --dedup-max-size 但未启 --dedup → 自动启用。"""
        args = _make_args(dedup_max_size=500000, dedup=False)
        self.assertTrue(validate_args(args))
        self.assertTrue(args.dedup)

    def test_dedup_max_size_default_no_auto_enable(self):
        """dedup-max-size 为默认值时不自动启用 dedup。"""
        args = _make_args(
            dedup_max_size=DEFAULT_DEDUP_MAX_SIZE, dedup=False
        )
        validate_args(args)
        self.assertFalse(args.dedup)

    # ── 11. window-size 范围验证 ──

    def test_window_size_below_min(self):
        """--window-size < 4 → False。"""
        args = _make_args(window_size=3)
        self.assertFalse(validate_args(args))

    def test_window_size_above_max(self):
        """--window-size > 8 → False。"""
        args = _make_args(window_size=9)
        self.assertFalse(validate_args(args))

    def test_window_size_boundary_4(self):
        """--window-size = 4 (下界) → True。"""
        args = _make_args(window_size=4)
        self.assertTrue(validate_args(args))

    def test_window_size_boundary_8(self):
        """--window-size = 8 (上界) → True。"""
        args = _make_args(window_size=8)
        self.assertTrue(validate_args(args))

    # ── 12. workers 检查 ──

    def test_workers_lt_1(self):
        """--workers < 1 → False。"""
        args = _make_args(workers=0)
        self.assertFalse(validate_args(args))

    def test_workers_negative(self):
        """--workers = -1 → False。"""
        args = _make_args(workers=-1)
        self.assertFalse(validate_args(args))

    # ── 13. duration 检查 ──

    def test_duration_negative(self):
        """--duration < 0 → False。"""
        args = _make_args(duration=-1)
        self.assertFalse(validate_args(args))

    def test_duration_zero_valid(self):
        """--duration = 0 → True。"""
        args = _make_args(duration=0)
        self.assertTrue(validate_args(args))

    # ── 14. 全合法参数 → True ──

    def test_all_valid_random_mode(self):
        """random 模式所有参数合法 → True。"""
        args = _make_args(mode="random")
        self.assertTrue(validate_args(args))

    def test_brute_force_mode_valid(self):
        """brute_force 模式合法参数 → True。"""
        args = _make_args(mode="brute_force", start="AABBCCDD")
        self.assertTrue(validate_args(args))

    def test_range_mode_full_valid(self):
        """range 模式完整合法参数 → True。"""
        args = _make_args(
            mode="range",
            start="1",
            end="FF",
            checkpoint_interval=60,
            window_size=6,
            workers=4,
            duration=3600,
        )
        self.assertTrue(validate_args(args))


# ── TestGetOutput ──────────────────────────────────────────────


class TestGetOutput(unittest.TestCase):
    """_get_output() 延迟导入测试。"""

    @patch("src.cli.output.CLIOutput")
    def test_get_output_returns_singleton(self, mock_cls):
        """_get_output 返回 CLIOutput 单例。"""
        instance = _get_output()
        self.assertIs(instance, mock_cls.get_instance.return_value)


# ── TestValidateFilePath ───────────────────────────────────────


class TestValidateFilePath(unittest.TestCase):
    """validate_file_path() 全覆盖。"""

    def setUp(self):
        self.mock_output = _make_mock_output()
        patcher = patch(
            "src.cli.validation._get_output", return_value=self.mock_output
        )
        self.addCleanup(patcher.stop)
        patcher.start()

    def _temp_file(self, content="test"):
        """创建临时文件并返回路径 (Pytest-style tempfile)。"""
        fd, path = tempfile.mkstemp()
        os.close(fd)
        with open(path, "w") as f:
            f.write(content)
        self.addCleanup(os.unlink, path)
        return path

    def test_file_exists_and_readable(self):
        """存在的可读文件 → True。"""
        path = self._temp_file()
        self.assertTrue(validate_file_path(path))

    def test_file_not_exists(self):
        """不存在的文件 → False。"""
        self.assertFalse(validate_file_path("/nonexistent/path/to/file.txt"))

    def test_path_is_directory(self):
        """路径是目录 → False。"""
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(os.rmdir, tmpdir)
        self.assertFalse(validate_file_path(tmpdir))

    def test_file_no_read_permission(self):
        """文件无读权限 → False (Unix-only, mock os.access)。"""
        with patch("os.access", return_value=False), patch(
            "pathlib.Path.exists", return_value=True
        ), patch("pathlib.Path.is_file", return_value=True):
            self.assertFalse(validate_file_path("unreadable_file.txt"))

    def test_large_file_warning(self):
        """大文件 (>100MB) → True + 警告。"""
        with patch(
            "pathlib.Path.stat"
        ) as mock_stat, patch(
            "pathlib.Path.exists", return_value=True
        ), patch(
            "pathlib.Path.is_file", return_value=True
        ), patch(
            "os.access", return_value=True
        ):
            mock_stat.return_value.st_size = 200 * 1024 * 1024  # 200 MB
            self.assertTrue(validate_file_path("large_file.txt"))
            self.mock_output.warning.assert_called()

    def test_small_file_no_warning(self):
        """小文件 (<100MB) → True, 无 error 无 warning。"""
        path = self._temp_file("hello")
        result = validate_file_path(path)
        self.assertTrue(result)
        self.mock_output.error.assert_not_called()
        self.mock_output.warning.assert_not_called()

    def test_stat_oserror_ignored(self):
        """stat() 抛出 OSError → 忽略, 仍返回 True。"""
        with patch(
            "pathlib.Path.stat", side_effect=OSError("permission denied")
        ), patch("pathlib.Path.exists", return_value=True), patch(
            "pathlib.Path.is_file", return_value=True
        ), patch(
            "os.access", return_value=True
        ):
            self.assertTrue(validate_file_path("broken_stat.txt"))


# ── Integration Tests ──────────────────────────────────────────


class TestValidateArgsWithRealFilePath(unittest.TestCase):
    """validate_args 与 validate_file_path 集成测试。"""

    def setUp(self):
        self.mock_output = _make_mock_output()
        patcher = patch(
            "src.cli.validation._get_output", return_value=self.mock_output
        )
        self.addCleanup(patcher.stop)
        patcher.start()

    def _temp_file(self, content="AABBCCDDEEFF"):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        with open(path, "w") as f:
            f.write(content)
        self.addCleanup(os.unlink, path)
        return path

    def test_file_arg_with_real_file_valid(self):
        """-f 指定真实文件 → 验证通过。"""
        path = self._temp_file()
        args = _make_args(targets=None, file=path)
        self.assertTrue(validate_args(args))

    def test_file_arg_with_invalid_path(self):
        """-f 指定不存在文件 → 验证失败。"""
        args = _make_args(targets=None, file="/no/such/file.txt")
        self.assertFalse(validate_args(args))
