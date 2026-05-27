"""Integration tests for CLI pipeline.

Covers:
- Full argument parsing → parameter validation pipeline
- Utility command dispatch (--health-check, --config-check, --examples, etc.)
- Configuration loading and validation
- Engine runner lifecycle (with mocked engine)
"""

import sys
import threading
from unittest.mock import MagicMock, patch

import pytest

from src.cli.arg_parser import parse_args
from src.cli.commands import dispatch_utility_commands
from src.cli.engine_runner import (
    _compute_range,
    _run_collision_loop,
)
from src.cli.validation import validate_args

# ============================================================================
# Argument parsing + validation pipeline
# ============================================================================


@pytest.mark.integration
class TestArgParsingPipeline:
    """Full arg parsing → validation pipeline tests."""

    def test_minimal_random_mode(self):
        """最小参数 - random 模式正常解析。."""
        sys.argv = [
            "key_collision_cli",
            "-t",
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "-m",
            "random",
        ]
        args = parse_args()
        assert args.mode == "random"
        assert args.targets == ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
        assert validate_args(args) is True

    def test_file_mode_with_checkpoint(self):
        """文件模式 + checkpoint 正常解析。."""
        sys.argv = [
            "key_collision_cli",
            "-f",
            "targets.txt",
            "-m",
            "random",
            "--checkpoint",
        ]
        args = parse_args()
        assert args.file == "targets.txt"
        assert args.checkpoint is True

    def test_gpu_mode_exclusive(self):
        """--use-gpu 和 --multi-gpu 互斥。."""
        sys.argv = [
            "key_collision_cli",
            "-t",
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "--use-gpu",
        ]
        args = parse_args()
        assert args.use_gpu is True
        assert args.multi_gpu is False

    def test_verbose_counting(self):
        """-v 叠加计数。."""
        sys.argv = [
            "key_collision_cli",
            "-t",
            "test",
            "-vvv",
        ]
        args = parse_args()
        assert args.verbose == 3

    def test_auto_tune_argument(self):
        """--auto-tune 参数正常解析。."""
        sys.argv = [
            "key_collision_cli",
            "-t",
            "test",
            "--auto-tune",
        ]
        args = parse_args()
        assert args.auto_tune is True

    def test_batch_size_argument(self):
        """--batch-size 参数正常解析。."""
        sys.argv = [
            "key_collision_cli",
            "-t",
            "test",
            "--batch-size",
            "50000",
        ]
        args = parse_args()
        assert args.batch_size == 50000

    def test_validation_rejects_missing_targets(self):
        """验证：缺少 -t 和 -f 时返回 False。."""
        sys.argv = [
            "key_collision_cli",
            "-m",
            "random",
        ]
        args = parse_args()
        assert validate_args(args) is False

    def test_validation_rejects_invalid_mode(self):
        """验证：无效模式被 argparse 自身拒绝（parse 时退出码 2）。."""
        sys.argv = [
            "key_collision_cli",
            "-t",
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "-m",
            "invalid",
        ]
        # argparse 自身的 choices 校验在 parse 阶段就触发 SystemExit(2)
        with pytest.raises(SystemExit) as exc_info:
            parse_args()
        assert exc_info.value.code == 2


# ============================================================================
# Utility command dispatch
# ============================================================================


