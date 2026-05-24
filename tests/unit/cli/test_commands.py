"""CLI 工具命令 (commands.py) 单元测试。

覆盖范围：
- _cmd_examples: 示例输出
- _cmd_config_check: 配置检查
- _cmd_validate_addresses: 地址验证
- 命令分发逻辑
- 快速启动向导核心流程
- 快速运行模式核心流程
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cli.commands import (
    _dispatch_utility_commands,
    _handle_info_commands,
    _handle_system_commands,
    _handle_wizard_and_quickstart,
)


# ============================================================================
# _handle_info_commands
# ============================================================================


class TestHandleInfoCommands:
    """信息类工具命令测试。"""

    def test_examples_calls_cmd_examples(self):
        """--examples 调用 _cmd_examples 并退出。"""
        args = MagicMock()
        args.examples = True
        args.config_check = False
        args.template = None
        args.recommend = False

        with patch("src.cli.commands._cmd_examples") as mock_cmd:
            with pytest.raises(SystemExit):
                _handle_info_commands(args)
            mock_cmd.assert_called_once()

    def test_config_check_calls_cmd_config_check(self):
        """--config-check 调用 _cmd_config_check 并退出。"""
        args = MagicMock()
        args.examples = False
        args.config_check = True
        args.template = None
        args.recommend = False

        with patch("src.cli.commands._cmd_config_check") as mock_cmd:
            with pytest.raises(SystemExit):
                _handle_info_commands(args)
            mock_cmd.assert_called_once()

    def test_template_applies_and_exits_success(self):
        """--template 有效名称应用成功。"""
        args = MagicMock()
        args.examples = False
        args.config_check = False
        args.template = "quick-test"
        args.recommend = False

        # apply_template 在函数内延迟导入 from src.cli.advanced_features
        with patch("src.cli.advanced_features.apply_template", return_value=True):
            with pytest.raises(SystemExit) as exc_info:
                _handle_info_commands(args)
            assert exc_info.value.code == 0

    def test_template_applies_and_exits_failure(self):
        """--template 应用失败返回错误码。"""
        args = MagicMock()
        args.examples = False
        args.config_check = False
        args.template = "bad-template"
        args.recommend = False

        with patch("src.cli.advanced_features.apply_template", return_value=False):
            with pytest.raises(SystemExit) as exc_info:
                _handle_info_commands(args)
            assert exc_info.value.code == 1

    def test_recommend_shows_and_exits(self):
        """--recommend 显示推荐并退出。"""
        args = MagicMock()
        args.examples = False
        args.config_check = False
        args.template = None
        args.recommend = True

        # recommend_parameters 在函数内延迟导入
        with patch("src.cli.advanced_features.recommend_parameters") as mock_rec:
            mock_rec.return_value = {
                "recommendations": ["--use-gpu", "--workers 4"],
                "reasons": ["检测到 GPU", "4 核心推荐"],
            }
            with pytest.raises(SystemExit) as exc_info:
                _handle_info_commands(args)
            assert exc_info.value.code == 0
            mock_rec.assert_called_once_with(args)

    def test_no_info_command_returns_false(self):
        """无信息类命令时返回 False。"""
        args = MagicMock()
        args.examples = False
        args.config_check = False
        args.template = None
        args.recommend = False

        result = _handle_info_commands(args)
        assert result is False


# ============================================================================
# _handle_wizard_and_quickstart
# ============================================================================


class TestHandleWizardAndQuickstart:
    """向导和快速启动命令测试。"""

    def test_quick_run_dispatched(self):
        """--quick-run 被正确分发。"""
        args = MagicMock()
        args.quick_run = True
        args.quick_start = False
        args.compact = False

        with patch("src.cli.commands._cmd_quick_run") as mock_cmd:
            with pytest.raises(SystemExit):
                _handle_wizard_and_quickstart(args)
            mock_cmd.assert_called_once()

    def test_quick_start_dispatched(self):
        """--quick-start 被正确分发（含 compact）。"""
        args = MagicMock()
        args.quick_run = False
        args.quick_start = True
        args.compact = True

        with patch("src.cli.commands._cmd_quick_start") as mock_cmd:
            with pytest.raises(SystemExit):
                _handle_wizard_and_quickstart(args)
            mock_cmd.assert_called_once_with(executor=None, compact=True)

    def test_quick_start_compact_false(self):
        """--quick-start 不传 compact 时默认 False。"""
        args = MagicMock()
        args.quick_run = False
        args.quick_start = True
        args.compact = False

        with patch("src.cli.commands._cmd_quick_start") as mock_cmd:
            with pytest.raises(SystemExit):
                _handle_wizard_and_quickstart(args)
            mock_cmd.assert_called_once_with(executor=None, compact=False)

    def test_no_wizard_command_returns_false(self):
        """无向导/快速启动命令时返回 False。"""
        args = MagicMock()
        args.quick_run = False
        args.quick_start = False

        # 需要模拟 config.json 存在以避免触发首次运行检测
        with patch.object(Path, "exists", return_value=True):
            result = _handle_wizard_and_quickstart(args)
            assert result is False


# ============================================================================
# _handle_system_commands
# ============================================================================


class TestHandleSystemCommands:
    """系统工具命令测试。"""

    def test_health_check_dispatched(self):
        """--health-check 被正确分发。"""
        args = MagicMock()
        args.health_check = True
        args.platform_check = False
        args.cleanup = False
        args.validate_addresses = None

        # HealthChecker 在函数内延迟导入 from src.utils.health_check
        with patch("src.utils.health_check.HealthChecker") as mock_checker_cls:
            mock_checker = MagicMock()
            mock_checker.run_all_checks.return_value = {"check1": (True, "OK")}
            mock_checker_cls.return_value = mock_checker

            with pytest.raises(SystemExit) as exc_info:
                _handle_system_commands(args)
            assert exc_info.value.code == 0

    def test_health_check_fails_exits_with_error(self):
        """--health-check 检查失败返回错误码。"""
        args = MagicMock()
        args.health_check = True
        args.platform_check = False
        args.cleanup = False
        args.validate_addresses = None

        with patch("src.utils.health_check.HealthChecker") as mock_checker_cls:
            mock_checker = MagicMock()
            mock_checker.run_all_checks.return_value = {"check1": (False, "FAIL")}
            mock_checker_cls.return_value = mock_checker

            with pytest.raises(SystemExit) as exc_info:
                _handle_system_commands(args)
            assert exc_info.value.code == 1

    def test_platform_check_dispatched(self, capsys):
        """--platform-check 正确分发并成功完成。"""
        args = MagicMock()
        args.health_check = False
        args.platform_check = True
        args.cleanup = False
        args.validate_addresses = None

        # PlatformChecker 已实现，应成功退出
        with pytest.raises(SystemExit) as exc_info:
            _handle_system_commands(args)
        assert exc_info.value.code == 0

    def test_cleanup_dispatched(self):
        """--cleanup 被正确分发。"""
        args = MagicMock()
        args.health_check = False
        args.platform_check = False
        args.cleanup = True
        args.dry_run = False
        args.validate_addresses = None
        args.migrate_config = False

        with patch("src.utils.data_cleanup.DataCleaner") as mock_cleaner_cls:
            mock_cleaner = MagicMock()
            # DataCleaner.clean_all() returns int (file count)
            mock_cleaner.clean_all.return_value = 5
            mock_cleaner_cls.return_value = mock_cleaner

            with pytest.raises(SystemExit) as exc_info:
                _handle_system_commands(args)
            assert exc_info.value.code == 0
            mock_cleaner.clean_all.assert_called_once_with()

    def test_cleanup_dry_run(self):
        """--cleanup --dry-run 不会调用 clean_all()，只输出预览。"""
        args = MagicMock()
        args.health_check = False
        args.platform_check = False
        args.cleanup = True
        args.dry_run = True
        args.validate_addresses = None
        args.migrate_config = False

        with patch("src.utils.data_cleanup.DataCleaner") as mock_cleaner_cls:
            mock_cleaner = MagicMock()
            mock_cleaner.clean_all.return_value = 0
            mock_cleaner_cls.return_value = mock_cleaner

            with pytest.raises(SystemExit):
                _handle_system_commands(args)
            # dry_run 模式不应调用 clean_all()
            mock_cleaner.clean_all.assert_not_called()

    def test_no_system_command_returns_false(self):
        """无系统命令时返回 False。"""
        args = MagicMock()
        args.health_check = False
        args.platform_check = False
        args.cleanup = False
        args.validate_addresses = None
        args.migrate_config = False

        result = _handle_system_commands(args)
        assert result is False


# ============================================================================
# _dispatch_utility_commands
# ============================================================================


class TestDispatchUtilityCommands:
    """命令分发总入口测试。"""

    def test_dispatch_falls_through_all_handlers(self):
        """无任何命令时各处理器返回 False，最终返回 False。"""
        args = MagicMock()
        args.examples = False
        args.config_check = False
        args.template = None
        args.recommend = False
        args.quick_run = False
        args.quick_start = False
        args.health_check = False
        args.platform_check = False
        args.cleanup = False
        args.validate_addresses = None
        args.migrate_config = False

        with patch.object(Path, "exists", return_value=True):
            result = _dispatch_utility_commands(args)
            assert result is False


# ============================================================================
# _cmd_config_check
# ============================================================================


class TestCmdConfigCheck:
    """配置检查命令测试。"""

    def test_config_check_output(self, capsys):
        """--config-check 输出合理内容。"""
        from src.cli.commands import _cmd_config_check

        _cmd_config_check()
        captured = capsys.readouterr()
        # 应该包含配置检查相关输出
        output = captured.out
        assert "Config Check" in output or "config" in output.lower()


# ============================================================================
# _cmd_examples
# ============================================================================


class TestCmdExamples:
    """示例输出命令测试。"""

    def test_examples_output(self, capsys):
        """--examples 输出包含常见用例。"""
        from src.cli.commands import _cmd_examples

        _cmd_examples()
        captured = capsys.readouterr()
        output = captured.out
        assert "random" in output.lower()
        assert "GPU" in output or "gpu" in output.lower()
        assert "key_collision" in output


# ============================================================================
# Quick run / Quick start helper functions
# ============================================================================


class TestYNPrompt:
    """_yn_prompt 交互测试。"""

    def test_yn_prompt_yes(self):
        """输入 y 返回 True。"""
        from src.cli.commands import _yn_prompt

        mock_output = MagicMock()
        with patch("builtins.input", return_value="y"):
            result = _yn_prompt(mock_output, "Enable?")
            assert result is True

    def test_yn_prompt_no(self):
        """输入 n 返回 False。"""
        from src.cli.commands import _yn_prompt

        mock_output = MagicMock()
        with patch("builtins.input", return_value="n"):
            result = _yn_prompt(mock_output, "Enable?")
            assert result is False

    def test_yn_prompt_default_yes(self):
        """空输入默认返回 True。"""
        from src.cli.commands import _yn_prompt

        mock_output = MagicMock()
        with patch("builtins.input", return_value=""):
            result = _yn_prompt(mock_output, "Enable?")
            assert result is True


class TestDurationPrompt:
    """_duration_prompt 交互测试。"""

    def test_duration_prompt_unlimited(self):
        """选择1(无限)返回 0。"""
        from src.cli.commands import _duration_prompt

        mock_output = MagicMock()
        with patch("builtins.input", return_value="1"):
            result = _duration_prompt(mock_output)
            assert result == 0

    def test_duration_prompt_hours(self):
        """选择2 + 小时输入返回秒数。"""
        from src.cli.commands import _duration_prompt

        mock_output = MagicMock()
        with patch("builtins.input", side_effect=["2", "5"]):
            result = _duration_prompt(mock_output)
            assert result == 18000  # 5 * 3600

    def test_duration_prompt_days(self):
        """选择3 + 天数输入返回秒数。"""
        from src.cli.commands import _duration_prompt

        mock_output = MagicMock()
        with patch("builtins.input", side_effect=["3", "2"]):
            result = _duration_prompt(mock_output)
            assert result == 172800  # 2 * 86400


class TestQuickRunDefaults:
    """快速模式默认配置测试。"""

    def test_defaults_structure(self):
        """默认配置包含所有必要字段。"""
        from src.cli.commands import QUICK_RUN_DEFAULTS

        assert "target_file" in QUICK_RUN_DEFAULTS
        assert "mode" in QUICK_RUN_DEFAULTS
        assert "checkpoint" in QUICK_RUN_DEFAULTS
        assert "dedup" in QUICK_RUN_DEFAULTS
        assert "duration" in QUICK_RUN_DEFAULTS
        assert "countdown_seconds" in QUICK_RUN_DEFAULTS
        assert QUICK_RUN_DEFAULTS["mode"] == "random"

    def test_quick_run_config_summary(self):
        """配置摘要构建正确。"""
        from src.cli.commands import _quick_run_config_summary

        summary = _quick_run_config_summary("test_targets.txt")
        assert summary["目标文件"] == "test_targets.txt"
        assert "碰撞模式" in summary
        assert "断点续传" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
