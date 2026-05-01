#!/usr/bin/env python3
"""向导模块核心组件单元测试

覆盖 src/wizard/ 下未充分测试的模块：
- interfaces.py (WizardMode, WizardConfig, WizardResult)
- mode_selector.py (ModeSelector)
- gpu_selector.py (GPUSelector)
- option_selector.py (OptionSelector)
- selector_protocol.py (SelectorProtocol)
- config_builder.py (ConfigBuilder)
- events.py (WizardEvent, WizardEventType)
- message_queue.py (MessageQueue)
"""

import pytest
from unittest.mock import patch

from src.wizard.interfaces import WizardMode, WizardConfig, WizardResult
from src.wizard.selector_protocol import SelectorProtocol
from src.wizard.mode_selector import ModeSelector
from src.wizard.gpu_selector import GPUSelector
from src.wizard.config_builder import ConfigBuilder
from src.wizard.events import WizardEvent, WizardEventType
from src.wizard.message_queue import (
    WizardMessageQueue,
    get_message_queue,
    set_message_queue,
    reset_message_queue,
)

# ============================================================================
# 1. WizardMode & WizardConfig & WizardResult 测试
# ============================================================================


class TestWizardMode:
    """WizardMode 枚举测试"""

    def test_values(self):
        assert WizardMode.INTERACTIVE.value == "interactive"
        assert WizardMode.COMPACT.value == "compact"
        assert WizardMode.AUTO.value == "auto"


class TestWizardConfig:
    """WizardConfig 测试"""

    def test_defaults(self):
        config = WizardConfig()
        assert config.mode == WizardMode.INTERACTIVE
        assert config.show_intro is True
        assert config.show_summary is True
        assert config.validate_input is True
        assert config.auto_continue is False
        assert config.countdown_seconds == 3

    def test_custom(self):
        config = WizardConfig(mode=WizardMode.AUTO, show_intro=False, countdown_seconds=10)
        assert config.mode == WizardMode.AUTO
        assert config.show_intro is False
        assert config.countdown_seconds == 10


