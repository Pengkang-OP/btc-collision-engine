"""引擎启动与主循环 (engine_runner) 单元测试 — 对齐 src/cli/engine_runner.py 真实 API

注意:
- _setup_and_start_engine 在函数内做相对导入，patch 路径必须对应实际模块
- _run_collision_loop 内懒加载 format_progress，patch 路径为 src.cli.progress
"""

import threading
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.cli.engine_runner import (
    _compute_range,
    _print_config_info,
)


# ============================================================================
# _compute_range 测试
# ============================================================================


@pytest.mark.unit
class TestComputeRange:
    """范围计算测试"""

    def test_random_mode_returns_none(self):
        args = Mock(mode="random")
        start_val, end_val, total = _compute_range(args)
        assert start_val is None
        assert end_val is None
        assert total is None

    def test_range_mode_with_start_end(self):
        args = Mock(mode="range", start="1", end="FF")
        start_val, end_val, total = _compute_range(args)
        assert start_val == "1"
        assert end_val == "FF"
        assert total == 0xFF - 0x1 + 1

    def test_range_mode_no_start(self):
        args = Mock(mode="range", start=None, end="FF")
        start_val, end_val, total = _compute_range(args)
        assert start_val is None
        assert end_val == "FF"
        assert total is None

    def test_range_mode_no_end(self):
        args = Mock(mode="range", start="A", end=None)
        start_val, end_val, total = _compute_range(args)
        assert start_val == "A"
        assert end_val is None
        assert total is None

    def test_invalid_hex_total_is_none(self):
        args = Mock(mode="range", start="NOT_HEX", end="FF")
        start_val, end_val, total = _compute_range(args)
        assert total is None

    def test_large_hex_values(self):
        args = Mock(mode="range", start="FFFFFFFF", end="1FFFFFFFF")
        start_val, end_val, total = _compute_range(args)
        assert start_val == "FFFFFFFF"
        assert end_val == "1FFFFFFFF"
        assert total == 0x1FFFFFFFF - 0xFFFFFFFF + 1


# ============================================================================
# _print_config_info 测试
# ============================================================================


@pytest.mark.unit
class TestPrintConfigInfo:
    """配置信息打印测试 — 使用 print() 非 CLIOutput"""

    def test_random_mode_output(self, capsys):
        args = Mock(mode="random", use_gpu=False, checkpoint=False, dedup=False,
                    workers="auto", duration=None)
        _print_config_info(args, {"addr1", "addr2"}, None, None, None)
        captured = capsys.readouterr().out
        assert "random" in captured

    def test_range_mode_with_range(self, capsys):
        args = Mock(mode="range", use_gpu=False, checkpoint=True, dedup=False,
                    workers=4, duration=None)
        _print_config_info(args, {"addr1"}, "0", "FF", 256)
        captured = capsys.readouterr().out
        assert "range" in captured

    def test_gpu_mode(self, capsys):
        args = Mock(mode="random", use_gpu=True, checkpoint=False, dedup=False,
                    workers="auto", duration=None)
        _print_config_info(args, {"addr1"}, None, None, None)
        captured = capsys.readouterr().out
        assert "random" in captured

    def test_duration_output(self, capsys):
        args = Mock(mode="random", use_gpu=False, checkpoint=False, dedup=False,
                    workers="auto", duration=3600)
        _print_config_info(args, {"addr1"}, None, None, None)
        captured = capsys.readouterr().out
        assert "3600" in captured


# ============================================================================
# _setup_and_start_engine 测试
# 注意：此函数做实际导入和引擎实例化，需要 patch 正确的模块路径
# ============================================================================


