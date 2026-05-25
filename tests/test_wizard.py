"""Tests for src/wizard package - 引导界面模块

Covers all wizard modules:
- __init__.py, selector_protocol.py, events.py, interfaces.py
- option_selector.py, mode_selector.py, config_builder.py
- message_queue.py, target_selector.py, gpu_selector.py, wizard_engine.py
"""

import json
from pathlib import Path
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
    """Test SelectorProtocol Protocol."""

    def test_protocol_interface(self):
        class MySelector:
            def get_selection(self) -> list[str]:
                return ["option1"]

        selector = MySelector()
        # Protocol uses structural typing; verify it has the required method
        assert hasattr(selector, "get_selection")
        assert callable(selector.get_selection)
        assert selector.get_selection() == ["option1"]

    def test_get_selection_returns_list(self):
        class MySelector:
            def get_selection(self) -> list[str]:
                return []

        selector = MySelector()
        assert selector.get_selection() == []

    def test_protocol_requires_get_selection(self):
        class BadSelector:
            pass

        # Protocol: structural typing, doesn't raise at instantiation
        # But mypy would flag this
        selector = BadSelector()
        # Protocol check via isinstance with structural typing
        assert not hasattr(selector, "get_selection")

    def test_get_selection_multiple(self):
        class MySelector:
            def get_selection(self) -> list[str]:
                return ["a", "b", "c"]

        selector = MySelector()
        assert len(selector.get_selection()) == 3


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

        event = WizardEvent(type=WizardEventType.WIZARD_START.value)
        assert event.type == "wizard_start"
        assert event.data == {}
        assert isinstance(event.timestamp, float)
        assert event.source == "wizard"

    def test_custom_values(self):
        from src.wizard.events import WizardEvent, WizardEventType

        event = WizardEvent(
            type=WizardEventType.TARGET_SELECTED.value,
            data={"targets": ["addr1"]},
            timestamp=12345.0,
            source="test",
        )
        assert event.data == {"targets": ["addr1"]}
        assert event.timestamp == 12345.0
        assert event.source == "test"

    def test_to_dict(self):
        from src.wizard.events import WizardEvent, WizardEventType

        event = WizardEvent(type=WizardEventType.MODE_SELECTED.value, data={"mode": "random"})
        d = event.to_dict()
        assert d["type"] == "mode_selected"
        assert d["data"] == {"mode": "random"}
        assert "timestamp" in d
        assert d["source"] == "wizard"


