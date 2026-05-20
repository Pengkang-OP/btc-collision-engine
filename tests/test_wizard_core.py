"""引导模块核心测试 — wizard events, interfaces, engine"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.wizard.events import EventDispatcher, WizardEvent, WizardEventType  # noqa: E402
from src.wizard.interfaces import WizardConfig, WizardMode, WizardResult  # noqa: E402


class TestWizardEventType(unittest.TestCase):
    """WizardEventType 枚举测试"""

    def test_event_type_values(self):
        self.assertEqual(WizardEventType.WIZARD_START.value, "wizard_start")
        self.assertEqual(WizardEventType.TARGET_SELECTED.value, "target_selected")
        self.assertEqual(WizardEventType.MODE_SELECTED.value, "mode_selected")
        self.assertEqual(WizardEventType.OPTIONS_SELECTED.value, "options_selected")
        self.assertEqual(WizardEventType.GPU_SELECTED.value, "gpu_selected")
        self.assertEqual(WizardEventType.CONFIG_BUILT.value, "config_built")
        self.assertEqual(WizardEventType.WIZARD_COMPLETE.value, "wizard_complete")
        self.assertEqual(WizardEventType.WIZARD_CANCELLED.value, "wizard_cancelled")
        self.assertEqual(WizardEventType.WIZARD_ERROR.value, "wizard_error")

    def test_event_type_is_enum(self):
        self.assertIsInstance(WizardEventType.WIZARD_START, WizardEventType)


class TestWizardEvent(unittest.TestCase):
    """WizardEvent 数据类测试"""

    def test_create_event(self):
        event = WizardEvent(
            event_type=WizardEventType.WIZARD_START,
            data={"mode": "interactive"},
        )
        self.assertEqual(event.event_type, WizardEventType.WIZARD_START)
        self.assertEqual(event.data, {"mode": "interactive"})
        self.assertEqual(event.source, "wizard")

    def test_create_event_with_timestamp(self):
        event = WizardEvent(event_type=WizardEventType.MODE_SELECTED, timestamp=12345.0)
        self.assertEqual(event.timestamp, 12345.0)

    def test_to_dict(self):
        event = WizardEvent(
            event_type=WizardEventType.TARGET_SELECTED,
            data={"targets": ["addr1", "addr2"]},
            timestamp=1000.0,
        )
        d = event.to_dict()
        self.assertEqual(d["event_type"], "target_selected")
        self.assertEqual(d["data"], {"targets": ["addr1", "addr2"]})
        self.assertEqual(d["timestamp"], 1000.0)
        self.assertEqual(d["source"], "wizard")

    def test_default_data_empty(self):
        event = WizardEvent(event_type=WizardEventType.WIZARD_COMPLETE)
        self.assertEqual(event.data, {})


class TestEventDispatcher(unittest.TestCase):
    """EventDispatcher 测试"""

    def setUp(self):
        self.dispatcher = EventDispatcher()

    def test_register_and_dispatch(self):
        received = []
        def handler(event):
            received.append(event.event_type)
        self.dispatcher.register(WizardEventType.WIZARD_START, handler)
        event = WizardEvent(event_type=WizardEventType.WIZARD_START)
        self.dispatcher.dispatch(event)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], WizardEventType.WIZARD_START)

    def test_unregister(self):
        received = []
        def handler(event):
            received.append(1)
        self.dispatcher.register(WizardEventType.WIZARD_COMPLETE, handler)
        self.dispatcher.unregister(WizardEventType.WIZARD_COMPLETE, handler)
        event = WizardEvent(event_type=WizardEventType.WIZARD_COMPLETE)
        self.dispatcher.dispatch(event)
        self.assertEqual(len(received), 0)

    def test_dispatch_unregistered_event(self):
        event = WizardEvent(event_type=WizardEventType.MODE_SELECTED)
        self.dispatcher.dispatch(event)

    def test_multiple_handlers(self):
        results = []
        def h1(event):
            results.append(1)
        def h2(event):
            results.append(2)
        self.dispatcher.register(WizardEventType.TARGET_SELECTED, h1)
        self.dispatcher.register(WizardEventType.TARGET_SELECTED, h2)
        event = WizardEvent(event_type=WizardEventType.TARGET_SELECTED)
        self.dispatcher.dispatch(event)
        self.assertEqual(results, [1, 2])

    def test_handler_exception_does_not_block(self):
        results = []
        def bad_handler(event):
            raise RuntimeError("test")
        def good_handler(event):
            results.append(1)
        self.dispatcher.register(WizardEventType.WIZARD_ERROR, bad_handler)
        self.dispatcher.register(WizardEventType.WIZARD_ERROR, good_handler)
        event = WizardEvent(event_type=WizardEventType.WIZARD_ERROR)
        self.dispatcher.dispatch(event)
        self.assertEqual(results, [1])

    def test_clear(self):
        received = []
        def handler(event):
            received.append(1)
        self.dispatcher.register(WizardEventType.WIZARD_START, handler)
        self.dispatcher.clear()
        event = WizardEvent(event_type=WizardEventType.WIZARD_START)
        self.dispatcher.dispatch(event)
        self.assertEqual(len(received), 0)


class TestWizardMode(unittest.TestCase):
    """WizardMode 枚举测试"""

    def test_mode_values(self):
        self.assertEqual(WizardMode.INTERACTIVE.value, "interactive")
        self.assertEqual(WizardMode.COMPACT.value, "compact")
        self.assertEqual(WizardMode.AUTO.value, "auto")


class TestWizardConfig(unittest.TestCase):
    """WizardConfig 测试"""

    def test_defaults(self):
        cfg = WizardConfig()
        self.assertEqual(cfg.mode, WizardMode.INTERACTIVE)
        self.assertTrue(cfg.show_intro)
        self.assertTrue(cfg.show_summary)
        self.assertTrue(cfg.validate_input)
        self.assertFalse(cfg.auto_continue)
        self.assertEqual(cfg.countdown_seconds, 3)

    def test_custom_config(self):
        cfg = WizardConfig(
            mode=WizardMode.AUTO,
            show_intro=False,
            countdown_seconds=5,
        )
        self.assertEqual(cfg.mode, WizardMode.AUTO)
        self.assertFalse(cfg.show_intro)
        self.assertEqual(cfg.countdown_seconds, 5)


class TestWizardResult(unittest.TestCase):
    """WizardResult 测试"""

    def test_defaults(self):
        r = WizardResult()
        self.assertFalse(r.success)
        self.assertEqual(r.targets, [])
        self.assertEqual(r.mode, "random")
        self.assertTrue(r.checkpoint)
        self.assertTrue(r.dedup)
        self.assertEqual(r.gpu_indices, [])
        self.assertFalse(r.use_multi_gpu)

    def test_custom_result(self):
        r = WizardResult(
            success=True,
            targets=["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
            mode="range",
            gpu_indices=[0],
        )
        self.assertTrue(r.success)
        self.assertEqual(len(r.targets), 1)
        self.assertEqual(r.mode, "range")

    def test_to_dict(self):
        r = WizardResult(success=True, mode="sequential", targets=["addr1"])
        d = r.to_dict()
        self.assertTrue(d["success"])
        self.assertEqual(d["mode"], "sequential")
        self.assertEqual(d["targets"], ["addr1"])

    def test_build_command(self):
        r = WizardResult(
            success=True,
            targets=["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
            mode="random",
            checkpoint=True,
            dedup=True,
        )
        cmd = r.build_command()
        self.assertIsInstance(cmd, list)
        self.assertIn("random", cmd or [])  # command should include mode

    def test_save_to_file(self):
        r = WizardResult(success=True, mode="random")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            result = r.save_to_file(filepath)
            self.assertTrue(result)
            loaded = WizardResult.load_from_file(filepath)
            self.assertIsNotNone(loaded)
            self.assertTrue(loaded.success)
            self.assertEqual(loaded.mode, "random")
        finally:
            os.unlink(filepath)

    def test_load_from_file_nonexistent(self):
        result = WizardResult.load_from_file("/nonexistent/wizard_result.json")
        self.assertIsNone(result)

    def test_load_from_file_invalid_json(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"not valid json")
            filepath = f.name
        try:
            result = WizardResult.load_from_file(filepath)
            self.assertIsNone(result)
        finally:
            os.unlink(filepath)


if __name__ == "__main__":
    unittest.main(verbosity=2)
