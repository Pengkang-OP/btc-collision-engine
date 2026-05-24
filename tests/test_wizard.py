"""Tests for src/wizard package - 引导界面模块

Covers all wizard modules:
- __init__.py, selector_protocol.py, events.py, interfaces.py
- option_selector.py, mode_selector.py, config_builder.py
- message_queue.py, target_selector.py, gpu_selector.py, wizard_engine.py
"""

import json
import sys
from unittest.mock import MagicMock

import pytest

# ============================================================================
# __init__ tests
# ============================================================================


class TestWizardInit:
    """Test wizard/__init__.py exports."""

    def test_version(self):
        from src.wizard import __version__

        assert __version__ == "5.0.0"

    def test_all_exports(self):
        from src.wizard import __all__

        assert "WizardEngine" in __all__
        assert "WizardResult" in __all__
        assert "WizardConfig" in __all__
        assert "WizardMode" in __all__
        assert "WizardEvent" in __all__
        assert "SelectorProtocol" in __all__

    def test_wizard_engine_importable(self):
        from src.wizard import WizardEngine

        assert WizardEngine is not None

    def test_wizard_result_importable(self):
        from src.wizard import WizardResult

        assert WizardResult is not None


# ============================================================================
# selector_protocol.py tests
# ============================================================================


class TestSelectorProtocol:
    """Test SelectorProtocol ABC."""

    def test_cannot_instantiate_abstract(self):
        from src.wizard.selector_protocol import SelectorProtocol

        with pytest.raises(TypeError):
            SelectorProtocol()

    def test_concrete_subclass_works(self):
        from src.wizard.selector_protocol import SelectorProtocol

        class MySelector(SelectorProtocol):
            def select(self, compact=False):
                return "result"

        selector = MySelector()
        assert selector.select() == "result"
        assert selector.select(compact=True) == "result"

    def test_is_compact_supported_default(self):
        from src.wizard.selector_protocol import SelectorProtocol

        class MySelector(SelectorProtocol):
            def select(self, compact=False):
                return True

        selector = MySelector()
        assert selector.is_compact_supported() is True

    def test_is_compact_supported_overridden(self):
        from src.wizard.selector_protocol import SelectorProtocol

        class MySelector(SelectorProtocol):
            def select(self, compact=False):
                return True

            def is_compact_supported(self):
                return False

        selector = MySelector()
        assert selector.is_compact_supported() is False


# ============================================================================
# events.py tests
# ============================================================================


class TestWizardEventType:
    """Test WizardEventType enum."""

    def test_all_event_types(self):
        from src.wizard.events import WizardEventType

        types = list(WizardEventType)
        assert len(types) >= 10
        assert WizardEventType.WIZARD_START.value == "wizard_start"
        assert WizardEventType.WIZARD_COMPLETE.value == "wizard_complete"
        assert WizardEventType.WIZARD_CANCELLED.value == "wizard_cancelled"
        assert WizardEventType.WIZARD_ERROR.value == "wizard_error"


class TestWizardEvent:
    """Test WizardEvent dataclass."""

    def test_default_values(self):
        from src.wizard.events import WizardEvent, WizardEventType

        event = WizardEvent(event_type=WizardEventType.WIZARD_START)
        assert event.event_type == WizardEventType.WIZARD_START
        assert event.data == {}
        assert isinstance(event.timestamp, float)
        assert event.source == "wizard"

    def test_custom_values(self):
        from src.wizard.events import WizardEvent, WizardEventType

        event = WizardEvent(
            event_type=WizardEventType.TARGET_SELECTED,
            data={"targets": ["addr1"]},
            timestamp=12345.0,
            source="test",
        )
        assert event.data == {"targets": ["addr1"]}
        assert event.timestamp == 12345.0
        assert event.source == "test"

    def test_to_dict(self):
        from src.wizard.events import WizardEvent, WizardEventType

        event = WizardEvent(event_type=WizardEventType.MODE_SELECTED, data={"mode": "random"})
        d = event.to_dict()
        assert d["event_type"] == "mode_selected"
        assert d["data"] == {"mode": "random"}
        assert "timestamp" in d
        assert d["source"] == "wizard"


class TestEventDispatcher:
    """Test EventDispatcher."""

    def test_register_and_dispatch(self):
        from src.wizard.events import EventDispatcher, WizardEvent, WizardEventType

        dispatcher = EventDispatcher()
        callback = MagicMock()
        dispatcher.register(WizardEventType.WIZARD_START, callback)
        event = WizardEvent(event_type=WizardEventType.WIZARD_START)
        dispatcher.dispatch(event)
        callback.assert_called_once_with(event)

    def test_unregister(self):
        from src.wizard.events import EventDispatcher, WizardEvent, WizardEventType

        dispatcher = EventDispatcher()
        callback = MagicMock()
        dispatcher.register(WizardEventType.WIZARD_START, callback)
        dispatcher.unregister(WizardEventType.WIZARD_START, callback)
        event = WizardEvent(event_type=WizardEventType.WIZARD_START)
        dispatcher.dispatch(event)
        callback.assert_not_called()

    def test_dispatch_no_listeners(self):
        from src.wizard.events import EventDispatcher, WizardEvent, WizardEventType

        dispatcher = EventDispatcher()
        event = WizardEvent(event_type=WizardEventType.WIZARD_START)
        dispatcher.dispatch(event)  # should not raise

    def test_dispatch_callback_exception(self, caplog):
        from src.wizard.events import EventDispatcher, WizardEvent, WizardEventType

        dispatcher = EventDispatcher()

        def failing_callback(event):
            raise RuntimeError("test error")

        dispatcher.register(WizardEventType.WIZARD_ERROR, failing_callback)
        event = WizardEvent(event_type=WizardEventType.WIZARD_ERROR)
        dispatcher.dispatch(event)  # should not raise
        # Error should be logged
        assert "test error" in caplog.text

    def test_dispatch_multiple_callbacks(self):
        from src.wizard.events import EventDispatcher, WizardEvent, WizardEventType

        dispatcher = EventDispatcher()
        cb1 = MagicMock()
        cb2 = MagicMock()
        dispatcher.register(WizardEventType.WIZARD_START, cb1)
        dispatcher.register(WizardEventType.WIZARD_START, cb2)
        event = WizardEvent(event_type=WizardEventType.WIZARD_START)
        dispatcher.dispatch(event)
        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_clear(self):
        from src.wizard.events import EventDispatcher, WizardEvent, WizardEventType

        dispatcher = EventDispatcher()
        callback = MagicMock()
        dispatcher.register(WizardEventType.WIZARD_START, callback)
        dispatcher.clear()
        event = WizardEvent(event_type=WizardEventType.WIZARD_START)
        dispatcher.dispatch(event)
        callback.assert_not_called()


# ============================================================================
# interfaces.py tests
# ============================================================================


class TestWizardMode:
    """Test WizardMode enum."""

    def test_modes(self):
        from src.wizard.interfaces import WizardMode

        assert WizardMode.INTERACTIVE.value == "interactive"
        assert WizardMode.COMPACT.value == "compact"
        assert WizardMode.AUTO.value == "auto"