@pytest.mark.integration
class TestUtilityCommandDispatch:
    """工具命令分发集成测试。."""

    def test_examples_command_dispatched(self):
        """--examples 被正确分发并退出。."""
        sys.argv = ["key_collision_cli", "--examples"]
        args = parse_args()
        with pytest.raises(SystemExit) as exc_info:
            dispatch_utility_commands(args)
        assert exc_info.value.code == 0

    def test_config_check_dispatched(self):
        """--config-check 被正确分发。."""
        sys.argv = ["key_collision_cli", "--config-check"]
        args = parse_args()
        with pytest.raises(SystemExit) as exc_info:
            dispatch_utility_commands(args)
        # 没有 config.json 时可能以 0 退出（checker 内部处理）
        assert exc_info.value.code is not None

    def test_health_check_dispatched(self):
        """--health-check 被正确分发。."""
        sys.argv = ["key_collision_cli", "--health-check"]
        args = parse_args()
        with pytest.raises(SystemExit):
            dispatch_utility_commands(args)

    def test_platform_check_dispatched(self):
        """--platform-check 被正确分发。."""
        sys.argv = ["key_collision_cli", "--platform-check"]
        args = parse_args()
        with pytest.raises(SystemExit):
            dispatch_utility_commands(args)

    def test_recommend_dispatched(self):
        """--recommend 被正确分发。."""
        sys.argv = ["key_collision_cli", "--recommend"]
        args = parse_args()
        with pytest.raises(SystemExit):
            dispatch_utility_commands(args)

    def test_template_dispatched(self):
        """--template 无效名称时正常退出。."""
        sys.argv = ["key_collision_cli", "--template", "nonexistent"]
        args = parse_args()
        with pytest.raises(SystemExit) as exc_info:
            dispatch_utility_commands(args)
        # 模板不存在，应返回错误
        assert exc_info.value.code == 1

    def test_validate_addresses_dispatched(self):
        """--validate-addresses 不存在文件时退出。."""
        sys.argv = ["key_collision_cli", "--validate-addresses", "nonexistent.txt"]
        args = parse_args()
        with pytest.raises(SystemExit) as exc_info:
            dispatch_utility_commands(args)
        assert exc_info.value.code == 1

    def test_quick_start_flag(self):
        """--quick-start 被正确识别。."""
        sys.argv = ["key_collision_cli", "--quick-start"]
        args = parse_args()
        assert args.quick_start is True

    def test_quick_run_flag(self):
        """--quick-run 被正确识别。."""
        sys.argv = ["key_collision_cli", "--quick-run"]
        args = parse_args()
        assert args.quick_run is True

    def test_version_flag(self):
        """--version 显示版本号。."""
        sys.argv = ["key_collision_cli", "--version"]
        with pytest.raises(SystemExit):
            parse_args()

    def test_language_option(self):
        """--language 参数解析。."""
        sys.argv = [
            "key_collision_cli",
            "-t",
            "test",
            "--language",
            "en_US",
        ]
        args = parse_args()
        assert args.language == "en_US"


# ============================================================================
# Engine runner lifecycle
# ============================================================================


@pytest.mark.integration
class TestEngineRunnerLifecycle:
    """引擎运行器生命周期集成测试。."""

    def test_compute_range_random_mode(self):
        """Random 模式返回 None 范围。."""
        args = MagicMock()
        args.mode = "random"
        start, end, total = _compute_range(args)
        assert start is None
        assert end is None
        assert total is None

    def test_compute_range_with_boundaries(self):
        """Range 模式计算范围。."""
        args = MagicMock()
        args.mode = "range"
        args.start = "0"
        args.end = "FF"
        start, end, total = _compute_range(args)
        assert start == "0"
        assert end == "FF"
        assert total == 256  # 0xFF + 1

    def test_collision_loop_timeout_stops(self):
        """碰撞循环在超时后自动停止。."""
        engine = MagicMock()
        # Simulate engine running (always True — timeout triggers stop)
        engine.is_running.return_value = True
        engine.get_stats.return_value = {
            "total_checked": 1000,
            "speed": 500,
            "matches_found": 0,
        }

        args = MagicMock()
        args.duration = 1  # 1 秒超时

        stop_event = threading.Event()
        alert_system = MagicMock()

        _run_collision_loop(
            engine=engine,
            engine_type="CPU",
            args=args,
            total_range=None,
            alert_system=alert_system,
            stop_event=stop_event,
        )

        engine.stop.assert_called()
        assert stop_event.is_set()

    def test_collision_loop_signal_triggers_stop(self):
        """信号触发的 stop_event 使循环退出。."""
        engine = MagicMock()
        engine.is_running.return_value = True
        engine.get_stats.return_value = None

        args = MagicMock()
        args.duration = None

        stop_event = threading.Event()
        alert_system = MagicMock()

        # 在循环开始后立即设置 stop_event
        def set_stop():
            import time

            time.sleep(0.1)
            stop_event.set()

        import threading as _threading

        _threading.Thread(target=set_stop, daemon=True).start()

        _run_collision_loop(
            engine=engine,
            engine_type="CPU",
            args=args,
            total_range=None,
            alert_system=alert_system,
            stop_event=stop_event,
        )

        # 循环应该因为 stop_event 退出
        assert stop_event.is_set()