class TestEventDispatcher:
    """Test EventDispatcher."""

    def test_register_and_dispatch(self):
        from src.wizard.events import EventDispatcher, WizardEvent, WizardEventType

        dispatcher = EventDispatcher()
        callback = MagicMock()
        dispatcher.register(WizardEventType.WIZARD_START.value, callback)
        event = WizardEvent(type=WizardEventType.WIZARD_START.value)
        dispatcher.dispatch(event)
        callback.assert_called_once_with(event)

    def test_unregister(self):
        from src.wizard.events import EventDispatcher, WizardEvent, WizardEventType

        dispatcher = EventDispatcher()
        callback = MagicMock()
        dispatcher.register(WizardEventType.WIZARD_START.value, callback)
        dispatcher.unregister(WizardEventType.WIZARD_START.value, callback)
        event = WizardEvent(type=WizardEventType.WIZARD_START.value)
        dispatcher.dispatch(event)
        callback.assert_not_called()

    def test_dispatch_no_listeners(self):
        from src.wizard.events import EventDispatcher, WizardEvent, WizardEventType

        dispatcher = EventDispatcher()
        event = WizardEvent(type=WizardEventType.WIZARD_START.value)
        dispatcher.dispatch(event)  # should not raise

    def test_dispatch_callback_exception(self, caplog):
        from src.wizard.events import EventDispatcher, WizardEvent, WizardEventType

        dispatcher = EventDispatcher()

        def failing_callback(event):
            raise RuntimeError("test error")

        dispatcher.register(WizardEventType.WIZARD_ERROR.value, failing_callback)
        event = WizardEvent(type=WizardEventType.WIZARD_ERROR.value)
        dispatcher.dispatch(event)  # should not raise
        # Error should be logged
        assert "test error" in caplog.text

    def test_dispatch_multiple_callbacks(self):
        from src.wizard.events import EventDispatcher, WizardEvent, WizardEventType

        dispatcher = EventDispatcher()
        cb1 = MagicMock()
        cb2 = MagicMock()
        dispatcher.register(WizardEventType.WIZARD_START.value, cb1)
        dispatcher.register(WizardEventType.WIZARD_START.value, cb2)
        event = WizardEvent(type=WizardEventType.WIZARD_START.value)
        dispatcher.dispatch(event)
        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_clear(self):
        from src.wizard.events import EventDispatcher, WizardEvent, WizardEventType

        dispatcher = EventDispatcher()
        callback = MagicMock()
        dispatcher.register(WizardEventType.WIZARD_START.value, callback)
        dispatcher.clear()
        event = WizardEvent(type=WizardEventType.WIZARD_START.value)
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
        assert config.countdown_seconds == 5

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
        assert result.target_file == ""
        assert result.mode == ""
        assert result.checkpoint is False
        assert result.dedup is False
        assert result.duration == 0.0
        assert result.gpu_indices == []
        assert result.use_multi_gpu is False
        assert result.error_message == ""
        assert result.start_key == ""
        assert result.end_key == ""

    def test_to_dict(self):
        from src.wizard.interfaces import WizardResult

        result = WizardResult(success=True, targets=["addr1"], mode="range", duration=3600.0)
        d = result.to_dict()
        assert d["success"] is True
        assert d["targets"] == ["addr1"]
        assert d["mode"] == "range"
        assert d["duration"] == 3600.0
        assert d["error_message"] == ""

    def test_build_command(self):
        from src.wizard.interfaces import WizardResult

        result = WizardResult(success=True, targets=["addr1"], mode="random")
        cmd = result.build_command()
        assert isinstance(cmd, str)
        assert "random" in cmd
        assert "addr1" in cmd

    def test_save_to_file(self, tmp_path):
        from src.wizard.interfaces import WizardResult

        result = WizardResult(success=True, targets=["addr1"])
        filepath = tmp_path / "result.json"
        result.save_to_file(str(filepath))  # returns None
        assert filepath.exists()
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert data["targets"] == ["addr1"]

    def test_save_to_file_io_error(self, tmp_path):
        from src.wizard.interfaces import WizardResult

        result = WizardResult(success=True)
        # save_to_file raises OSError on invalid path
        with pytest.raises((OSError, PermissionError, IsADirectoryError)):
            result.save_to_file(str(tmp_path))

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
    """Test ConfigBuilder - builds command list from wizard selections."""

    def test_build_returns_list(self):
        from src.wizard.config_builder import ConfigBuilder

        selections = {"mode": "random", "targets": ["addr1"]}
        result = ConfigBuilder().build(selections)
        assert isinstance(result, list)
        assert "-m" in result
        assert "random" in result
        assert "addr1" in result

    def test_build_random_mode(self):
        from src.wizard.config_builder import ConfigBuilder

        selections = {
            "mode": "random",
            "targets": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
            "checkpoint": True,
            "dedup": True,
            "duration": 0,
        }
        result = ConfigBuilder().build(selections)
        assert isinstance(result, list)
        assert "random" in result
        assert "--checkpoint" in result
        assert "--dedup" in result

    def test_build_range_mode(self):
        from src.wizard.config_builder import ConfigBuilder

        selections = {
            "mode": "range",
            "targets": ["addr1"],
            "start_key": "abc123",
            "end_key": "def456",
            "checkpoint": False,
            "dedup": False,
        }
        result = ConfigBuilder().build(selections)
        assert "range" in result
        assert "--checkpoint" not in result
        assert "--dedup" not in result

    def test_build_brute_force_mode(self):
        from src.wizard.config_builder import ConfigBuilder

        selections = {
            "mode": "brute_force",
            "targets": ["addr1"],
            "start_key": "abc123",
        }
        result = ConfigBuilder().build(selections)
        assert "brute_force" in result

    def test_build_with_target_file(self):
        from src.wizard.config_builder import ConfigBuilder

        selections = {"targets": [], "target_file": "my_targets.txt", "mode": "random"}
        result = ConfigBuilder().build(selections)
        assert "random" in result

    def test_build_with_duration(self):
        from src.wizard.config_builder import ConfigBuilder

        selections = {"mode": "random", "duration": 7200}
        result = ConfigBuilder().build(selections)
        assert isinstance(result, list)
        assert "random" in result

    def test_build_with_gpu_indices(self):
        from src.wizard.config_builder import ConfigBuilder

        selections = {"mode": "random", "gpu_indices": [0, 1], "use_multi_gpu": True}
        result = ConfigBuilder().build(selections)
        assert "random" in result

    def test_build_empty_selections(self):
        from src.wizard.config_builder import ConfigBuilder

        result = ConfigBuilder().build({})
        assert isinstance(result, list)
        assert len(result) >= 2  # at least ["python", "key_collision_cli.py"]

    def test_build_preserves_extra_keys(self):
        from src.wizard.config_builder import ConfigBuilder

        selections = {"mode": "random", "custom_field": "value"}
        result = ConfigBuilder().build(selections)
        assert isinstance(result, list)
        assert "random" in result