class TestWizardConfig:
    """Test WizardConfig dataclass."""

    def test_defaults(self):
        from src.wizard.interfaces import WizardConfig, WizardMode

        config = WizardConfig()
        assert config.mode == WizardMode.INTERACTIVE
        assert config.show_intro is True
        assert config.show_summary is True
        assert config.validate_input is True
        assert config.auto_continue is False
        assert config.countdown_seconds == 3

    def test_custom_values(self):
        from src.wizard.interfaces import WizardConfig, WizardMode

        config = WizardConfig(
            mode=WizardMode.COMPACT,
            show_intro=False,
            countdown_seconds=5,
        )
        assert config.mode == WizardMode.COMPACT
        assert config.show_intro is False
        assert config.countdown_seconds == 5


class TestWizardResult:
    """Test WizardResult dataclass."""

    def test_defaults(self):
        from src.wizard.interfaces import WizardResult

        result = WizardResult()
        assert result.success is False
        assert result.targets == []
        assert result.target_file is None
        assert result.mode == "random"
        assert result.checkpoint is True
        assert result.dedup is True
        assert result.duration == 0
        assert result.gpu_indices == []
        assert result.use_multi_gpu is False

    def test_to_dict(self):
        from src.wizard.interfaces import WizardResult

        result = WizardResult(success=True, targets=["addr1"], mode="range", duration=3600)
        d = result.to_dict()
        assert d["success"] is True
        assert d["targets"] == ["addr1"]
        assert d["mode"] == "range"
        assert d["duration"] == 3600
        assert d["error_message"] is None

    def test_build_command(self):
        from src.wizard.interfaces import WizardResult

        result = WizardResult(success=True, targets=["addr1"], mode="random")
        cmd = result.build_command()
        assert isinstance(cmd, list)
        assert "python" in cmd
        assert "random" in cmd

    def test_save_to_file(self, tmp_path):
        from src.wizard.interfaces import WizardResult

        result = WizardResult(success=True, targets=["addr1"])
        filepath = tmp_path / "result.json"
        assert result.save_to_file(str(filepath)) is True
        assert filepath.exists()
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert data["targets"] == ["addr1"]

    def test_save_to_file_io_error(self, tmp_path):
        from src.wizard.interfaces import WizardResult

        result = WizardResult(success=True)
        # Use a directory as path to cause IOError
        assert result.save_to_file(str(tmp_path)) is False

    def test_load_from_file(self, tmp_path):
        from src.wizard.interfaces import WizardResult

        filepath = tmp_path / "result.json"
        filepath.write_text(
            json.dumps({"success": True, "targets": ["addr1"], "mode": "random"}),
            encoding="utf-8",
        )
        result = WizardResult.load_from_file(str(filepath))
        assert result is not None
        assert result.success is True
        assert result.targets == ["addr1"]

    def test_load_from_file_nonexistent(self, tmp_path):
        from src.wizard.interfaces import WizardResult

        result = WizardResult.load_from_file(str(tmp_path / "nonexistent.json"))
        assert result is None

    def test_load_from_file_invalid_json(self, tmp_path):
        from src.wizard.interfaces import WizardResult

        filepath = tmp_path / "bad.json"
        filepath.write_text("not json", encoding="utf-8")
        result = WizardResult.load_from_file(str(filepath))
        assert result is None


# ============================================================================
# config_builder.py tests
# ============================================================================


class TestConfigBuilder:
    """Test ConfigBuilder - pure logic, no I/O dependencies."""

    def _make_result(self, **overrides):
        from src.wizard.interfaces import WizardResult

        defaults = {
            "success": True,
            "targets": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
            "mode": "random",
            "checkpoint": True,
            "dedup": True,
            "duration": 0,
        }
        defaults.update(overrides)
        return WizardResult(**defaults)

    def test_build_random_mode(self):
        from src.wizard.config_builder import ConfigBuilder

        result = self._make_result(mode="random", targets=["addr1"])
        cmd = ConfigBuilder().build(result)
        assert cmd[0] == "python"
        assert "key_collision_cli.py" in cmd[1]
        assert "-t" in cmd
        assert "addr1" in cmd
        assert "-m" in cmd
        assert "random" in cmd

    def test_build_range_mode(self):
        from src.wizard.config_builder import ConfigBuilder

        result = self._make_result(
            mode="range",
            targets=["addr1"],
            start_key="abc123",
            end_key="def456",
            checkpoint=False,
            dedup=False,
        )
        cmd = ConfigBuilder().build(result)
        assert "range" in cmd
        assert "--start" in cmd and "abc123" in cmd
        assert "--end" in cmd and "def456" in cmd
        assert "--checkpoint" not in cmd
        assert "--dedup" not in cmd

    def test_build_brute_force_mode(self):
        from src.wizard.config_builder import ConfigBuilder

        result = self._make_result(
            mode="brute_force",
            targets=["addr1"],
            start_key="abc123",
        )
        cmd = ConfigBuilder().build(result)
        assert "brute_force" in cmd
        assert "--start" in cmd and "abc123" in cmd

    def test_build_with_target_file(self):
        from src.wizard.config_builder import ConfigBuilder

        result = self._make_result(targets=[], target_file="my_targets.txt", mode="random")
        cmd = ConfigBuilder().build(result)
        assert "-f" in cmd
        assert "my_targets.txt" in cmd

    def test_build_with_duration(self):
        from src.wizard.config_builder import ConfigBuilder

        result = self._make_result(mode="random", duration=7200)
        cmd = ConfigBuilder().build(result)
        assert "--duration" in cmd
        assert "7200" in cmd

    def test_build_with_gpu_indices(self):
        from src.wizard.config_builder import ConfigBuilder

        result = self._make_result(mode="random", gpu_indices=[0, 1], use_multi_gpu=True)
        cmd = ConfigBuilder().build(result)
        assert "--multi-gpu" in cmd
        assert "--gpu-indices" in cmd
        assert "0" in cmd
        assert "1" in cmd

    def test_build_no_targets_raises(self):
        from src.wizard.config_builder import ConfigBuilder
        from src.wizard.interfaces import WizardResult

        result = WizardResult(targets=[], target_file=None, mode="random")
        with pytest.raises(ValueError, match="No targets specified"):
            ConfigBuilder().build(result)

    def test_build_invalid_mode_raises(self):
        from src.wizard.config_builder import ConfigBuilder

        result = self._make_result(mode="invalid_mode")
        with pytest.raises(ValueError, match="Invalid mode"):
            ConfigBuilder().build(result)

    def test_build_range_without_start_key_raises(self):
        from src.wizard.config_builder import ConfigBuilder

        result = self._make_result(mode="range", start_key=None, end_key="some")
        with pytest.raises(ValueError, match="requires a start_key"):
            ConfigBuilder().build(result)

    def test_build_range_without_end_key_raises(self):
        from src.wizard.config_builder import ConfigBuilder

        result = self._make_result(mode="range", start_key="abc", end_key=None)
        with pytest.raises(ValueError, match="requires an end_key"):
            ConfigBuilder().build(result)

    def test_build_brute_force_without_start_key_raises(self):
        from src.wizard.config_builder import ConfigBuilder

        result = self._make_result(mode="brute_force", start_key=None)
        with pytest.raises(ValueError, match="requires a start_key"):
            ConfigBuilder().build(result)

    def test_build_summary(self):
        from src.wizard.config_builder import ConfigBuilder

        result = self._make_result(mode="random")
        summary = ConfigBuilder().build_summary(result)
        assert "生成的命令" in summary
        assert "python" in summary

    def test_save_command(self, tmp_path):
        from src.wizard.config_builder import ConfigBuilder

        result = self._make_result(mode="random")
        filepath = tmp_path / "start.sh"
        assert ConfigBuilder().save_command(result, str(filepath)) is True
        assert filepath.exists()
        content = filepath.read_text(encoding="utf-8")
        assert "#!/bin/bash" in content
        assert "key_collision_cli.py" in content

    def test_save_command_io_error(self, tmp_path):
        from src.wizard.config_builder import ConfigBuilder

        result = self._make_result(mode="random")
        assert ConfigBuilder().save_command(result, str(tmp_path)) is False