@pytest.mark.unit
class TestSetupAndStartEngine:
    """引擎启动测试 — patch 实际导入路径"""

    def test_cpu_engine_created(self):
        from src.cli.engine_runner import _setup_and_start_engine

        args = Mock(use_gpu=False, mode="random", checkpoint=False, dedup=False)

        mock_engine = MagicMock()
        mock_as = MagicMock()

        with (
            patch("src.collision.key_collision_engine.KeyCollisionEngine", return_value=mock_engine),
            patch("src.cli.engine_runner.AlertSystem", return_value=mock_as),
            patch("signal.signal"),
        ):
            engine, engine_type, alert_system, stop_event = _setup_and_start_engine(
                args, {"addr1"}, {}, None, None,
            )

            assert engine_type == "CPU"
            assert engine is mock_engine
            assert alert_system is mock_as
            assert stop_event is not None

    def test_gpu_engine_created(self):
        from src.cli.engine_runner import _setup_and_start_engine

        args = Mock(use_gpu=True, mode="random", checkpoint=False, dedup=False)

        mock_engine = MagicMock()
        mock_as = MagicMock()

        with (
            patch("src.gpu.facade.GPUFacade", return_value=mock_engine),
            patch("src.cli.engine_runner.AlertSystem", return_value=mock_as),
            patch("signal.signal"),
        ):
            engine, engine_type, _, _ = _setup_and_start_engine(
                args, {"addr1"}, {"gpu": True}, None, None,
            )

            assert engine_type == "GPU"
            assert engine is mock_engine

    def test_alert_system_initialized(self):
        from src.cli.engine_runner import _setup_and_start_engine

        args = Mock(use_gpu=False, mode="random", checkpoint=False, dedup=False)

        mock_engine = MagicMock()
        mock_as = MagicMock()

        with (
            patch("src.collision.key_collision_engine.KeyCollisionEngine", return_value=mock_engine),
            patch("src.cli.engine_runner.AlertSystem", return_value=mock_as),
            patch("signal.signal"),
        ):
            _setup_and_start_engine(args, {"addr1"}, {}, None, None)
            mock_as.setup_default_rules.assert_called_once()

    def test_stop_event_is_threading_event(self):
        import threading
        from src.cli.engine_runner import _setup_and_start_engine

        args = Mock(use_gpu=False, mode="random", checkpoint=False, dedup=False)

        mock_engine = MagicMock()
        mock_as = MagicMock()

        with (
            patch("src.collision.key_collision_engine.KeyCollisionEngine", return_value=mock_engine),
            patch("src.cli.engine_runner.AlertSystem", return_value=mock_as),
            patch("signal.signal"),
        ):
            _, _, _, stop_event = _setup_and_start_engine(
                args, {"addr1"}, {}, None, None,
            )
            assert isinstance(stop_event, threading.Event)

    def test_signal_handlers_registered(self):
        import signal as _signal
        from src.cli.engine_runner import _setup_and_start_engine

        args = Mock(use_gpu=False, mode="random", checkpoint=False, dedup=False)
        sig_calls = []

        def fake_signal(sig, handler):
            sig_calls.append(sig)

        mock_engine = MagicMock()
        mock_as = MagicMock()

        with (
            patch("src.collision.key_collision_engine.KeyCollisionEngine", return_value=mock_engine),
            patch("src.cli.engine_runner.AlertSystem", return_value=mock_as),
            patch("signal.signal", fake_signal),
        ):
            _setup_and_start_engine(args, {"addr1"}, {}, None, None)
            assert _signal.SIGINT in sig_calls
            assert _signal.SIGTERM in sig_calls


# ============================================================================
# _run_collision_loop 测试
# ============================================================================


@pytest.mark.unit
class TestRunCollisionLoop:
    """主循环测试"""

    def _make_mock_engine(self, is_running_side_effect=None):
        eng = MagicMock()
        if is_running_side_effect is not None:
            eng.is_running.side_effect = is_running_side_effect
        else:
            eng.is_running.return_value = False
        stats = MagicMock()
        stats.get.return_value = 0
        eng.get_stats.return_value = stats
        return eng

    def test_loop_exits_when_engine_not_running(self):
        from src.cli.engine_runner import _run_collision_loop

        engine = self._make_mock_engine()
        args = Mock(duration=None, mode="random")

        with (
            patch("src.cli.progress.format_progress", return_value=""),
            patch("src.cli.engine_runner.time.sleep"),
        ):
            _run_collision_loop(engine, "CPU", args, None, None, threading.Event())

        engine.is_running.assert_called()

    def test_loop_shows_progress(self):
        from src.cli.engine_runner import _run_collision_loop

        engine = self._make_mock_engine([True, False])
        stats = MagicMock()
        stats.get.side_effect = lambda k, d=0: {"total_checked": 1000, "speed": 500, "matches_found": 0}.get(k, d)
        engine.get_stats.return_value = stats

        args = Mock(duration=None, mode="random")

        with (
            patch("src.cli.progress.format_progress", return_value="[CPU] progress"),
            patch("src.cli.engine_runner.time.sleep"),
        ):
            _run_collision_loop(engine, "CPU", args, None, None, threading.Event())

        engine.get_stats.assert_called()

    def test_duration_limit_stops_engine(self):
        from src.cli.engine_runner import _run_collision_loop

        engine = self._make_mock_engine([True])
        args = Mock(duration=1, mode="random")

        # engine_runner 内 import time，需 patch 模块级引用
        with (
            patch("src.cli.progress.format_progress", return_value=""),
            patch("src.cli.engine_runner.time.sleep"),
            patch("src.cli.engine_runner.time.time", side_effect=[0, 99999]),
        ):
            _run_collision_loop(engine, "CPU", args, None, None, threading.Event())

        engine.stop.assert_called()

    def test_keyboard_interrupt_stops_engine(self):
        from src.cli.engine_runner import _run_collision_loop

        engine = self._make_mock_engine()
        engine.is_running.side_effect = KeyboardInterrupt()

        args = Mock(duration=None, mode="random")

        with (
            patch("src.cli.progress.format_progress", return_value=""),
            patch("src.cli.engine_runner.time.sleep"),
        ):
            # KeyboardInterrupt 被源码 try/except 捕获，函数正常返回
            _run_collision_loop(engine, "CPU", args, None, None, threading.Event())

        engine.stop.assert_called()

    def test_progress_exception_non_fatal(self):
        from src.cli.engine_runner import _run_collision_loop

        engine = self._make_mock_engine([True, False])
        engine.get_stats.side_effect = RuntimeError("stats error")

        args = Mock(duration=None, mode="random")

        with patch("src.cli.engine_runner.time.sleep"):
            _run_collision_loop(engine, "CPU", args, None, None, threading.Event())

        # 不应抛异常
