#!/usr/bin/env python3
"""CLI命令模块 (commands) 单元测试

覆盖：
- QUICK_RUN_DEFAULTS / PREVIEW_CONFIG 常量
- _format_device_label 格式化
- _cmd_validate_addresses 地址验证命令
- _cmd_config_check 配置检查命令
- _save_address_to_targets_file 地址保存
- _handle_info_commands / _handle_system_commands 命令分发
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# ============================================================================
# 常量测试
# ============================================================================


@pytest.mark.unit
class TestConstants:
    """常量定义测试"""

    def test_quick_run_defaults(self):
        from src.cli.commands import QUICK_RUN_DEFAULTS

        assert QUICK_RUN_DEFAULTS["target_file"] == "targets.txt"
        assert QUICK_RUN_DEFAULTS["mode"] == "random"
        assert QUICK_RUN_DEFAULTS["checkpoint"] is True
        assert QUICK_RUN_DEFAULTS["dedup"] is True
        assert QUICK_RUN_DEFAULTS["duration"] == 0
        assert QUICK_RUN_DEFAULTS["countdown_seconds"] == 3

    def test_preview_config(self):
        from src.cli.commands import PREVIEW_CONFIG

        assert PREVIEW_CONFIG["max_preview_addresses"] == 3
        assert PREVIEW_CONFIG["max_address_display_length"] == 20


# ============================================================================
# _format_device_label 测试
# ============================================================================


@pytest.mark.unit
class TestFormatDeviceLabel:
    """设备标签格式化测试"""

    def test_format_with_memory_gb(self):
        from src.cli.commands import _format_device_label

        device = {"name": "Intel Arc A770", "global_mem_size": 16 * 1024**3}
        label = _format_device_label(device, 0)
        assert "Intel Arc A770" in label
        assert "16GB" in label

    def test_format_with_memory_mb(self):
        from src.cli.commands import _format_device_label

        device = {"name": "Test GPU", "global_mem_size": 512 * 1024**2}
        label = _format_device_label(device, 0)
        assert "Test GPU" in label
        assert "512MB" in label

    def test_format_without_memory(self):
        from src.cli.commands import _format_device_label

        device = {"name": "Unknown GPU"}
        label = _format_device_label(device, 0)
        assert label == "Unknown GPU"

    def test_format_zero_memory(self):
        from src.cli.commands import _format_device_label

        device = {"name": "GPU", "global_mem_size": 0}
        label = _format_device_label(device, 1)
        assert label == "GPU"


# ============================================================================
# _cmd_validate_addresses 测试
# ============================================================================


@pytest.mark.unit
class TestCmdValidateAddresses:
    """地址验证命令测试"""

    def test_file_not_found_exits(self, temp_dir):
        """文件不存在时应退出（sys.exit 被 mock 后函数会继续执行到多次 exit）"""
        from src.cli.commands import _cmd_validate_addresses

        with (
            patch.object(sys, "exit") as mock_exit,
            patch("src.cli.commands.validate_file_path", return_value=True),
        ):
            _cmd_validate_addresses(os.path.join(temp_dir, "nonexistent.txt"))
            # sys.exit(1) 应至少被调用一次
            mock_exit.assert_any_call(1)

    def test_empty_file(self, temp_dir):
        """空文件应正常退出"""
        from src.cli.commands import _cmd_validate_addresses

        target_file = os.path.join(temp_dir, "empty.txt")
        with open(target_file, "w") as f:
            f.write("# just a comment\n")

        with (
            patch.object(sys, "exit") as mock_exit,
            patch("src.cli.commands.validate_file_path", return_value=True),
        ):
            _cmd_validate_addresses(target_file)
            mock_exit.assert_called_once_with(0)

    def test_validates_addresses(self, temp_dir):
        """有地址时应正常处理"""
        from src.cli.commands import _cmd_validate_addresses

        target_file = os.path.join(temp_dir, "addresses.txt")
        with open(target_file, "w") as f:
            f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
            f.write("invalid_address_xxx\n")

        with (
            patch.object(sys, "exit") as mock_exit,
            patch("src.cli.commands.validate_file_path", return_value=True),
        ):
            _cmd_validate_addresses(target_file)
            # 不应因错误退出
            call_args = mock_exit.call_args
            if call_args:
                assert call_args[0][0] == 0

    def test_path_validation_fails(self):
        """路径验证失败应调用 sys.exit(1) 提前退出，不读文件"""
        from src.cli.commands import _cmd_validate_addresses

        with (
            patch("src.cli.commands.validate_file_path", return_value=False),
            patch("builtins.open") as mock_open,
        ):
            with pytest.raises(SystemExit):
                _cmd_validate_addresses("/invalid/../path")
            # 验证提前退出：不应打开文件
            mock_open.assert_not_called()


# ============================================================================
# _cmd_config_check 测试
# ============================================================================


@pytest.mark.unit
class TestCmdConfigCheck:
    """配置检查命令测试"""

    def test_config_not_exists(self):
        """配置文件不存在时"""
        from src.cli.commands import _cmd_config_check

        with (
            patch("src.cli.commands.CONFIG_FILE_NAME", "nonexistent_config_test.json"),
            patch("src.cli.commands.CONFIG_EXAMPLE_FILE", "nonexistent_example_test.json"),
            patch("src.utils.platform_utils.PlatformUtils.ensure_utf8_output"),
        ):
            _cmd_config_check()  # 不应崩溃

    def test_config_valid(self, temp_dir):
        """有效配置文件"""
        import src.cli.commands as commands_module
        from src.cli.commands import _cmd_config_check

        config_path = os.path.join(temp_dir, "config_test.json")
        config = {
            "crypto": {},
            "collision": {},
            "logging": {},
            "gpu": {},
            "monitoring": {},
            "engine": {},
        }
        with open(config_path, "w") as f:
            json.dump(config, f)

        with (
            patch.object(commands_module, "CONFIG_FILE_NAME", config_path),
            patch.object(commands_module, "CONFIG_EXAMPLE_FILE", "no_example.json"),
            patch("src.utils.platform_utils.PlatformUtils.ensure_utf8_output"),
        ):
            _cmd_config_check()  # 不应崩溃

    def test_config_invalid_json(self, temp_dir):
        """无效 JSON 配置"""
        import src.cli.commands as commands_module
        from src.cli.commands import _cmd_config_check

        config_path = os.path.join(temp_dir, "invalid.json")
        with open(config_path, "w") as f:
            f.write("not valid json")

        with (
            patch.object(commands_module, "CONFIG_FILE_NAME", config_path),
            patch.object(commands_module, "CONFIG_EXAMPLE_FILE", "no_example.json"),
            patch("src.utils.platform_utils.PlatformUtils.ensure_utf8_output"),
        ):
            _cmd_config_check()  # 不应崩溃


# ============================================================================
# _save_address_to_targets_file 测试
# ============================================================================


@pytest.mark.unit
class TestSaveAddressToTargetsFile:
    """地址保存测试"""

    def test_creates_new_file(self, temp_dir):
        import src.cli.commands as commands_module
        from src.cli.commands import _save_address_to_targets_file

        targets_path = os.path.join(temp_dir, "targets_test.txt")
        mock_output = MagicMock()

        # 确保目标文件不存在
        if os.path.exists(targets_path):
            os.remove(targets_path)

        with patch.object(commands_module, "DEFAULT_TARGETS_FILE", targets_path):
            _save_address_to_targets_file("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", mock_output)

        assert os.path.exists(targets_path)
        with open(targets_path, encoding="utf-8") as f:
            content = f.read()
        assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in content

    def test_skips_duplicate(self, temp_dir):
        import src.cli.commands as commands_module
        from src.cli.commands import _save_address_to_targets_file

        targets_path = os.path.join(temp_dir, "dup_targets.txt")
        addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        with open(targets_path, "w") as f:
            f.write(addr + "\n")

        mock_output = MagicMock()
        with patch.object(commands_module, "DEFAULT_TARGETS_FILE", targets_path):
            _save_address_to_targets_file(addr, mock_output)

        # 不应重复添加
        with open(targets_path) as f:
            lines = f.readlines()
        addr_lines = [
            line.strip()
            for line in lines
            if line.strip() and not line.strip().startswith("#")
        ]
        assert addr_lines.count(addr) == 1


# ============================================================================
# _handle_info_commands / _handle_system_commands 测试
# ============================================================================


@pytest.mark.unit
class TestHandleInfoCommands:
    """信息命令分发测试"""

    def test_examples_command(self):
        """examples 命令：sys.exit 被 mock 后函数不会真正退出，返回值可能为 False"""
        from src.cli.commands import _handle_info_commands

        args = Mock()
        args.examples = True
        args.config_check = False
        args.template = None
        args.recommend = False
        with (
            patch("src.cli.commands._cmd_examples") as mock_cmd,
            patch.object(sys, "exit") as mock_exit,
        ):
            _handle_info_commands(args)
        # sys.exit 被调用即说明匹配到了命令
        mock_exit.assert_called_once_with(0)
        mock_cmd.assert_called_once()

    def test_no_info_command(self):
        from src.cli.commands import _handle_info_commands

        args = Mock()
        args.examples = False
        args.config_check = False
        args.template = None
        args.recommend = False
        result = _handle_info_commands(args)
        assert result is False


@pytest.mark.unit
class TestHandleSystemCommands:
    """系统命令分发测试"""

    def test_validate_addresses_command(self):
        """validate-addresses 命令：sys.exit 被 mock 后函数继续执行，验证命令被调用即可"""
        from src.cli.commands import _handle_system_commands

        args = Mock()
        args.health_check = False
        args.platform_check = False
        args.cleanup = False
        args.validate_addresses = "test.txt"
        args.migrate_config = False
        with (
            patch("src.cli.commands._cmd_validate_addresses") as mock_cmd,
            patch.object(sys, "exit") as mock_exit,
        ):
            _handle_system_commands(args)
        mock_cmd.assert_called_once_with("test.txt")
        mock_exit.assert_called_once_with(0)

    def test_migrate_config_command(self):
        """migrate-config 命令：sys.exit 被 mock 后函数继续执行，验证 migrate_config_file 被调用即可"""
        from src.cli.commands import _handle_system_commands

        args = Mock()
        args.health_check = False
        args.platform_check = False
        args.cleanup = False
        args.validate_addresses = None
        args.migrate_config = True
        with (
            patch("src.cli.config_migration.migrate_config_file", return_value=True) as mock_migrate,
            patch.object(sys, "exit") as mock_exit,
        ):
            _handle_system_commands(args)
        mock_migrate.assert_called_once()
        mock_exit.assert_called_once_with(0)

    def test_no_system_command(self):
        from src.cli.commands import _handle_system_commands

        args = Mock()
        args.health_check = False
        args.platform_check = False
        args.cleanup = False
        args.validate_addresses = None
        args.migrate_config = False
        result = _handle_system_commands(args)
        assert result is False


# ============================================================================
# _dispatch_utility_commands 测试
# ============================================================================


@pytest.mark.unit
class TestDispatchUtilityCommands:
    """工具命令调度测试"""

    def test_dispatches_to_info(self):
        """调度到信息命令：sys.exit 被 mock 后函数继续执行，验证 _cmd_examples 被调用即可"""
        from src.cli.commands import _dispatch_utility_commands

        args = Mock()
        args.examples = True
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
        with (
            patch("src.cli.commands._cmd_examples") as mock_cmd,
            patch.object(sys, "exit") as mock_exit,
        ):
            _dispatch_utility_commands(args)
        mock_cmd.assert_called_once()
        mock_exit.assert_called_once_with(0)

    def test_no_match_returns_false(self):
        from src.cli.commands import _dispatch_utility_commands

        args = Mock()
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
        # 需要 mock Path 来绕过首次运行检测
        with patch("src.cli.commands.Path", wraps=Path) as mock_path:  # noqa: F841
            result = _dispatch_utility_commands(args)
        assert result is False