# ============================================================================
# option_selector.py tests
# ============================================================================


class TestOptionSelector:
    """Test OptionSelector with mocked input."""

    def test_is_compact_supported(self):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        assert selector.is_compact_supported() is True

    def test_select_compact(self):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        result = selector.select(compact=True)
        assert result == (True, True, 0)

    def test_select_interactive_defaults(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        # User presses Enter for all (defaults)
        inputs = iter(["", "", ""])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
        result = selector.select(compact=False)
        assert result == (True, True, 0)

    def test_ask_checkpoint_yes(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        monkeypatch.setattr("builtins.input", lambda p: "y")
        assert selector._ask_checkpoint() is True

    def test_ask_checkpoint_no(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        monkeypatch.setattr("builtins.input", lambda p: "n")
        assert selector._ask_checkpoint() is False

    def test_ask_checkpoint_invalid_then_valid(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        inputs = iter(["invalid", "y"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        assert selector._ask_checkpoint() is True

    def test_ask_dedup_yes(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        monkeypatch.setattr("builtins.input", lambda p: "yes")
        assert selector._ask_dedup() is True

    def test_ask_dedup_no(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        monkeypatch.setattr("builtins.input", lambda p: "no")
        assert selector._ask_dedup() is False

    def test_ask_duration_default(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        monkeypatch.setattr("builtins.input", lambda p: "")
        assert selector._ask_duration() == 0

    def test_ask_duration_option1(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        monkeypatch.setattr("builtins.input", lambda p: "1")
        assert selector._ask_duration() == 0

    def test_ask_duration_option2_hours(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        inputs = iter(["2", "5"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        assert selector._ask_duration() == 18000  # 5 * 3600

    def test_ask_duration_option3_days(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        inputs = iter(["3", "2"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        assert selector._ask_duration() == 172800  # 2 * 86400

    def test_ask_duration_invalid_choice(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        inputs = iter(["invalid", "1"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        assert selector._ask_duration() == 0

    def test_ask_hours_empty(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        monkeypatch.setattr("builtins.input", lambda p: "")
        assert selector._ask_hours() == 0

    def test_ask_hours_zero(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        inputs = iter(["0", "1"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        assert selector._ask_hours() == 3600

    def test_ask_hours_invalid(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        inputs = iter(["abc", "3"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        assert selector._ask_hours() == 10800

    def test_ask_dedup_invalid_then_valid(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        inputs = iter(["invalid", "yes"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        assert selector._ask_dedup() is True

    def test_ask_days_empty(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        monkeypatch.setattr("builtins.input", lambda p: "")
        assert selector._ask_days() == 0

    def test_ask_days_zero(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        inputs = iter(["0", "2"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        assert selector._ask_days() == 172800

    def test_ask_days_invalid(self, monkeypatch):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        inputs = iter(["xyz", "1"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        assert selector._ask_days() == 86400


# ============================================================================
# mode_selector.py tests
# ============================================================================


class TestModeSelector:
    """Test ModeSelector with mocked input."""

    def test_select_compact(self):
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        result = selector.select(compact=True)
        assert result == ("random", None, None)

    def test_select_random_default(self, monkeypatch):
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        monkeypatch.setattr("builtins.input", lambda p: "")
        result = selector.select(compact=False)
        assert result == ("random", None, None)

    def test_select_random_explicit(self, monkeypatch):
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        monkeypatch.setattr("builtins.input", lambda p: "1")
        result = selector.select(compact=False)
        assert result == ("random", None, None)

    def test_select_range(self, monkeypatch):
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        inputs = iter(["2", "abc123", "def456"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        result = selector.select(compact=False)
        assert result == ("range", "abc123", "def456")

    def test_select_brute_force(self, monkeypatch):
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        inputs = iter(["3", "abc123"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        result = selector.select(compact=False)
        assert result == ("brute_force", "abc123", None)

    def test_select_invalid_mode(self, monkeypatch):
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        inputs = iter(["invalid", "1"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        result = selector.select(compact=False)
        assert result == ("random", None, None)

    def test_select_range_empty_keys(self, monkeypatch):
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        # First pass: empty keys, then valid ones
        inputs = iter(["2", "", "", "abc", "def"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        result = selector.select(compact=False)
        assert result == ("range", "abc", "def")

    def test_select_range_invalid_hex(self, monkeypatch):
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        inputs = iter(["2", "zzz", "yyy", "abc", "def"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        result = selector.select(compact=False)
        assert result == ("range", "abc", "def")

    def test_select_brute_force_empty_key(self, monkeypatch):
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        inputs = iter(["3", "", "abc"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        result = selector.select(compact=False)
        assert result == ("brute_force", "abc", None)

    def test_select_brute_force_invalid_hex(self, monkeypatch):
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        inputs = iter(["3", "zzz", "abc"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        result = selector.select(compact=False)
        assert result == ("brute_force", "abc", None)

    def test_select_range_empty_end_key(self, monkeypatch):
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        # First: empty end_key, then valid range (use valid hex)
        inputs = iter(["2", "abc", "", "def", "456"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        result = selector.select(compact=False)
        assert result == ("range", "def", "456")

    def test_select_fallback_line(self, monkeypatch):
        """Cover the fallback return on line 76 (unreachable in normal flow)."""
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        # Patch MODES to simulate a mode that bypasses all branches
        original_modes = selector.MODES
        selector.MODES = {"4": {"name": "unknown_mode"}}
        monkeypatch.setattr("builtins.input", lambda p: "4")
        result = selector.select(compact=False)
        selector.MODES = original_modes
        assert result == ("unknown_mode", None, None)

    def test_modes_dict(self):
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        assert "1" in selector.MODES
        assert selector.MODES["1"]["name"] == "random"
        assert "2" in selector.MODES
        assert selector.MODES["2"]["name"] == "range"
        assert "3" in selector.MODES
        assert selector.MODES["3"]["name"] == "brute_force"


# ============================================================================
# message_queue.py tests
# ============================================================================


class TestWizardMessageQueue:
    """Test WizardMessageQueue."""

    def test_init_defaults(self):
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        assert mq.is_empty()
        assert not mq.is_full()
        assert mq.size() == 0

    def test_send_and_receive(self):
        from src.wizard.events import WizardEventType
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        assert mq.send(WizardEventType.WIZARD_START, {"key": "val"})
        event = mq.receive()
        assert event is not None
        assert event.event_type == WizardEventType.WIZARD_START
        assert event.data == {"key": "val"}

    def test_send_disabled_queue(self):
        from src.wizard.events import WizardEventType
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        mq.disable()
        assert mq.send(WizardEventType.WIZARD_START, {}) is False

    def test_send_queue_full(self):
        from src.wizard.events import WizardEventType
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue(maxsize=1)
        assert mq.send(WizardEventType.WIZARD_START, {})
        assert mq.send(WizardEventType.WIZARD_START, {}) is False

    def test_receive_timeout(self):
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        event = mq.receive(timeout=0.01)
        assert event is None

    def test_receive_all(self):
        from src.wizard.events import WizardEventType
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        mq.send(WizardEventType.WIZARD_START, {})
        mq.send(WizardEventType.TARGET_SELECTED, {"targets": ["a"]})
        events = mq.receive_all()
        assert len(events) == 2

    def test_subscribe_and_notify(self):
        from src.wizard.events import WizardEventType
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        callback = MagicMock()
        mq.subscribe(callback)
        mq.send(WizardEventType.WIZARD_START, {})
        callback.assert_called_once()

    def test_unsubscribe(self):
        from src.wizard.events import WizardEventType
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        callback = MagicMock()
        mq.subscribe(callback)
        mq.unsubscribe(callback)
        mq.send(WizardEventType.WIZARD_START, {})
        callback.assert_not_called()

    def test_subscriber_exception_handled(self, caplog):
        from src.wizard.events import WizardEventType
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()

        def failing_cb(event):
            raise RuntimeError("sub error")

        mq.subscribe(failing_cb)
        mq.send(WizardEventType.WIZARD_START, {})
        assert "sub error" in caplog.text

    def test_enable_disable(self):
        from src.wizard.events import WizardEventType
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        mq.disable()
        assert mq.send(WizardEventType.WIZARD_START, {}) is False
        mq.enable()
        assert mq.send(WizardEventType.WIZARD_START, {}) is True

    def test_clear(self):
        from src.wizard.events import WizardEventType
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        mq.send(WizardEventType.WIZARD_START, {})
        mq.send(WizardEventType.WIZARD_START, {})
        mq.clear()
        assert mq.is_empty()

    def test_send_wizard_start(self):
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        assert mq.send_wizard_start({"mode": "interactive"})
        assert mq.size() == 1

    def test_send_target_selected(self):
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        assert mq.send_target_selected(["addr1"], "file.txt")
        assert mq.size() == 1

    def test_send_mode_selected(self):
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        assert mq.send_mode_selected("random", "start", "end")
        assert mq.size() == 1

    def test_send_options_selected(self):
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        assert mq.send_options_selected(True, False, 3600)
        assert mq.size() == 1

    def test_send_gpu_selected(self):
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        assert mq.send_gpu_selected([0, 1], True)
        assert mq.size() == 1

    def test_send_wizard_complete(self):
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        assert mq.send_wizard_complete({"success": True})
        assert mq.size() == 1

    def test_send_wizard_cancelled(self):
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        assert mq.send_wizard_cancelled()
        assert mq.size() == 1

    def test_send_wizard_error(self):
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        assert mq.send_wizard_error("test error")
        assert mq.size() == 1

    def test_clear_race_condition(self):
        """Test clear() handles queue.Empty during drain."""
        from src.wizard.events import WizardEventType
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        mq.send(WizardEventType.WIZARD_START, {})
        # Simulate race: empty() returns False, but get_nowait raises Empty
        original_get = mq._queue.get_nowait
        call_count = [0]

        def mock_empty():
            # First call: not empty (enter loop)
            # After get raises Empty, called again → still says not empty
            return call_count[0] < 2

        def mock_get_nowait():
            call_count[0] += 1
            if call_count[0] == 1:
                return original_get()
            raise __import__("queue").Empty()

        mq._queue.empty = mock_empty
        mq._queue.get_nowait = mock_get_nowait
        mq.clear()
        assert mq.is_empty()


class TestMessageQueueGlobal:
    """Test global message queue functions."""

    def test_get_message_queue_creates_singleton(self, monkeypatch):
        from src.wizard.message_queue import get_message_queue, reset_message_queue

        # Reset first
        reset_message_queue(None)
        q1 = get_message_queue()
        q2 = get_message_queue()
        assert q1 is q2

    def test_set_message_queue(self):
        from src.wizard.message_queue import (
            WizardMessageQueue,
            get_message_queue,
            reset_message_queue,
            set_message_queue,
        )

        reset_message_queue(None)
        custom_q = WizardMessageQueue(maxsize=100)
        set_message_queue(custom_q)
        assert get_message_queue() is custom_q
        reset_message_queue(None)

    def test_set_message_queue_clears_old(self):
        from src.wizard.message_queue import (
            WizardMessageQueue,
            reset_message_queue,
            set_message_queue,
        )

        old_q = WizardMessageQueue()
        old_q.send_wizard_start({})
        reset_message_queue(None)
        set_message_queue(old_q)  # Now old_q is the global
        new_q = WizardMessageQueue()
        set_message_queue(new_q)
        assert old_q.is_empty()  # old was cleared
        reset_message_queue(None)

    def test_reset_message_queue(self):
        from src.wizard.message_queue import (
            WizardMessageQueue,
            get_message_queue,
            reset_message_queue,
        )

        reset_message_queue(None)
        q = WizardMessageQueue()
        q.send_wizard_start({})
        reset_message_queue(q)
        reset_message_queue(None)
        # get_message_queue always creates a new queue when None
        new_q = get_message_queue()
        assert new_q is not None
        assert isinstance(new_q, WizardMessageQueue)
        reset_message_queue(None)

    def test_reset_message_queue_with_new(self):
        from src.wizard.message_queue import (
            WizardMessageQueue,
            get_message_queue,
            reset_message_queue,
        )

        reset_message_queue(None)
        new_q = WizardMessageQueue()
        reset_message_queue(new_q)
        assert get_message_queue() is new_q
        reset_message_queue(None)


# ============================================================================
# target_selector.py tests
# ============================================================================


class TestTargetSelector:
    """Test TargetSelector with mocked TargetResolver."""

    @pytest.fixture
    def mock_resolver(self, monkeypatch):
        """Mock TargetResolver."""
        mock = MagicMock()
        mock.resolve_multiple.return_value = {"addr1": None}
        mock.load_from_file.return_value = ["addr1", "addr2"]

        # Mock the import in target_selector
        import src.wizard.target_selector as ts

        monkeypatch.setattr(ts, "TargetResolver", MagicMock(return_value=mock))
        return mock

    def test_select_compact_with_targets_file(self, mock_resolver, tmp_path, monkeypatch):
        from src.wizard.target_selector import TargetSelector

        monkeypatch.chdir(tmp_path)
        # Create targets.txt
        (tmp_path / "targets.txt").write_text("addr1\naddr2")
        selector = TargetSelector()
        result = selector.select(compact=True)
        assert len(result[0]) == 2
        assert result[1] == "targets.txt"

    def test_select_compact_no_file(self, mock_resolver, tmp_path, monkeypatch):
        from src.wizard.target_selector import TargetSelector

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("builtins.input", lambda *a, **kw: "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        selector = TargetSelector()
        result = selector.select(compact=True)
        assert len(result[0]) == 1
        assert result[1] is None

    def test_select_compact_empty_input(self, mock_resolver, tmp_path, monkeypatch):
        from src.wizard.target_selector import TargetSelector

        monkeypatch.chdir(tmp_path)
        inputs = iter(["", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])
        monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))
        selector = TargetSelector()
        result = selector.select(compact=True)
        assert len(result[0]) == 1

    def test_select_compact_invalid_address(self, mock_resolver, tmp_path, monkeypatch):
        from src.wizard.target_selector import TargetSelector

        monkeypatch.chdir(tmp_path)
        call_count = [0]

        def resolve_side_effect(addresses):
            call_count[0] += 1
            if call_count[0] == 1:
                return {}
            return {"addr": None}

        mock_resolver.resolve_multiple.side_effect = resolve_side_effect
        inputs = iter(["bad_addr", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])
        monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))
        selector = TargetSelector()
        result = selector.select(compact=True)
        assert len(result[0]) == 1

    def test_select_interactive_default_single(self, mock_resolver, monkeypatch):
        """Interactive mode: empty input defaults to single address."""
        from src.wizard.target_selector import TargetSelector

        monkeypatch.setattr("builtins.input", lambda *a, **kw: "")
        # Will default to "1", enter _select_single, read address
        # _select_single uses input() without prompt
        call_count = [0]

        def input_side(*args):
            call_count[0] += 1
            if call_count[0] == 2:  # address input
                return "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
            return ""

        monkeypatch.setattr("builtins.input", input_side)
        selector = TargetSelector()
        result = selector.select(compact=False)
        assert len(result[0]) == 1
        assert result[1] is None

    def test_select_interactive_single_valid(self, mock_resolver, monkeypatch):
        """Interactive mode: choose single address (option 1)."""
        from src.wizard.target_selector import TargetSelector

        call_count = [0]

        def input_side(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return "1"
            return "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

        monkeypatch.setattr("builtins.input", input_side)
        selector = TargetSelector()
        result = selector.select(compact=False)
        assert len(result[0]) == 1

    def test_select_interactive_single_empty_address(self, mock_resolver, monkeypatch):
        """Interactive mode: empty address in _select_single triggers retry."""
        from src.wizard.target_selector import TargetSelector

        call_count = [0]

        def input_side(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return "1"
            if call_count[0] == 2:
                return ""  # empty -> retry
            return "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

        monkeypatch.setattr("builtins.input", input_side)
        selector = TargetSelector()
        result = selector.select(compact=False)
        assert len(result[0]) == 1

    def test_select_interactive_single_invalid(self, mock_resolver, monkeypatch):
        """Interactive mode: invalid address triggers retry."""
        from src.wizard.target_selector import TargetSelector

        call_count = [0]

        def input_side(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return "1"
            if call_count[0] == 2:
                return "bad"
            return "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

        resolve_call = [0]

        def resolve_multi(addresses):
            resolve_call[0] += 1
            if resolve_call[0] == 1:
                return {}
            return {"addr": None}

        mock_resolver.resolve_multiple.side_effect = resolve_multi
        monkeypatch.setattr("builtins.input", input_side)
        selector = TargetSelector()
        result = selector.select(compact=False)
        assert len(result[0]) == 1

    def test_select_interactive_from_file(self, mock_resolver, tmp_path, monkeypatch):
        """Interactive mode: choose from file (option 2)."""
        from src.wizard.target_selector import TargetSelector

        monkeypatch.chdir(tmp_path)
        (tmp_path / "my_targets.txt").write_text("addr1\naddr2")
        call_count = [0]

        def input_side(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return "2"
            return "my_targets.txt"

        monkeypatch.setattr("builtins.input", input_side)
        selector = TargetSelector()
        result = selector.select(compact=False)
        assert len(result[0]) == 2
        assert result[1] == "my_targets.txt"

    def test_select_interactive_from_file_default(self, mock_resolver, tmp_path, monkeypatch):
        """Interactive mode: from file with default path."""
        from src.wizard.target_selector import TargetSelector

        monkeypatch.chdir(tmp_path)
        (tmp_path / "targets.txt").write_text("addr1")
        mock_resolver.load_from_file.return_value = ["addr1"]
        call_count = [0]

        def input_side(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return "2"
            return ""  # use default

        monkeypatch.setattr("builtins.input", input_side)
        selector = TargetSelector()
        result = selector.select(compact=False)
        assert len(result[0]) == 1

    def test_select_interactive_from_file_not_exists(self, mock_resolver, tmp_path, monkeypatch):
        """Interactive mode: file not exists triggers retry."""
        from src.wizard.target_selector import TargetSelector

        monkeypatch.chdir(tmp_path)
        (tmp_path / "targets.txt").write_text("addr1")
        mock_resolver.load_from_file.return_value = ["addr1"]
        call_count = [0]

        def input_side(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return "2"
            if call_count[0] == 2:
                return "no_such_file.txt"
            return ""  # use default targets.txt

        monkeypatch.setattr("builtins.input", input_side)
        selector = TargetSelector()
        result = selector.select(compact=False)
        assert len(result[0]) == 1

    def test_select_interactive_from_file_no_addresses(self, mock_resolver, tmp_path, monkeypatch):
        """Interactive mode: file with no valid addresses triggers retry."""
        from src.wizard.target_selector import TargetSelector

        monkeypatch.chdir(tmp_path)
        (tmp_path / "empty_file.txt").write_text("")
        (tmp_path / "targets.txt").write_text("addr1")

        load_call = [0]

        def load_side(file_path):
            load_call[0] += 1
            if load_call[0] == 1:
                return []
            return ["addr1"]

        mock_resolver.load_from_file.side_effect = load_side
        call_count = [0]

        def input_side(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return "2"
            if call_count[0] == 2:
                return "empty_file.txt"
            return ""

        monkeypatch.setattr("builtins.input", input_side)
        selector = TargetSelector()
        result = selector.select(compact=False)
        assert len(result[0]) == 1

    def test_select_interactive_invalid_option(self, mock_resolver, monkeypatch):
        """Interactive mode: invalid choice triggers retry."""
        from src.wizard.target_selector import TargetSelector

        call_count = [0]

        def input_side(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return "3"  # invalid
            if call_count[0] == 2:
                return "1"
            return "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

        monkeypatch.setattr("builtins.input", input_side)
        selector = TargetSelector()
        result = selector.select(compact=False)
        assert len(result[0]) == 1


# ============================================================================
# gpu_selector.py tests
# ============================================================================


class TestGPUSelector:
    """Test GPUSelector with mocked GPU detection."""

    @pytest.fixture
    def mock_detector(self, monkeypatch):
        """Mock GPUDeviceDetector."""
        mock = MagicMock()
        mock.detect_devices.return_value = [
            {"name": "NVIDIA RTX 3080"},
            {"name": "NVIDIA RTX 4090"},
        ]

        # Create a mock module for GPU device
        mock_gpu_device = MagicMock()
        mock_gpu_device.GPUDeviceDetector = mock
        original = sys.modules.get("src.gpu.device")
        sys.modules["src.gpu.device"] = mock_gpu_device

        yield mock

        # Restore original module
        if original is not None:
            sys.modules["src.gpu.device"] = original
        else:
            sys.modules.pop("src.gpu.device", None)

    def test_select_compact_no_gpus(self, monkeypatch):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        # Mock _detect_gpus to return empty
        monkeypatch.setattr(selector, "_detect_gpus", list)
        result = selector.select(compact=True)
        assert result == ([], False)

    def test_select_compact_single_gpu(self, monkeypatch):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        monkeypatch.setattr(selector, "_detect_gpus", lambda: [{"name": "GPU1"}])
        result = selector.select(compact=True)
        assert result == ([0], False)

    def test_select_compact_multi_gpu(self, monkeypatch):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        monkeypatch.setattr(selector, "_detect_gpus", lambda: [{"name": "GPU1"}, {"name": "GPU2"}])
        result = selector.select(compact=True)
        assert result == ([0, 1], True)

    def test_detect_gpus_exception(self, monkeypatch):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        # Mock the GPU device module to raise on detect_devices
        mock_gpu_device = MagicMock()
        mock_gpu_device.GPUDeviceDetector = MagicMock()
        mock_gpu_device.GPUDeviceDetector.detect_devices.side_effect = ImportError("no gpu")
        monkeypatch.setitem(sys.modules, "src.gpu.device", mock_gpu_device)
        result = selector._detect_gpus()
        assert result == []

    def test_select_cpu_mode(self, monkeypatch):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        monkeypatch.setattr(selector, "_detect_gpus", lambda: [{"name": "GPU1"}])
        monkeypatch.setattr("builtins.input", lambda p: "1")
        result = selector.select(compact=False)
        assert result == ([], False)

    def test_select_single_gpu_valid(self, monkeypatch):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        gpu_info = [{"name": "GPU1"}, {"name": "GPU2"}]
        monkeypatch.setattr(selector, "_detect_gpus", lambda: gpu_info)
        inputs = iter(["2", "1"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        result = selector.select(compact=False)
        assert result == ([0], False)

    def test_select_single_gpu_invalid_then_valid(self, monkeypatch):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        gpu_info = [{"name": "GPU1"}, {"name": "GPU2"}]
        monkeypatch.setattr(selector, "_detect_gpus", lambda: gpu_info)
        # First empty, then invalid number, then valid
        inputs = iter(["2", "", "abc", "5", "1"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        result = selector.select(compact=False)
        assert result == ([0], False)

    def test_select_multi_gpu_all(self, monkeypatch):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        gpu_info = [{"name": "GPU1"}, {"name": "GPU2"}]
        monkeypatch.setattr(selector, "_detect_gpus", lambda: gpu_info)
        inputs = iter(["3", ""])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        result = selector.select(compact=False)
        assert result == ([0, 1], True)

    def test_select_multi_gpu_specific(self, monkeypatch):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        gpu_info = [{"name": "GPU1"}, {"name": "GPU2"}, {"name": "GPU3"}]
        monkeypatch.setattr(selector, "_detect_gpus", lambda: gpu_info)
        inputs = iter(["3", "1 3"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        result = selector.select(compact=False)
        assert result == ([0, 2], True)

    def test_select_multi_gpu_invalid_then_valid(self, monkeypatch):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        gpu_info = [{"name": "GPU1"}, {"name": "GPU2"}]
        monkeypatch.setattr(selector, "_detect_gpus", lambda: gpu_info)
        # First invalid indices, then valid
        call_count = [0]

        def input_side(prompt):
            call_count[0] += 1
            if call_count[0] == 1:
                return "3"  # multi-gpu
            if call_count[0] == 2:
                return "5"  # invalid index
            if call_count[0] == 3:
                return "1"  # valid
            return ""

        monkeypatch.setattr("builtins.input", input_side)
        result = selector.select(compact=False)
        assert result == ([0], True)  # retry selects single GPU

    def test_detect_gpus_success(self, mock_detector):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        gpus = selector._detect_gpus()
        assert len(gpus) == 2
        assert gpus[0]["name"] == "NVIDIA RTX 3080"
        assert gpus[1]["name"] == "NVIDIA RTX 4090"

    def test_select_interactive_no_gpus(self, monkeypatch):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        monkeypatch.setattr(selector, "_detect_gpus", list)
        result = selector.select(compact=False)
        assert result == ([], False)

    def test_select_interactive_empty_defaults_to_single(self, monkeypatch):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        monkeypatch.setattr(selector, "_detect_gpus", lambda: [{"name": "GPU1"}])
        # Empty input defaults to "2" (single GPU), then pick GPU 1
        inputs = iter(["", "1"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        result = selector.select(compact=False)
        assert result == ([0], False)

    def test_select_interactive_invalid_option(self, monkeypatch):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        monkeypatch.setattr(selector, "_detect_gpus", lambda: [{"name": "GPU1"}])
        # Invalid "4", then valid "1"
        inputs = iter(["4", "1"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        result = selector.select(compact=False)
        assert result == ([], False)

    def test_select_multi_gpu_invalid_format(self, monkeypatch):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        gpu_info = [{"name": "GPU1"}, {"name": "GPU2"}]
        monkeypatch.setattr(selector, "_detect_gpus", lambda: gpu_info)
        # Select multi-gpu, then invalid format (abc), then valid
        inputs = iter(["3", "abc", "1"])
        monkeypatch.setattr("builtins.input", lambda p: next(inputs))
        result = selector.select(compact=False)
        # After invalid multi-gpu input, retries with single GPU
        assert result == ([0], True)


# ============================================================================
# wizard_engine.py tests
# ============================================================================


class TestWizardEngine:
    """Test WizardEngine orchestration."""

    def test_init_defaults(self):
        from src.wizard.interfaces import WizardMode
        from src.wizard.wizard_engine import WizardEngine

        engine = WizardEngine()
        assert engine.config.mode == WizardMode.INTERACTIVE
        assert engine.result.success is False
        assert engine._running is False
        assert "target" in engine._step_handlers
        assert "mode" in engine._step_handlers
        assert "options" in engine._step_handlers
        assert "gpu" in engine._step_handlers
        assert "build" in engine._step_handlers

    def test_init_custom_config(self):
        from src.wizard.interfaces import WizardConfig, WizardMode
        from src.wizard.wizard_engine import WizardEngine

        config = WizardConfig(mode=WizardMode.COMPACT, show_intro=False)
        engine = WizardEngine(config=config)
        assert engine.config.mode == WizardMode.COMPACT
        assert engine.config.show_intro is False

    def test_stop(self):
        from src.wizard.wizard_engine import WizardEngine

        engine = WizardEngine()
        assert engine.is_running() is False
        engine._running = True
        assert engine.is_running() is True
        engine.stop()
        assert engine.is_running() is False

    def test_register_step_handler(self):
        from src.wizard.wizard_engine import WizardEngine

        engine = WizardEngine()
        handler = MagicMock()
        engine.register_step_handler("custom_step", handler)
        assert engine._step_handlers["custom_step"] is handler

    def test_unregister_step_handler(self):
        from src.wizard.wizard_engine import WizardEngine

        engine = WizardEngine()
        engine.unregister_step_handler("target")
        assert "target" not in engine._step_handlers

    def test_show_intro(self, capsys):
        from src.wizard.wizard_engine import WizardEngine

        engine = WizardEngine()
        engine._show_intro()
        captured = capsys.readouterr()
        assert "BTC碰撞引擎" in captured.out
        assert "交互式向导" in captured.out

    def test_run_compact_mode(self, monkeypatch, tmp_path):
        """Test wizard run in compact mode - all defaults."""
        import src.wizard.wizard_engine as we
        from src.wizard.interfaces import WizardConfig, WizardMode

        # Mock subprocess to avoid actual command execution
        monkeypatch.setattr("subprocess.run", MagicMock())

        # Mock TargetSelector directly on wizard_engine module
        mock_target_selector = MagicMock()
        mock_target_selector.return_value.select.return_value = (["addr1"], None)
        monkeypatch.setattr(we, "TargetSelector", mock_target_selector)

        # Mock ModeSelector
        mock_mode_selector = MagicMock()
        mock_mode_selector.return_value.select.return_value = ("random", None, None)
        monkeypatch.setattr(we, "ModeSelector", mock_mode_selector)

        # Mock OptionSelector
        mock_opt_selector = MagicMock()
        mock_opt_selector.return_value.select.return_value = (True, True, 0)
        monkeypatch.setattr(we, "OptionSelector", mock_opt_selector)

        # Mock GPUSelector
        mock_gpu_selector = MagicMock()
        mock_gpu_selector.return_value.select.return_value = ([], False)
        monkeypatch.setattr(we, "GPUSelector", mock_gpu_selector)

        # Mock message queue
        from src.wizard.message_queue import WizardMessageQueue

        mock_mq = MagicMock(spec=WizardMessageQueue)

        config = WizardConfig(
            mode=WizardMode.COMPACT,
            show_intro=False,
            show_summary=False,
            auto_continue=True,
        )
        engine = we.WizardEngine(config=config, message_queue=mock_mq)
        result = engine.run()

        assert result.success is True
        assert result.targets == ["addr1"]
        assert result.mode == "random"

    def test_run_cancelled_midway(self, monkeypatch):
        """Test wizard cancelled during run."""
        import src.wizard.wizard_engine as we
        from src.wizard.interfaces import WizardConfig, WizardMode

        mock_target_selector = MagicMock()

        # Simulate cancellation by stopping during step execution
        call_count = [0]

        def select_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                return ([], False)
            import time

            time.sleep(0.05)  # Give stop thread time to cancel
            return (["addr1"], None)

        mock_target_selector.return_value.select.side_effect = select_side_effect
        monkeypatch.setattr(we, "TargetSelector", mock_target_selector)

        mock_mode_selector = MagicMock()
        mock_mode_selector.return_value.select.return_value = ("random", None, None)
        monkeypatch.setattr(we, "ModeSelector", mock_mode_selector)

        mock_opt_selector = MagicMock()
        mock_opt_selector.return_value.select.return_value = (True, True, 0)
        monkeypatch.setattr(we, "OptionSelector", mock_opt_selector)

        mock_gpu_selector = MagicMock()
        mock_gpu_selector.return_value.select.return_value = ([], False)
        monkeypatch.setattr(we, "GPUSelector", mock_gpu_selector)

        from src.wizard.message_queue import WizardMessageQueue

        mock_mq = MagicMock(spec=WizardMessageQueue)

        config = WizardConfig(
            mode=WizardMode.COMPACT,
            show_intro=False,
            show_summary=False,
            auto_continue=True,
        )

        engine = we.WizardEngine(config=config, message_queue=mock_mq)

        # Mock subprocess to avoid actual command execution
        monkeypatch.setattr("subprocess.run", MagicMock())

        # Stop the engine during run
        import threading

        def stop_soon():
            import time

            time.sleep(0.01)
            engine.stop()

        t = threading.Thread(target=stop_soon)
        t.start()
        result = engine.run()
        t.join()

        # Should be cancelled
        assert result.success is False
        assert "取消" in (result.error_message or "")

    def test_run_exception_handled(self, monkeypatch):
        """Test wizard handles exceptions during run."""
        import src.wizard.wizard_engine as we
        from src.wizard.interfaces import WizardConfig, WizardMode

        mock_target_selector = MagicMock()
        mock_target_selector.return_value.select.side_effect = RuntimeError("test error")
        monkeypatch.setattr(we, "TargetSelector", mock_target_selector)

        from src.wizard.message_queue import WizardMessageQueue

        mock_mq = MagicMock(spec=WizardMessageQueue)

        config = WizardConfig(mode=WizardMode.COMPACT, show_intro=False)
        engine = we.WizardEngine(config=config, message_queue=mock_mq)
        result = engine.run()

        assert result.success is False
        assert "RuntimeError" in (result.error_message or "")

    def test_run_keyboard_interrupt(self, monkeypatch):
        """Test wizard handles KeyboardInterrupt."""
        import src.wizard.wizard_engine as we
        from src.wizard.interfaces import WizardConfig, WizardMode

        mock_target_selector = MagicMock()
        mock_target_selector.return_value.select.side_effect = KeyboardInterrupt()
        monkeypatch.setattr(we, "TargetSelector", mock_target_selector)

        from src.wizard.message_queue import WizardMessageQueue

        mock_mq = MagicMock(spec=WizardMessageQueue)

        config = WizardConfig(mode=WizardMode.COMPACT, show_intro=False)
        engine = we.WizardEngine(config=config, message_queue=mock_mq)
        result = engine.run()

        assert result.success is False
        assert "取消" in (result.error_message or "")

    def test_build_config_value_error(self, monkeypatch):
        """Test _build_config catches ValueError."""
        import src.wizard.wizard_engine as we
        from src.wizard.interfaces import WizardConfig, WizardMode

        mock_ts = MagicMock()
        mock_ts.return_value.select.return_value = (["addr1"], None)
        monkeypatch.setattr(we, "TargetSelector", mock_ts)

        mock_ms = MagicMock()
        mock_ms.return_value.select.return_value = ("random", None, None)
        monkeypatch.setattr(we, "ModeSelector", mock_ms)

        mock_os = MagicMock()
        mock_os.return_value.select.return_value = (True, True, 0)
        monkeypatch.setattr(we, "OptionSelector", mock_os)

        mock_gs = MagicMock()
        mock_gs.return_value.select.return_value = ([], False)
        monkeypatch.setattr(we, "GPUSelector", mock_gs)

        from src.wizard.config_builder import ConfigBuilder

        mock_builder = MagicMock(spec=ConfigBuilder)
        mock_builder.return_value.build.side_effect = ValueError("bad config")
        monkeypatch.setattr(we, "ConfigBuilder", MagicMock(return_value=mock_builder.return_value))

        from src.wizard.message_queue import WizardMessageQueue

        mock_mq = MagicMock(spec=WizardMessageQueue)

        config = WizardConfig(
            mode=WizardMode.COMPACT,
            show_intro=False,
            show_summary=False,
            auto_continue=True,
        )
        engine = we.WizardEngine(config=config, message_queue=mock_mq)
        result = engine.run()

        assert result.success is False
        assert "Config validation" in (result.error_message or "")

    def test_execute_no_command(self, capsys):
        from src.wizard.wizard_engine import WizardEngine

        engine = WizardEngine()
        engine._execute()
        captured = capsys.readouterr()
        assert "没有可执行的命令" in captured.out

    def test_complete_user_declines(self, monkeypatch):
        from src.wizard.interfaces import WizardConfig, WizardMode
        from src.wizard.message_queue import WizardMessageQueue
        from src.wizard.wizard_engine import WizardEngine

        mock_mq = MagicMock(spec=WizardMessageQueue)
        config = WizardConfig(mode=WizardMode.INTERACTIVE, show_summary=False, auto_continue=False)
        engine = WizardEngine(config=config, message_queue=mock_mq)
        engine.result.success = False  # Pre-state
        engine.result.command = ["python", "test.py"]

        monkeypatch.setattr("builtins.input", lambda p: "n")
        engine._complete()

        assert engine.result.success is False
        assert "取消执行" in (engine.result.error_message or "")

    def test_complete_user_accepts(self, monkeypatch):
        from src.wizard.interfaces import WizardConfig, WizardMode
        from src.wizard.message_queue import WizardMessageQueue
        from src.wizard.wizard_engine import WizardEngine

        mock_mq = MagicMock(spec=WizardMessageQueue)
        config = WizardConfig(mode=WizardMode.INTERACTIVE, show_summary=False, auto_continue=False)
        engine = WizardEngine(config=config, message_queue=mock_mq)
        engine.result.command = ["python", "test.py"]

        monkeypatch.setattr("builtins.input", lambda p: "y")
        # Mock _execute to avoid subprocess.run
        engine._execute = MagicMock()
        engine._complete()

        assert engine.result.success is True
        engine._execute.assert_called_once()

    def test_show_summary(self, capsys):
        from src.wizard.wizard_engine import WizardEngine

        engine = WizardEngine()
        engine.result.targets = ["addr1", "addr2", "addr3"]
        engine.result.mode = "random"
        engine.result.gpu_indices = [0]
        engine._show_summary()
        captured = capsys.readouterr()
        assert "启动配置" in captured.out
        assert "addr1" in captured.out
        assert "+1 more" in captured.out

    def test_show_summary_no_gpu(self, capsys):
        from src.wizard.wizard_engine import WizardEngine

        engine = WizardEngine()
        engine.result.targets = ["addr1"]
        engine.result.mode = "random"
        engine.result.gpu_indices = []
        engine.result.duration = 0
        engine._show_summary()
        captured = capsys.readouterr()
        assert "不限制" in captured.out

    def test_execute_subprocess_error(self, monkeypatch, capsys):
        """Test _execute handles subprocess errors."""
        from src.wizard.wizard_engine import WizardEngine

        engine = WizardEngine()
        engine.result.command = ["nonexistent_command"]
        mock_run = MagicMock(side_effect=FileNotFoundError("no such command"))
        monkeypatch.setattr("subprocess.run", mock_run)
        engine._execute()
        captured = capsys.readouterr()
        assert "执行失败" in captured.out

    def test_complete_with_summary(self, monkeypatch):
        """Test _complete with show_summary=True."""
        from src.wizard.interfaces import WizardConfig, WizardMode
        from src.wizard.message_queue import WizardMessageQueue
        from src.wizard.wizard_engine import WizardEngine

        mock_mq = MagicMock(spec=WizardMessageQueue)
        config = WizardConfig(
            mode=WizardMode.COMPACT,
            show_intro=False,
            show_summary=True,
            auto_continue=True,
        )
        monkeypatch.setattr("subprocess.run", MagicMock())
        engine = WizardEngine(config=config, message_queue=mock_mq)
        engine.result.command = ["python", "test.py"]
        engine._complete()
        # Should not crash
        assert mock_mq.send_wizard_complete.called


# ============================================================================
# main() function tests
# ============================================================================


class TestWizardMain:
    """Test wizard_engine.main() function."""

    def test_main_compact(self, monkeypatch, capsys):
        """Test main with --compact flag."""
        import src.wizard.wizard_engine as we

        monkeypatch.setattr("sys.argv", ["wizard", "--compact"])
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_engine.return_value.run.return_value = mock_result
        monkeypatch.setattr(we, "WizardEngine", mock_engine)
        result = we.main()
        assert result == 0
        # Verify config was created with COMPACT mode
        args, kwargs = mock_engine.call_args
        assert kwargs["config"].mode.value == "compact"

    def test_main_auto(self, monkeypatch):
        """Test main with --auto flag."""
        import src.wizard.wizard_engine as we

        monkeypatch.setattr("sys.argv", ["wizard", "--auto"])
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_engine.return_value.run.return_value = mock_result
        monkeypatch.setattr(we, "WizardEngine", mock_engine)
        result = we.main()
        assert result == 0
        args, kwargs = mock_engine.call_args
        assert kwargs["config"].mode.value == "auto"

    def test_main_interactive_default(self, monkeypatch):
        """Test main with no flags (interactive mode)."""
        import src.wizard.wizard_engine as we

        monkeypatch.setattr("sys.argv", ["wizard"])
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_engine.return_value.run.return_value = mock_result
        monkeypatch.setattr(we, "WizardEngine", mock_engine)
        result = we.main()
        assert result == 0
        args, kwargs = mock_engine.call_args
        assert kwargs["config"].mode.value == "interactive"

    def test_main_failure_return_code(self, monkeypatch):
        """Test main returns 1 on failure."""
        import src.wizard.wizard_engine as we

        monkeypatch.setattr("sys.argv", ["wizard"])
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_engine.return_value.run.return_value = mock_result
        monkeypatch.setattr(we, "WizardEngine", mock_engine)
        result = we.main()
        assert result == 1

    def test_main_with_output(self, monkeypatch, tmp_path):
        """Test main with --output flag."""
        import src.wizard.wizard_engine as we

        output_file = str(tmp_path / "config.json")
        monkeypatch.setattr("sys.argv", ["wizard", "--output", output_file])
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_engine.return_value.run.return_value = mock_result
        monkeypatch.setattr(we, "WizardEngine", mock_engine)
        result = we.main()
        assert result == 0
        mock_result.save_to_file.assert_called_once_with(output_file)

    def test_main_module_guard(self, monkeypatch):
        """Test if __name__ == "__main__" guard."""
        import src.wizard.wizard_engine as we

        # Use exec to simulate the __name__ guard without re-executing the module
        monkeypatch.setattr("sys.argv", ["wizard"])
        monkeypatch.setattr("sys.exit", MagicMock())
        mock_engine = MagicMock()
        mock_engine.return_value.run.return_value = MagicMock(success=True)
        monkeypatch.setattr(we, "WizardEngine", mock_engine)
        import sys

        exec(
            "if __name__ == '__main__': sys.exit(main())",
            {"__name__": "__main__", "main": we.main, "sys": sys},
        )
        sys.exit.assert_called_once()