class TestWizardResult:
    """WizardResult 测试"""

    def test_default_values(self):
        result = WizardResult()
        assert result.success is False
        assert result.targets == []
        assert result.mode == "random"
        assert result.checkpoint is True
        assert result.dedup is True

    def test_to_dict(self):
        result = WizardResult(
            success=True,
            targets=["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
            mode="random",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert len(d["targets"]) == 1
        assert d["mode"] == "random"

    def test_to_dict_excludes_none_error(self):
        result = WizardResult()
        d = result.to_dict()
        assert d["error_message"] is None

    def test_save_and_load(self, tmp_path):
        result = WizardResult(
            success=True,
            targets=["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
            mode="random",
            gpu_indices=[0, 1],
            use_multi_gpu=True,
        )
        filepath = str(tmp_path / "result.json")
        assert result.save_to_file(filepath) is True
        loaded = WizardResult.load_from_file(filepath)
        assert loaded is not None
        assert loaded.success is True
        assert loaded.mode == "random"
        assert loaded.use_multi_gpu is True

    def test_load_nonexistent_file(self):
        result = WizardResult.load_from_file("/nonexistent/path.json")
        assert result is None

    def test_save_to_invalid_path(self):
        result = WizardResult(success=True)
        saved = result.save_to_file("/invalid_path/result.json")
        assert saved is False

    def test_build_command(self):
        result = WizardResult(
            success=True,
            targets=["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
            mode="random",
        )
        cmd = result.build_command()
        assert isinstance(cmd, list)
        assert "random" in cmd or any("random" in str(x) for x in cmd)


# ============================================================================
# 2. ModeSelector 测试
# ============================================================================


class TestModeSelector:
    """ModeSelector 测试"""

    def test_modes_defined(self):
        selector = ModeSelector()
        assert "1" in selector.MODES
        assert "2" in selector.MODES
        assert "3" in selector.MODES
        assert selector.MODES["1"]["name"] == "random"
        assert selector.MODES["2"]["name"] == "range"
        assert selector.MODES["3"]["name"] == "brute_force"

    def test_select_compact_returns_random(self):
        selector = ModeSelector()
        mode, start, end = selector.select(compact=True)
        assert mode == "random"
        assert start is None
        assert end is None

    @patch("builtins.input", return_value="1")
    def test_select_choice_1_random(self, mock_input):
        selector = ModeSelector()
        mode, start, end = selector.select(compact=False)
        assert mode == "random"

    @patch("builtins.input", side_effect=["2", "deadbeef", "cafebabe"])
    def test_select_choice_2_range(self, mock_input):
        selector = ModeSelector()
        mode, start, end = selector.select(compact=False)
        assert mode == "range"
        assert start == "deadbeef"
        assert end == "cafebabe"

    @patch("builtins.input", side_effect=["3", "abcd1234"])
    def test_select_choice_3_brute_force(self, mock_input):
        selector = ModeSelector()
        mode, start, end = selector.select(compact=False)
        assert mode == "brute_force"
        assert start == "abcd1234"

    @patch("builtins.input", side_effect=["99", "1"])
    def test_invalid_then_valid(self, mock_input):
        selector = ModeSelector()
        mode, _, _ = selector.select(compact=False)
        assert mode == "random"


# ============================================================================
# 3. GPUSelector 测试
# ============================================================================


class TestGPUSelector:
    """GPUSelector 测试"""

    def test_select_compact_no_gpu(self):
        selector = GPUSelector()
        with patch.object(selector, "_detect_gpus", return_value=[]):
            indices, multi = selector.select(compact=True)
            assert indices == []
            assert multi is False

    def test_detect_gpus_empty(self):
        selector = GPUSelector()
        with patch.object(selector, "_detect_gpus", return_value=[]):
            result = selector._detect_gpus()
            assert result == []

    def test_detect_gpus_with_devices(self):
        selector = GPUSelector()
        gpu_info = [
            {"index": 0, "name": "RTX 3080"},
            {"index": 1, "name": "Arc A770"},
        ]
        with patch.object(selector, "_detect_gpus", return_value=gpu_info):
            result = selector._detect_gpus()
            assert len(result) == 2
            assert result[0]["name"] == "RTX 3080"
            assert result[1]["name"] == "Arc A770"

    def test_detect_gpus_exception(self):
        """测试 _detect_gpus 内部 GPUDeviceDetector 异常被捕获后返回空列表"""
        selector = GPUSelector()
        with patch("src.gpu.device.GPUDeviceDetector") as mock_cls:
            mock_cls.detect_devices.side_effect = RuntimeError("No GPU")
            result = selector._detect_gpus()
            assert result == []

    def test_select_compact_multi_gpu(self):
        selector = GPUSelector()
        gpu_info = [{"index": 0, "name": "GPU0"}, {"index": 1, "name": "GPU1"}]
        with patch.object(selector, "_detect_gpus", return_value=gpu_info):
            indices, multi = selector.select(compact=True)
            assert len(indices) == 2
            assert multi is True

    def test_select_compact_single_gpu(self):
        selector = GPUSelector()
        with patch.object(selector, "_detect_gpus", return_value=[{"index": 0, "name": "GPU0"}]):
            indices, multi = selector.select(compact=True)
            assert indices == [0]
            assert multi is False


# ============================================================================
# 4. SelectorProtocol 测试
# ============================================================================


class TestSelectorProtocol:
    """SelectorProtocol 抽象类测试"""

    def test_can_subclass(self):
        class MySelector(SelectorProtocol):
            def select(self, compact=False):
                return "result"

        selector = MySelector()
        assert selector.select() == "result"

    def test_must_implement_select(self):
        with pytest.raises(TypeError):
            SelectorProtocol()


# ============================================================================
# 5. ConfigBuilder 测试
# ============================================================================


class TestConfigBuilder:
    """ConfigBuilder 测试"""

    def test_build_random_mode(self):
        builder = ConfigBuilder()
        result = WizardResult(
            success=True,
            targets=["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
            mode="random",
        )
        cmd = builder.build(result)
        assert isinstance(cmd, list)

    def test_build_range_mode(self):
        builder = ConfigBuilder()
        result = WizardResult(
            success=True,
            targets=["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
            mode="range",
            start_key="0x1",
            end_key="0xFFF",
        )
        cmd = builder.build(result)
        assert isinstance(cmd, list)

    def test_build_without_targets(self):
        builder = ConfigBuilder()
        result = WizardResult(success=False, mode="random")
        with pytest.raises(ValueError, match="No targets specified"):
            builder.build(result)


# ============================================================================
# 6. WizardEvent & WizardEventType 测试
# ============================================================================


class TestWizardEventType:
    """WizardEventType 测试"""

    def test_events_defined(self):
        expected = [
            "wizard_start",
            "target_selected",
            "mode_selected",
            "gpu_selected",
            "wizard_complete",
            "wizard_error",
            "wizard_cancelled",
        ]
        for name in expected:
            assert hasattr(WizardEventType, name.upper())

    def test_values(self):
        assert WizardEventType.WIZARD_START.value == "wizard_start"
        assert WizardEventType.WIZARD_ERROR.value == "wizard_error"


class TestWizardEvent:
    """WizardEvent 测试"""

    def test_creation(self):
        event = WizardEvent(
            event_type=WizardEventType.WIZARD_START,
        )
        assert event.event_type == WizardEventType.WIZARD_START
        assert isinstance(event.timestamp, float)

    def test_to_dict(self):
        event = WizardEvent(
            event_type=WizardEventType.WIZARD_COMPLETE,
            data={"mode": "random"},
        )
        d = event.to_dict()
        assert d["event_type"] == "wizard_complete"
        assert d["data"] == {"mode": "random"}


# ============================================================================
# 7. MessageQueue 测试
# ============================================================================


class TestWizardMessageQueue:
    """WizardMessageQueue 测试"""

    def test_init_empty(self):
        mq = WizardMessageQueue()
        assert mq.size() == 0
        assert mq.is_empty() is True

    def test_send_and_receive(self):
        mq = WizardMessageQueue()
        mq.send(WizardEventType.WIZARD_START, {"key": "val"})
        assert mq.size() == 1
        event = mq.receive(timeout=0.1)
        assert event is not None
        assert event.event_type == WizardEventType.WIZARD_START

    def test_receive_all(self):
        mq = WizardMessageQueue()
        for i in range(5):
            mq.send(WizardEventType.USER_INPUT, {"idx": i})
        events = mq.receive_all()
        assert len(events) == 5

    def test_clear(self):
        mq = WizardMessageQueue()
        for i in range(10):
            mq.send(WizardEventType.USER_INPUT, {"item": i})
        mq.clear()
        assert mq.is_empty() is True

    def test_disable_blocks_send(self):
        mq = WizardMessageQueue()
        mq.disable()
        result = mq.send(WizardEventType.WIZARD_START, {})
        assert result is False

    def test_enable_re_enables(self):
        mq = WizardMessageQueue()
        mq.disable()
        mq.enable()
        result = mq.send(WizardEventType.WIZARD_START, {})
        assert result is True

    def test_subscribe_notify(self):
        mq = WizardMessageQueue()
        received = []
        mq.subscribe(lambda e: received.append(e))
        mq.send(WizardEventType.TARGET_SELECTED, {"targets": []})
        assert len(received) == 1

    def test_unsubscribe(self):
        mq = WizardMessageQueue()

        def cb(e):  # noqa: E306
            return None

        mq.subscribe(cb)
        mq.unsubscribe(cb)
        assert len(mq._subscribers) == 0

    def test_is_full(self):
        mq = WizardMessageQueue(maxsize=2)
        mq.send(WizardEventType.USER_INPUT, {})
        mq.send(WizardEventType.USER_INPUT, {})
        assert mq.is_full() is True

    def test_queue_full_drops_event(self):
        mq = WizardMessageQueue(maxsize=2)
        mq.send(WizardEventType.USER_INPUT, {})
        mq.send(WizardEventType.USER_INPUT, {})
        result = mq.send(WizardEventType.USER_INPUT, {})
        assert result is False


class TestGlobalMessageQueue:
    """全局消息队列函数测试"""

    @pytest.fixture(autouse=True)
    def _isolate_global_queue(self):
        """测试前后保存/恢复全局队列状态，防止测试间相互干扰"""
        import src.wizard.message_queue as mq_mod

        saved = mq_mod._global_message_queue
        yield
        mq_mod._global_message_queue = saved

    def test_get_message_queue_returns_same_instance(self):
        q1 = get_message_queue()
        q2 = get_message_queue()
        assert q1 is q2

    def test_set_message_queue(self):
        custom = WizardMessageQueue(maxsize=50)
        set_message_queue(custom)
        result = get_message_queue()
        assert result is custom

    def test_reset_message_queue(self):
        custom = WizardMessageQueue()
        reset_message_queue(custom)
        result = get_message_queue()
        assert result is custom
