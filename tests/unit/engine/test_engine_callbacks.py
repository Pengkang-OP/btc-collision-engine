"""KeyCollisionEngine 回调测试 (MAINT-1拆分).

原 file: test_key_collision_engine.py
抽取类: TestKeyCollisionEngineCallbacks, TestKeyCollisionEngineSafeCallback
"""

import threading
import time
from unittest.mock import patch

from src.collision.collision_stats import CollisionStats
from src.collision.key_collision_engine import KeyCollisionEngine
from tests.conftest_engine import get_known_target


class TestKeyCollisionEngineCallbacks:
    """回调函数测试."""

    def test_progress_callback_called(self):
        """进度回调在运行期间被调用."""
        progress_events = []

        def on_progress(stats: CollisionStats):
            progress_events.append(stats.total_checked)

        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            on_progress=on_progress,
            max_workers=1,
        )
        engine.start(mode="random")
        time.sleep(2.5)
        engine.stop()

        assert len(progress_events) > 0, "进度回调应至少被调用一次"

    def test_complete_callback_called(self):
        """完成回调在停止后被调用."""
        complete_called = threading.Event()

        def on_complete(stats: CollisionStats):
            complete_called.set()

        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            on_complete=on_complete,
            max_workers=1,
        )
        engine.start(mode="random")
        time.sleep(1.0)
        engine.stop()
        complete_called.wait(timeout=15)
        assert complete_called.is_set(), "完成回调应在stop后触发"

    def test_match_callback_called_for_known_key(self):
        """使用已知私钥-地址对，range 扫描找到匹配后触发回调."""
        _, known_addr = get_known_target()
        match_event = threading.Event()
        match_results = []

        def on_match(pk: bytes, addr: str, wif: str):
            match_results.append((pk, addr, wif))
            match_event.set()

        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=on_match,
            max_workers=1,
        )
        engine.start(mode="range", start=1, end=5)
        match_event.wait(timeout=10)
        engine.stop()

        assert match_event.is_set(), "应在范围[1,5]内找到匹配"
        assert len(match_results) > 0
        _, found_addr, wif = match_results[0]
        assert found_addr == known_addr
        assert wif.startswith(("K", "L", "5"))


class TestKeyCollisionEngineSafeCallback:
    """安全回调 _safe_invoke_match_callback 异常/超时路径."""

    def test_match_callback_exception_isolation(self):
        """匹配回调抛出异常不影响引擎运行."""
        _, known_addr = get_known_target()
        exception_raised = threading.Event()

        def on_match_error(pk: bytes, addr: str, wif: str):
            exception_raised.set()
            raise ValueError("模拟回调异常")

        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=on_match_error,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.start(mode="range", start=1, end=5)
        exception_raised.wait(timeout=10)
        time.sleep(0.5)
        stats = engine.get_stats()
        assert stats.total_checked > 0, "引擎应继续运行"
        engine.stop()

    def test_match_callback_slow_isolation(self):
        """慢速匹配回调由 _safe_invoke_match_callback 超时保护."""
        _, known_addr = get_known_target()
        callback_started = threading.Event()
        callback_completed = threading.Event()

        def on_match_slow(pk: bytes, addr: str, wif: str):
            callback_started.set()
            time.sleep(10)
            callback_completed.set()

        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=on_match_slow,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._match_callback_timeout = 1
        engine.start(mode="range", start=1, end=5)
        callback_started.wait(timeout=10)
        time.sleep(1.5)
        stats = engine.get_stats()
        assert stats.total_checked > 0
        engine.stop()

    def test_safe_invoke_callback_no_handler(self):
        """on_match=None 时 _safe_invoke_match_callback 返回 True."""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            on_match=None,
            max_workers=1,
            data_logging_enabled=False,
        )
        result = engine._safe_invoke_match_callback((1).to_bytes(32, "big"), "1TestAddr", "WIF123")
        assert result
        engine.stop()

    def test_safe_invoke_callback_outer_exception(self):
        """_safe_invoke_match_callback 外层异常隔离."""
        _, known_addr = get_known_target()

        def on_match(pk, addr, wif):
            pass

        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=on_match,
            max_workers=1,
            data_logging_enabled=False,
        )
        with patch("src.collision.key_collision_engine.invoke_with_timeout", side_effect=RuntimeError("线程创建失败")):
            result = engine._safe_invoke_match_callback((1).to_bytes(32, "big"), known_addr, "WIF123")
            assert not result, "线程创建失败应返回 False"
        engine.stop()