# ============================================================================
# option_selector.py tests
# ============================================================================


class TestOptionSelector:
    """Test OptionSelector - matches actual API: select(options, key) -> str|None."""

    def test_select_by_key(self):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        options = [
            {"key": "checkpoint", "value": "enabled"},
            {"key": "dedup", "value": "disabled"},
        ]
        result = selector.select(options, "checkpoint")
        assert result == "enabled"

    def test_select_key_not_found(self):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        options = [{"key": "checkpoint", "value": "enabled"}]
        result = selector.select(options, "nonexistent")
        assert result is None

    def test_select_empty_options(self):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        result = selector.select([], "any")
        assert result is None

    def test_select_multiple_options(self):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        options = [
            {"key": "a", "value": 1},
            {"key": "b", "value": 2},
            {"key": "c", "value": 3},
        ]
        assert selector.select(options, "a") == 1
        assert selector.select(options, "b") == 2
        assert selector.select(options, "c") == 3

    def test_select_option_without_value(self):
        from src.wizard.option_selector import OptionSelector

        selector = OptionSelector()
        options = [{"key": "test"}, {"key": "other", "value": "val"}]
        result = selector.select(options, "test")
        assert result is None


# ============================================================================
# mode_selector.py tests
# ============================================================================


class TestModeSelector:
    """Test ModeSelector - matches actual API: select(options) -> str."""

    def test_select_first_option(self):
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        result = selector.select(["random", "range", "brute_force"])
        assert result == "random"

    def test_select_empty_returns_empty_str(self):
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        result = selector.select([])
        assert result == ""

    def test_select_single_option(self):
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        result = selector.select(["random"])
        assert result == "random"

    def test_select_returns_string(self):
        from src.wizard.mode_selector import ModeSelector

        selector = ModeSelector()
        result = selector.select(["custom_mode"])
        assert isinstance(result, str)
        assert result == "custom_mode"


# ============================================================================
# message_queue.py tests
# ============================================================================


class TestWizardMessageQueue:
    """Test WizardMessageQueue - matches actual stub API: send(message), receive(timeout)."""

    def test_send_and_receive(self):
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        mq.send({"type": "test", "data": "hello"})
        msg = mq.receive(timeout=0.1)
        assert msg == {"type": "test", "data": "hello"}

    def test_receive_timeout_returns_none(self):
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        msg = mq.receive(timeout=0.01)
        assert msg is None

    def test_fifo_order(self):
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        mq.send("first")
        mq.send("second")
        mq.send("third")
        assert mq.receive() == "first"
        assert mq.receive() == "second"
        assert mq.receive() == "third"

    def test_send_any_type(self):
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        mq.send(42)
        mq.send([1, 2, 3])
        mq.send(None)
        assert mq.receive() == 42
        assert mq.receive() == [1, 2, 3]
        assert mq.receive() is None

    def test_receive_custom_timeout(self):
        from src.wizard.message_queue import WizardMessageQueue

        mq = WizardMessageQueue()
        mq.send("msg")
        assert mq.receive(timeout=5.0) == "msg"