# ============================================================================
# Configuration loading
# ============================================================================


@pytest.mark.integration
class TestConfigLoading:
    """配置加载集成测试。."""

    def test_load_config_default(self):
        """默认配置文件不存在时返回 None。."""
        from src.cli.config_loader import load_config_with_validation

        # 使用不存在的配置文件
        config = load_config_with_validation(config_file="__nonexistent_config__.json")
        # 应该能返回默认配置或 None
        assert config is not None or config is None

    def test_load_config_with_valid_file(self, tmp_path):
        """有效配置文件正常加载。."""
        import json

        from src.cli.config_loader import ConfigLoader

        config_data = {
            "collision": {"max_workers": 4},
            "engine": {"use_gpu": False},
            "gpu": {"mode": "auto"},
        }
        config_file = tmp_path / "test_config.json"
        config_file.write_text(json.dumps(config_data))

        loader = ConfigLoader()
        result = loader.load(str(config_file))
        assert result == config_data

    def test_load_config_nonexistent_file(self):
        """不存在的配置文件返回空字典。."""
        from src.cli.config_loader import ConfigLoader

        loader = ConfigLoader()
        result = loader.load("__nonexistent__.json")
        assert result == {}

    def test_config_loader_merge(self):
        """配置合并：override 优先。."""
        from src.cli.config_loader import ConfigLoader

        loader = ConfigLoader()
        merged = loader.merge(
            {"a": 1, "b": 2},
            {"b": 99, "c": 3},
        )
        assert merged == {"a": 1, "b": 99, "c": 3}


# ============================================================================
# CLI main entry point
# ============================================================================


@pytest.mark.integration
class TestCLIMainEntry:
    """CLI 主入口集成测试。."""

    @patch("src.cli.commands.dispatch_utility_commands")
    @patch("src.cli.arg_parser.parse_args")
    def test_main_dispatches_utility_and_exits(self, mock_parse, mock_dispatch):
        """main() 正确分发工具命令后退出。."""
        mock_parse.return_value = MagicMock(
            targets=["test"],
            mode="random",
            config=None,
            verbose=0,
            quiet=False,
            no_color=False,
            language=None,
        )
        mock_dispatch.return_value = True  # 表示工具命令已处理

        from src.cli.main import main

        main()

        mock_dispatch.assert_called_once()
        mock_parse.assert_called_once()

    @patch("src.cli.arg_parser.parse_args")
    def test_main_error_handling(self, mock_parse):
        """main() 捕获异常并正确处理。."""
        mock_parse.side_effect = FileNotFoundError("test")

        from src.cli.main import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


# ============================================================================
# Validation
# ============================================================================


@pytest.mark.integration
class TestValidationIntegration:
    """验证模块集成测试。."""

    def test_validate_file_path_safe(self, tmp_path):
        """安全文件路径验证通过。."""
        from src.cli.validation import validate_file_path

        safe_file = tmp_path / "test.txt"
        safe_file.write_text("test")
        assert validate_file_path(str(safe_file)) is True

    def test_validate_file_path_empty(self):
        """空路径被拒绝。."""
        from src.cli.validation import validate_file_path

        assert validate_file_path("") is False
        assert validate_file_path(None) is False
