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

import os
import sys
import json
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


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
        """文件不存在时应退出"""
        from src.cli.commands import _cmd_validate_addresses
        with patch.object(sys, 'exit') as mock_exit, \
             patch('src.cli.commands.validate_file_path', return_value=True):
            _cmd_validate_addresses(os.path.join(temp_dir, "nonexistent.txt"))
            mock_exit.assert_called_once_with(1)

    def test_empty_file(self, temp_dir):
        """空文件应正常退出"""
        from src.cli.commands import _cmd_validate_addresses
        target_file = os.path.join(temp_dir, "empty.txt")
        with open(target_file, "w") as f:
            f.write("# just a comment\n")

        with patch.object(sys, 'exit') as mock_exit, \
             patch('src.cli.commands.validate_file_path', return_value=True):
            _cmd_validate_addresses(target_file)
            mock_exit.assert_called_once_with(0)

    def test_validates_addresses(self, temp_dir):
        """有地址时应正常处理"""
        from src.cli.commands import _cmd_validate_addresses
        target_file = os.path.join(temp_dir, "addresses.txt")
        with open(target_file, "w") as f:
            f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
            f.write("invalid_address_xxx\n")

        with patch.object(sys, 'exit') as mock_exit, \
             patch('src.cli.commands.validate_file_path', return_value=True):
            _cmd_validate_addresses(target_file)
            # 不应因错误退出
            call_args = mock_exit.call_args
            if call_args:
                assert call_args[0][0] == 0

    def test_path_validation_fails(self):
        """路径验证失败应提前返回"""
        from src.cli.commands import _cmd_validate_addresses
        with patch('src.cli.commands.validate_file_path', return_value=False):
            # 不应进入文件读取逻辑
            _cmd_validate_addresses("/invalid/../path")


# ============================================================================
# _cmd_config_check 测试
# ============================================================================

@pytest.mark.unit
class TestCmdConfigCheck:
    """配置检查命令测试"""

    def test_config_not_exists(self):
        """配置文件不存在时"""
        from src.cli.commands import _cmd_config_check
        with patch('src.cli.commands.CONFIG_FILE_NAME', 'nonexistent_config_test.json'), \
             patch('src.cli.commands.CONFIG_EXAMPLE_FILE', 'nonexistent_example_test.json'), \
             patch('src.utils.platform_utils.PlatformUtils.ensure_utf8_output'):
            _cmd_config_check()  # 不应崩溃

    def test_config_valid(self, temp_dir):
        """有效配置文件"""
        from src.cli.commands import _cmd_config_check
        import src.cli.commands as commands_module

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

        with patch.object(commands_module, 'CONFIG_FILE_NAME', config_path), \
             patch.object(commands_module, 'CONFIG_EXAMPLE_FILE', 'no_example.json'), \
             patch('src.utils.platform_utils.PlatformUtils.ensure_utf8_output'):
            _cmd_config_check()  # 不应崩溃

    def test_config_invalid_json(self, temp_dir):
        """无效 JSON 配置"""
        from src.cli.commands import _cmd_config_check
        import src.cli.commands as commands_module

        config_path = os.path.join(temp_dir, "invalid.json")
        with open(config_path, "w") as f:
            f.write("not valid json")

        with patch.object(commands_module, 'CONFIG_FILE_NAME', config_path), \
             patch.object(commands_module, 'CONFIG_EXAMPLE_FILE', 'no_example.json'), \
             patch('src.utils.platform_utils.PlatformUtils.ensure_utf8_output'):
            _cmd_config_check()  # 不应崩溃


# ============================================================================
# _save_address_to_targets_file 测试
# ============================================================================

@pytest.mark.unit
class TestSaveAddressToTargetsFile:
    """地址保存测试"""

    def test_creates_new_file(self, temp_dir):
        from src.cli.commands import _save_address_to_targets_file, DEFAULT_TARGETS_FILE
        import src.cli.commands as commands_module

        targets_path = os.path.join(temp_dir, "targets_test.txt")
        mock_output = MagicMock()

        with patch.object(commands_module, 'DEFAULT_TARGETS_FILE', targets_path):
            _save_address_to_targets_file("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", mock_output)

        assert os.path.exists(targets_path)
        with open(targets_path, "r") as f:
            content = f.read()
        assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in content

    def test_skips_duplicate(self, temp_dir):
        from src.cli.commands import _save_address_to_targets_file
        import src.cli.commands as commands_module

        targets_path = os.path.join(temp_dir, "dup_targets.txt")
        addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        with open(targets_path, "w") as f:
            f.write(addr + "\n")

        mock_output = MagicMock()
        with patch.object(commands_module, 'DEFAULT_TARGETS_FILE', targets_path):
            _save_address_to_targets_file(addr, mock_output)

        # 不应重复添加
        with open(targets_path, "r") as f:
            lines = f.readlines()
        addr_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
        assert addr_lines.count(addr) == 1


# ============================================================================
# _handle_info_commands / _handle_system_commands 测试
# ============================================================================

@pytest.mark.unit
class TestHandleInfoCommands:
    """信息命令分发测试"""

    def test_examples_command(self):
        from src.cli.commands import _handle_info_commands
        args = Mock()
        args.examples = True
        args.config_check = False
        args.template = None
        args.recommend = False
        with patch.object(sys, 'exit') as mock_exit:
            result = _handle_info_commands(args)
        assert result is True
        mock_exit.assert_called_once_with(0)

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
        from src.cli.commands import _handle_system_commands
        args = Mock()
        args.health_check = False
        args.platform_check = False
        args.cleanup = False
        args.validate_addresses = "test.txt"
        args.migrate_config = False
        with patch('src.cli.commands._cmd_validate_addresses') as mock_cmd, \
             patch.object(sys, 'exit') as mock_exit:
            result = _handle_system_commands(args)
        assert result is True
        mock_cmd.assert_called_once_with("test.txt")
        mock_exit.assert_called_once_with(0)

    def test_migrate_config_command(self):
        from src.cli.commands import _handle_system_commands
        args = Mock()
        args.health_check = False
        args.platform_check = False
        args.cleanup = False
        args.validate_addresses = None
        args.migrate_config = True
        with patch('src.cli.config_migration.migrate_config_file', return_value=True), \
             patch.object(sys, 'exit') as mock_exit:
            result = _handle_system_commands(args)
        assert result is True
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
        with patch.object(sys, 'exit') as mock_exit:
            result = _dispatch_utility_commands(args)
        assert result is True

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
        with patch('src.cli.commands.Path', wraps=Path) as mock_path:
            result = _dispatch_utility_commands(args)
        assert result is False
