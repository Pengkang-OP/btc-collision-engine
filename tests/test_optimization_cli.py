"""optimization_cli.py 单元测试。

测试 print_settings() 和 main() 的 CLI 输出。
"""

import copy
import io
import os
import sys
import unittest
from unittest.mock import patch

from src.cli.optimization_cli import main, print_settings
from src.config.optimization_config import optimization_config

_ENV_KEYS = (
    "OPTIMIZE_DELTA_STATS",
    "OPTIMIZE_DISTRIBUTED",
    "OPTIMIZE_MONITOR",
    "DELTA_FLUSH_INTERVAL",
    "AGGREGATOR_INTERVAL",
    "MONITOR_INTERVAL",
)


def _save_and_clear_env():
    """保存并清除优化相关环境变量。"""
    saved = {}
    for k in _ENV_KEYS:
        saved[k] = os.environ.pop(k, None)
    return saved


def _restore_env(saved):
    """恢复环境变量。"""
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        elif k in os.environ:
            del os.environ[k]


class TestPrintSettings(unittest.TestCase):
    """测试 print_settings 输出。"""

    def setUp(self):
        """保存全局配置状态并清理环境变量，重置为已知默认值。"""
        self._env_saved = _save_and_clear_env()
        self._config_saved = copy.deepcopy(optimization_config._config)
        # 重置为纯默认值（不受 import 时环境变量影响）
        optimization_config._config = {
            "delta_stats_enabled": True,
            "distributed_aggregator_enabled": True,
            "performance_monitor_enabled": True,
            "delta_stats_flush_interval": 0.1,
            "aggregator_interval": 0.1,
            "monitor_interval": 1.0,
            "alert_thresholds": {
                "latency_ms": 100.0,
                "lock_contention": 0.5,
                "memory_mb": 512.0,
                "cpu_usage": 80.0,
            },
        }

    def tearDown(self):
        """恢复全局配置和环境变量。"""
        optimization_config._config = self._config_saved
        _restore_env(self._env_saved)

    def test_print_settings_contains_title(self):
        """print_settings 输出包含标题。"""
        stdout_buf = io.StringIO()
        with patch.object(sys, "stdout", stdout_buf):
            print_settings()
        output = stdout_buf.getvalue()
        self.assertIn("优化设置", output)

    def test_print_settings_shows_enabled_features(self):
        """print_settings 输出包含功能开关区域和状态。"""
        stdout_buf = io.StringIO()
        with patch.object(sys, "stdout", stdout_buf):
            print_settings()
        output = stdout_buf.getvalue()
        self.assertIn("功能开关", output)
        self.assertIn("增量统计优化", output)
        self.assertIn("分布式统计聚合", output)
        self.assertIn("性能监控", output)
        self.assertIn("✅ 启用", output)

    def test_print_settings_shows_config_params(self):
        """print_settings 输出包含配置参数区域。"""
        stdout_buf = io.StringIO()
        with patch.object(sys, "stdout", stdout_buf):
            print_settings()
        output = stdout_buf.getvalue()
        self.assertIn("配置参数", output)
        self.assertIn("增量统计刷新间隔", output)

    def test_print_settings_shows_default_float_values(self):
        """print_settings 输出包含默认浮点值。"""
        stdout_buf = io.StringIO()
        with patch.object(sys, "stdout", stdout_buf):
            print_settings()
        output = stdout_buf.getvalue()
        # delta_stats_flush_interval 和 aggregator_interval 默认均为 0.1
        self.assertIn("0.1", output)
        self.assertIn("1.0", output)  # monitor_interval


class TestMain(unittest.TestCase):
    """测试 main() CLI 命令处理。"""

    def setUp(self):
        """保存全局配置状态并清理环境变量，重置为已知默认值。"""
        self._env_saved = _save_and_clear_env()
        self._config_saved = copy.deepcopy(optimization_config._config)
        optimization_config._config = {
            "delta_stats_enabled": True,
            "distributed_aggregator_enabled": True,
            "performance_monitor_enabled": True,
            "delta_stats_flush_interval": 0.1,
            "aggregator_interval": 0.1,
            "monitor_interval": 1.0,
            "alert_thresholds": {
                "latency_ms": 100.0,
                "lock_contention": 0.5,
                "memory_mb": 512.0,
                "cpu_usage": 80.0,
            },
        }

    def tearDown(self):
        """恢复全局配置和环境变量。"""
        optimization_config._config = self._config_saved
        _restore_env(self._env_saved)

    def test_main_enable_feature(self):
        """--enable delta_stats 启用功能并打印确认，不走 print_settings。"""
        test_args = ["prog", "--enable", "delta_stats"]
        stdout_buf = io.StringIO()
        with patch.object(sys, "argv", test_args), patch.object(sys, "stdout", stdout_buf):
            main()
        output = stdout_buf.getvalue()
        self.assertIn("已启用: delta_stats", output)
        self.assertNotIn("优化设置", output)
        self.assertTrue(optimization_config.get("delta_stats_enabled"))

    def test_main_disable_feature(self):
        """--disable performance_monitor 禁用功能并打印确认，不走 print_settings。"""
        test_args = ["prog", "--disable", "performance_monitor"]
        stdout_buf = io.StringIO()
        with patch.object(sys, "argv", test_args), patch.object(sys, "stdout", stdout_buf):
            main()
        output = stdout_buf.getvalue()
        self.assertIn("已禁用: performance_monitor", output)
        self.assertNotIn("优化设置", output)
        self.assertFalse(optimization_config.get("performance_monitor_enabled"))

    def test_main_list_features(self):
        """--list 列出可用功能，不走 print_settings。"""
        test_args = ["prog", "--list"]
        stdout_buf = io.StringIO()
        with patch.object(sys, "argv", test_args), patch.object(sys, "stdout", stdout_buf):
            main()
        output = stdout_buf.getvalue()
        self.assertIn("可用的优化功能", output)
        self.assertIn("delta_stats", output)
        self.assertIn("distributed_aggregator", output)
        self.assertIn("performance_monitor", output)
        self.assertNotIn("优化设置", output)

    def test_main_no_args_shows_settings(self):
        """无参数时默认显示当前设置。"""
        test_args = ["prog"]
        stdout_buf = io.StringIO()
        with patch.object(sys, "argv", test_args), patch.object(sys, "stdout", stdout_buf):
            main()
        output = stdout_buf.getvalue()
        self.assertIn("优化设置", output)

    def test_main_enable_invalid_choice_exits(self):
        """--enable 非法选项时 argparse 触发 SystemExit(2)。"""
        test_args = ["prog", "--enable", "nonexistent"]
        stderr_buf = io.StringIO()
        with patch.object(sys, "argv", test_args), patch.object(sys, "stderr", stderr_buf):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 2)

    def test_main_disable_invalid_choice_exits(self):
        """--disable 非法选项时 argparse 触发 SystemExit(2)。"""
        test_args = ["prog", "--disable", "nonexistent"]
        stderr_buf = io.StringIO()
        with patch.object(sys, "argv", test_args), patch.object(sys, "stderr", stderr_buf):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