class TestMessageQueueGlobal:
    """Test global message queue functions."""

    def test_get_message_queue_singleton(self):
        from src.wizard.message_queue import get_message_queue

        q1 = get_message_queue()
        q2 = get_message_queue()
        assert q1 is q2

    def test_get_message_queue_works(self):
        from src.wizard.message_queue import WizardMessageQueue, get_message_queue

        q = get_message_queue()
        assert isinstance(q, WizardMessageQueue)
        q.send("test")
        assert q.receive() == "test"


# ============================================================================
# target_selector.py tests
# ============================================================================


class TestTargetSelector:
    """Test TargetSelector - matches actual API: select(targets) -> list[str]."""

    def test_select_returns_copy(self):
        from src.wizard.target_selector import TargetSelector

        selector = TargetSelector()
        targets = ["addr1", "addr2"]
        result = selector.select(targets)
        assert result == ["addr1", "addr2"]
        assert result is not targets  # returns a copy

    def test_select_empty(self):
        from src.wizard.target_selector import TargetSelector

        selector = TargetSelector()
        result = selector.select([])
        assert result == []

    def test_select_single(self):
        from src.wizard.target_selector import TargetSelector

        selector = TargetSelector()
        result = selector.select(["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])
        assert result == ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]

    def test_select_modification_does_not_affect_original(self):
        from src.wizard.target_selector import TargetSelector

        selector = TargetSelector()
        targets = ["a", "b"]
        result = selector.select(targets)
        result.append("c")
        assert targets == ["a", "b"]


class TestTargetResolver:
    """Test TargetResolver stub."""

    def test_resolve_valid_p2pkh(self):
        from src.wizard.target_selector import TargetResolver

        resolver = TargetResolver()
        result = resolver.resolve("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        assert result == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

    def test_resolve_valid_p2sh(self):
        from src.wizard.target_selector import TargetResolver

        resolver = TargetResolver()
        result = resolver.resolve("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy")
        assert result == "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"

    def test_resolve_valid_bech32(self):
        from src.wizard.target_selector import TargetResolver

        resolver = TargetResolver()
        result = resolver.resolve("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")
        assert result == "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"

    def test_resolve_invalid_returns_none(self):
        from src.wizard.target_selector import TargetResolver

        resolver = TargetResolver()
        result = resolver.resolve("invalid_address")
        assert result is None

    def test_resolve_multiple(self):
        from src.wizard.target_selector import TargetResolver

        resolver = TargetResolver()
        results = resolver.resolve_multiple(["1addr", "bad", "3addr"])
        assert results == ["1addr", "3addr"]

    def test_clear_cache(self):
        from src.wizard.target_selector import TargetResolver

        resolver = TargetResolver()
        resolver.resolve("1addr")
        resolver.clear_cache()
        stats = resolver.get_cache_stats()
        assert stats["size"] == 0

    def test_get_cache_stats(self):
        from src.wizard.target_selector import TargetResolver

        resolver = TargetResolver(cache_max_size=500)
        stats = resolver.get_cache_stats()
        assert stats["max_size"] == 500
        assert stats["size"] == 0


# ============================================================================
# gpu_selector.py tests
# ============================================================================


class TestGPUSelector:
    """Test GPUSelector - matches actual API: select(devices) -> list[int]."""

    def test_select_empty_devices(self):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        result = selector.select([])
        assert result == []

    def test_select_single_device(self):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        result = selector.select([{"name": "GPU1", "index": 0}])
        assert result == [0]

    def test_select_multiple_devices(self):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        result = selector.select([
            {"name": "GPU1", "index": 0},
            {"name": "GPU2", "index": 1},
        ])
        assert result == [0, 1]

    def test_select_devices_without_index(self):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        # Devices without "index" key fall back to enumerate position
        result = selector.select([{"name": "GPU1"}, {"name": "GPU2"}])
        assert result == [0, 1]

    def test_select_devices_mixed_index(self):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        result = selector.select([
            {"name": "GPU0"},
            {"name": "GPU1", "index": 5},
            {"name": "GPU2"},
        ])
        assert result == [0, 5, 2]

    def test_select_device_with_index_zero(self):
        from src.wizard.gpu_selector import GPUSelector

        selector = GPUSelector()
        result = selector.select([{"name": "GPU0", "index": 0}])
        assert result == [0]


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
        mock_target_selector.return_value.select.return_value = ["addr1"]
        monkeypatch.setattr(we, "TargetSelector", mock_target_selector)

        # Mock ModeSelector
        mock_mode_selector = MagicMock()
        mock_mode_selector.return_value.select.return_value = "random"
        monkeypatch.setattr(we, "ModeSelector", mock_mode_selector)

        # Mock OptionSelector
        mock_opt_selector = MagicMock()
        mock_opt_selector.return_value.select.return_value = None
        monkeypatch.setattr(we, "OptionSelector", mock_opt_selector)

        # Mock GPUSelector
        mock_gpu_selector = MagicMock()
        mock_gpu_selector.return_value.select.return_value = []
        monkeypatch.setattr(we, "GPUSelector", mock_gpu_selector)

        # Mock ConfigBuilder to return a command list
        mock_config_builder = MagicMock()
        mock_config_builder.return_value.build.return_value = [
            "python", "key_collision_cli.py", "-m", "random"
        ]
        monkeypatch.setattr(we, "ConfigBuilder", mock_config_builder)

        # Mock message queue
        mock_mq = MagicMock()

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
                return []
            import time

            time.sleep(0.05)  # Give stop thread time to cancel
            return ["addr1"]

        mock_target_selector.return_value.select.side_effect = select_side_effect
        monkeypatch.setattr(we, "TargetSelector", mock_target_selector)

        mock_mode_selector = MagicMock()
        mock_mode_selector.return_value.select.return_value = "random"
        monkeypatch.setattr(we, "ModeSelector", mock_mode_selector)

        mock_opt_selector = MagicMock()
        mock_opt_selector.return_value.select.return_value = None
        monkeypatch.setattr(we, "OptionSelector", mock_opt_selector)

        mock_gpu_selector = MagicMock()
        mock_gpu_selector.return_value.select.return_value = []
        monkeypatch.setattr(we, "GPUSelector", mock_gpu_selector)

        mock_mq = MagicMock()

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

        mock_mq = MagicMock()

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

        mock_mq = MagicMock()

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
        mock_ts.return_value.select.return_value = ["addr1"]
        monkeypatch.setattr(we, "TargetSelector", mock_ts)

        mock_ms = MagicMock()
        mock_ms.return_value.select.return_value = "random"
        monkeypatch.setattr(we, "ModeSelector", mock_ms)

        mock_os = MagicMock()
        mock_os.return_value.select.return_value = None
        monkeypatch.setattr(we, "OptionSelector", mock_os)

        mock_gs = MagicMock()
        mock_gs.return_value.select.return_value = []
        monkeypatch.setattr(we, "GPUSelector", mock_gs)

        from src.wizard.config_builder import ConfigBuilder

        mock_builder = MagicMock(spec=ConfigBuilder)
        mock_builder.return_value.build.side_effect = ValueError("bad config")
        monkeypatch.setattr(we, "ConfigBuilder", MagicMock(return_value=mock_builder.return_value))

        mock_mq = MagicMock()

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
        from src.wizard.wizard_engine import WizardEngine

        mock_mq = MagicMock()
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
        from src.wizard.wizard_engine import WizardEngine

        mock_mq = MagicMock()
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
        from src.wizard.wizard_engine import WizardEngine

        mock_mq = MagicMock()
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
        assert mock_mq.send.called


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

    def test_main_with_output(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
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
        mock_exit = MagicMock()
        monkeypatch.setattr("sys.exit", mock_exit)
        mock_engine = MagicMock()
        mock_engine.return_value.run.return_value = MagicMock(success=True)
        monkeypatch.setattr(we, "WizardEngine", mock_engine)
        import sys

        exec(
            "if __name__ == '__main__': sys.exit(main())",
            {"__name__": "__main__", "main": we.main, "sys": sys},
        )
        mock_exit.assert_called_once()
