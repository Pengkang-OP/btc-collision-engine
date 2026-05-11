#!/usr/bin/env python3
"""引擎启动与主循环 (engine_runner) 单元测试

覆盖：
- _suppress_console_logging / _restore_console_logging 日志抑制
- _compute_range 范围计算
- _print_config_info 配置信息打印
"""

import sys
import logging
import pytest
from unittest.mock import Mock, patch, MagicMock


# ── 模块级测试辅助 ───────────────────────────────────────────────


def _make_mock_engine(is_running_side_effect=None):
    """创建 mock engine，支持控制 is_running 行为。

    参数:
        is_running_side_effect: 若提供则设为 is_running.side_effect，
                               否则 is_running.return_value = False。
    """
    eng = MagicMock()
    if is_running_side_effect is not None:
        eng.is_running.side_effect = is_running_side_effect
    else:
        eng.is_running.return_value = False
    stats = MagicMock()
    stats.total_checked = 10000
    stats.elapsed = 60.0
    stats.start_time = 1000
    stats.matches = []
    eng.get_stats.return_value = stats
    return eng


# ============================================================================
# _suppress_console_logging / _restore_console_logging 测试
# ============================================================================


@pytest.mark.unit
class TestConsoleLogSuppression:
    """控制台日志抑制测试"""

    def test_suppress_raises_stream_handler_level(self):
        """抑制应将 StreamHandler 级别提升到 CRITICAL"""
        from src.cli.engine_runner import _suppress_console_logging, _restore_console_logging
        import src.cli.engine_runner as er

        # 创建一个 StreamHandler 添加到 root logger
        root = logging.getLogger()
        original_handlers = list(root.handlers)
        root.handlers.clear()

        try:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.DEBUG)
            root.addHandler(handler)

            _suppress_console_logging()
            assert handler.level == logging.CRITICAL
            # _suppressed_handlers 应包含被抑制的处理器
            assert len(er._suppressed_handlers) >= 1
        finally:
            _restore_console_logging()
            root.handlers.clear()
            for h in original_handlers:
                root.addHandler(h)

    def test_restore_recovers_original_level(self):
        """恢复应还原原始日志级别"""
        from src.cli.engine_runner import _suppress_console_logging, _restore_console_logging

        root = logging.getLogger()
        original_handlers = list(root.handlers)
        root.handlers.clear()

        try:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.INFO)
            root.addHandler(handler)

            _suppress_console_logging()
            _restore_console_logging()

            assert handler.level == logging.INFO
            from src.cli.engine_runner import _suppressed_handlers

            assert len(_suppressed_handlers) == 0
        finally:
            root.handlers.clear()
            for h in original_handlers:
                root.addHandler(h)

    def test_suppress_skips_file_handlers(self):
        """抑制应跳过 FileHandler"""
        from src.cli.engine_runner import _suppress_console_logging, _restore_console_logging
        from logging import FileHandler

        root = logging.getLogger()
        original_handlers = list(root.handlers)
        root.handlers.clear()

        try:
            # FileHandler 不应被抑制
            fh = FileHandler("nul")
            fh.setLevel(logging.DEBUG)
            root.addHandler(fh)

            _suppress_console_logging()
            # FileHandler 级别不应改变
            assert fh.level == logging.DEBUG
        finally:
            _restore_console_logging()
            fh.close()
            root.handlers.clear()
            for h in original_handlers:
                root.addHandler(h)

    def test_double_suppress_is_safe(self):
        """重复抑制应安全"""
        from src.cli.engine_runner import _suppress_console_logging, _restore_console_logging

        root = logging.getLogger()
        original_handlers = list(root.handlers)
        root.handlers.clear()

        try:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.DEBUG)
            root.addHandler(handler)

            _suppress_console_logging()
            _suppress_console_logging()  # 重复调用

            # 应不崩溃
            assert handler.level == logging.CRITICAL
        finally:
            _restore_console_logging()
            root.handlers.clear()
            for h in original_handlers:
                root.addHandler(h)


# ============================================================================
# _compute_range 测试
# ============================================================================


@pytest.mark.unit
class TestComputeRange:
    """范围计算测试"""

    def test_range_mode_with_both_keys(self):
        from src.cli.engine_runner import _compute_range

        args = Mock()
        args.mode = "range"
        args.start = "1"
        args.end = "FF"
        start_val, end_val, total = _compute_range(args)
        assert start_val == 1
        assert end_val == 255
        assert total == 255

    def test_brute_force_mode_no_end(self):
        from src.cli.engine_runner import _compute_range

        args = Mock()
        args.mode = "brute_force"
        args.start = "A"
        args.end = None
        start_val, end_val, total = _compute_range(args)
        assert start_val == 10
        assert end_val is None
        assert total is None

    def test_random_mode_no_range(self):
        from src.cli.engine_runner import _compute_range

        args = Mock()
        args.mode = "random"
        args.start = None
        args.end = None
        start_val, end_val, total = _compute_range(args)
        assert start_val is None
        assert end_val is None
        assert total is None

    def test_range_mode_no_start(self):
        from src.cli.engine_runner import _compute_range

        args = Mock()
        args.mode = "range"
        args.start = None
        args.end = "FF"
        start_val, end_val, total = _compute_range(args)
        assert start_val is None
        assert end_val == 255
        assert total is None  # 没有 start 无法计算 total

    def test_large_hex_values(self):
        from src.cli.engine_runner import _compute_range

        args = Mock()
        args.mode = "range"
        args.start = "FFFFFFFF"
        args.end = "1FFFFFFFF"
        start_val, end_val, total = _compute_range(args)
        assert start_val == 0xFFFFFFFF
        assert end_val == 0x1FFFFFFFF
        assert total == 0x1FFFFFFFF - 0xFFFFFFFF + 1


# ============================================================================
# _print_config_info 测试
# ============================================================================


@pytest.mark.unit
class TestPrintConfigInfo:
    """配置信息打印测试"""

    def test_cpu_mode_output(self):
        from src.cli.engine_runner import _print_config_info

        args = Mock()
        args.mode = "random"
        args.multi_gpu = False
        args.use_gpu = False
        args.checkpoint = True
        args.dedup = False
        args.duration = 0
        args.workers = 4
        args.no_optimize = False
        args.window_size = 8
        args.no_simd = False
        args.no_memory_pool = False

        with patch("src.cli.engine_runner.CLIOutput") as mock_output_cls:
            mock_output = MagicMock()
            mock_output_cls.get_instance.return_value = mock_output
            _print_config_info(args, {"addr1", "addr2"}, None, None, None)
            # startup_panel 应被调用
            mock_output.startup_panel.assert_called_once()

    def test_gpu_mode_output(self):
        from src.cli.engine_runner import _print_config_info

        args = Mock()
        args.mode = "random"
        args.multi_gpu = False
        args.use_gpu = True
        args.checkpoint = True
        args.dedup = True
        args.duration = 3600
        args.gpu_device = 0
        args.gpu_batch_size = 1000000

        with patch("src.cli.engine_runner.CLIOutput") as mock_output_cls:
            mock_output = MagicMock()
            mock_output_cls.get_instance.return_value = mock_output
            _print_config_info(args, {"addr1"}, None, None, None)
            mock_output.startup_panel.assert_called_once()
            # 验证 panel 内容包含 GPU
            call_args = mock_output.startup_panel.call_args[0][0]
            assert any("GPU" in str(v) for v in call_args.values())

    def test_multi_gpu_mode_output(self):
        from src.cli.engine_runner import _print_config_info

        args = Mock()
        args.mode = "range"
        args.multi_gpu = True
        args.use_gpu = False
        args.checkpoint = False
        args.dedup = False
        args.duration = 7200
        args.gpu_indices = "0 1"
        args.gpu_count = 2

        with patch("src.cli.engine_runner.CLIOutput") as mock_output_cls:
            mock_output = MagicMock()
            mock_output_cls.get_instance.return_value = mock_output
            _print_config_info(args, {"addr1"}, 1, 255, 255)
            mock_output.startup_panel.assert_called_once()

    def test_range_mode_config(self):
        from src.cli.engine_runner import _print_config_info

        args = Mock()
        args.mode = "range"
        args.multi_gpu = False
        args.use_gpu = False
        args.checkpoint = True
        args.dedup = True
        args.duration = 0
        args.workers = 8
        args.no_optimize = True
        args.window_size = 8
        args.no_simd = False
        args.no_memory_pool = False

        with patch("src.cli.engine_runner.CLIOutput") as mock_output_cls:
            mock_output = MagicMock()
            mock_output_cls.get_instance.return_value = mock_output
            _print_config_info(args, {"addr1"}, 0, 100, 101)
            mock_output.startup_panel.assert_called_once()
            # 验证 panel 包含范围信息
            call_args = mock_output.startup_panel.call_args[0][0]
            panel_text = str(call_args)
            assert "101" in panel_text


# ============================================================================
# _setup_and_start_engine 测试
# ============================================================================


@pytest.mark.unit
class TestSetupAndStartEngine:
    """引擎启动测试 — AlertSystem 导入回退、初始化失败、SIGTERM 注册"""

    def test_alert_system_import_fallback_relative(self):
        """AlertSystem 从 src.monitoring 导入失败后尝试相对导入 (L75-79)。"""
        import builtins
        from src.cli.engine_runner import _setup_and_start_engine

        args = Mock()
        args.use_gpu = False
        args.multi_gpu = False
        args.mode = "random"
        args.no_optimize = False
        args.window_size = 8
        args.no_simd = False
        args.no_memory_pool = False
        args.workers = 4
        args.checkpoint = False
        args.checkpoint_interval = 30
        args.dedup = False
        args.dedup_max_size = 1000000
        args.sensitive_mode = "full"

        real_import = builtins.__import__

        def mock_import(name, *a, **kw):
            if 'alert_system' in name:
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *a, **kw)

        with patch("builtins.__import__", side_effect=mock_import):
            with patch("src.cli.engine_runner.build_engine",
                       return_value=(MagicMock(), "cpu")):
                with patch("signal.signal"):
                    with patch("builtins.print"):
                        engine, etype, alert, stop = _setup_and_start_engine(
                            args, {"addr1"}, {}, None, None)
                        assert alert is None

    def test_alert_system_init_exception(self):
        """AlertSystem 构造/设置异常时不崩溃，alert_system 设为 None (L93-95)。"""
        from src.cli.engine_runner import _setup_and_start_engine

        args = Mock()
        args.use_gpu = False
        args.multi_gpu = False
        args.mode = "random"
        args.no_optimize = False
        args.window_size = 8
        args.no_simd = False
        args.no_memory_pool = False
        args.workers = 4
        args.checkpoint = False
        args.checkpoint_interval = 30
        args.dedup = False
        args.dedup_max_size = 1000000
        args.sensitive_mode = "full"

        mock_as_cls = MagicMock(side_effect=RuntimeError("setup failed"))

        with patch("src.cli.engine_runner.build_engine",
                   return_value=(MagicMock(), "cpu")):
            with patch("signal.signal"):
                with patch("builtins.print"):
                    with patch("src.monitoring.alert_system.AlertSystem",
                               mock_as_cls):
                        engine, etype, alert, stop = _setup_and_start_engine(
                            args, {"addr1"}, {}, None, None)
                        assert alert is None

    def test_sigterm_handler_registered(self):
        """SIGTERM 信号处理器注册 (L106-107)。"""
        from src.cli.engine_runner import _setup_and_start_engine
        import signal as _signal

        args = Mock()
        args.use_gpu = False
        args.multi_gpu = False
        args.mode = "random"
        args.no_optimize = False
        args.window_size = 8
        args.no_simd = False
        args.no_memory_pool = False
        args.workers = 4
        args.checkpoint = False
        args.checkpoint_interval = 30
        args.dedup = False
        args.dedup_max_size = 1000000
        args.sensitive_mode = "full"

        sig_calls = []

        def fake_signal(sig, handler):
            sig_calls.append(sig)

        with patch("src.cli.engine_runner.build_engine",
                   return_value=(MagicMock(), "cpu")):
            with patch("signal.signal", fake_signal):
                with patch("builtins.print"):
                    _setup_and_start_engine(args, {"addr1"}, {}, None, None)
                    assert _signal.SIGINT in sig_calls
                    if hasattr(_signal, "SIGTERM"):
                        assert _signal.SIGTERM in sig_calls

    def test_multi_gpu_start_failure_exits(self):
        """多GPU 引擎 start() 返回 False → SystemExit(1) (L122-124)。"""
        from src.cli.engine_runner import _setup_and_start_engine

        args = Mock()
        args.multi_gpu = True
        args.use_gpu = False
        args.mode = "range"
        args.no_optimize = False
        args.window_size = 8
        args.no_simd = False
        args.no_memory_pool = False
        args.workers = 4
        args.checkpoint = False
        args.checkpoint_interval = 30
        args.dedup = False
        args.dedup_max_size = 1000000
        args.sensitive_mode = "full"

        mock_engine = MagicMock()
        mock_engine.start.return_value = False

        with patch("src.cli.engine_runner.build_engine",
                   return_value=(mock_engine, "multi_gpu")):
            with patch("signal.signal"):
                with patch("builtins.print"):
                    with pytest.raises(SystemExit) as ctx:
                        _setup_and_start_engine(
                            args, {"addr1"}, {}, 1, 255)
                    assert ctx.value.code == 1

    def test_single_gpu_engine_start_with_range(self):
        """单GPU引擎 range 模式启动 (L127-132)。"""
        from src.cli.engine_runner import _setup_and_start_engine

        args = Mock()
        args.use_gpu = True
        args.multi_gpu = False
        args.mode = "range"
        args.no_optimize = False
        args.window_size = 8
        args.no_simd = False
        args.no_memory_pool = False
        args.workers = 4
        args.checkpoint = False
        args.checkpoint_interval = 30
        args.dedup = False
        args.dedup_max_size = 1000000
        args.sensitive_mode = "full"

        mock_engine = MagicMock()
        mock_engine.start = MagicMock()

        with patch("src.cli.engine_runner.build_engine",
                   return_value=(mock_engine, "gpu")):
            with patch("signal.signal"):
                with patch("builtins.print"):
                    engine, etype, alert, stop = _setup_and_start_engine(
                        args, {"addr1"}, {}, 10, 100)
                    mock_engine.start.assert_called_once_with(
                        mode="range", start=10, end=100)


# ============================================================================
# _run_collision_loop 内 on_key 回调测试
# ============================================================================


@pytest.mark.unit
class TestOnKeyCallbacks:
    """_run_collision_loop 内 KeyboardListener on_key 回调逻辑测试"""

    def _capture_on_key_callback(self, engine_type="cpu"):
        """调用 _run_collision_loop 并捕获注册的 on_key 回调。"""
        import threading
        from src.cli.engine_runner import _run_collision_loop

        engine = _make_mock_engine()
        stop_event = threading.Event()

        args = Mock()
        args.mode = "random"
        args.duration = 0
        args.progress_interval = 5.0

        with patch("src.cli.keyboard_listener.KeyboardListener") as mock_kl:
            mock_kl_instance = MagicMock()
            mock_kl.return_value = mock_kl_instance
            mock_kl_instance._available = False

            with patch("src.cli.engine_runner.CLIOutput") as mock_co:
                mock_out = MagicMock()
                mock_co.get_instance.return_value = mock_out

                _run_collision_loop(
                    engine, engine_type, args, None, None, stop_event)

                # _available=False → warning 被调用
                mock_out.warning.assert_called_once()

                # 获取注册的回调（KeyboardListener 的第一个位置参数）
                assert mock_kl.called
                return mock_kl.call_args[0][0], engine, stop_event

    def test_on_key_p_pauses_engine(self):
        """按 P 键暂停 → engine.pause() 被调用。"""
        cb, engine, stop_event = self._capture_on_key_callback()
        cb("P")
        assert stop_event.is_set() is False
        engine.pause.assert_called_once()

    def test_on_key_q_stops_engine(self):
        """按 Q 键退出 → stop_event.set() + engine.stop() 被调用。"""
        cb, engine, stop_event = self._capture_on_key_callback()
        cb("Q")
        assert stop_event.is_set()
        engine.stop.assert_called()

    def test_on_key_s_shows_detailed_stats(self):
        """按 S 键显示详细统计 → _print_detailed_stats 被调用。"""
        import threading
        from src.cli.engine_runner import _run_collision_loop

        engine = _make_mock_engine()
        stop_event = threading.Event()

        args = Mock()
        args.mode = "random"
        args.duration = 0
        args.progress_interval = 5.0

        with patch("src.cli.keyboard_listener.KeyboardListener") as mock_kl:
            mock_kl_instance = MagicMock()
            mock_kl.return_value = mock_kl_instance
            mock_kl_instance._available = False

            with patch("src.cli.engine_runner.CLIOutput") as mock_co:
                mock_out = MagicMock()
                mock_co.get_instance.return_value = mock_out

                with patch("src.cli.engine_runner._print_detailed_stats") as mock_pds:
                    _run_collision_loop(
                        engine, "cpu", args, None, None, stop_event)

                    reg_cb = mock_kl.call_args[0][0]
                    reg_cb("S")
                    mock_pds.assert_called_once()

    def test_on_key_s_multi_gpu_shows_stats(self):
        """多GPU模式下按 S 显示统计 → 调用 get_combined_stats。"""
        import threading
        from src.cli.engine_runner import _run_collision_loop

        engine = _make_mock_engine()
        engine.get_combined_stats = MagicMock(return_value={
            "total_keys_checked": 5000, "device_count": 2,
            "total_matches": 1, "elapsed_time": 60
        })
        stop_event = threading.Event()

        args = Mock()
        args.mode = "range"
        args.duration = 0
        args.progress_interval = 5.0

        with patch("src.cli.keyboard_listener.KeyboardListener") as mock_kl:
            mock_kl_instance = MagicMock()
            mock_kl.return_value = mock_kl_instance
            mock_kl_instance._available = False

            with patch("src.cli.engine_runner.CLIOutput") as mock_co:
                mock_out = MagicMock()
                mock_co.get_instance.return_value = mock_out

                _run_collision_loop(
                    engine, "multi_gpu", args, None, None, stop_event)

                reg_cb = mock_kl.call_args[0][0]
                reg_cb("S")
                engine.get_combined_stats.assert_called()

    def test_on_key_pause_resume_cycle(self):
        """暂停后恢复 → engine.resume() 被调用。"""
        cb, engine, stop_event = self._capture_on_key_callback()
        cb("P")
        cb("R")
        engine.resume.assert_called_once()


# ============================================================================
# _print_config_info 多GPU子分支测试
# ============================================================================


@pytest.mark.unit
class TestPrintConfigInfoMultiGPU:
    """_print_config_info 多GPU分支补充"""

    def test_multi_gpu_no_indices_shows_all(self):
        """多GPU模式 gpu_count=-1 无 gpu_indices → 显示 '全部' (L343-344)。"""
        from src.cli.engine_runner import _print_config_info

        args = Mock()
        args.mode = "random"
        args.multi_gpu = True
        args.use_gpu = False
        args.checkpoint = False
        args.dedup = False
        args.duration = 0
        args.gpu_indices = None
        args.gpu_count = -1

        with patch("src.cli.engine_runner.CLIOutput") as mock_co:
            mock_out = MagicMock()
            mock_co.get_instance.return_value = mock_out
            _print_config_info(args, {"addr1"}, 0, 100, 101)
            mock_out.startup_panel.assert_called_once()

    def test_multi_gpu_with_specific_indices(self):
        """多GPU模式有指定 gpu_indices → 显示指定索引 (L339-340)。"""
        from src.cli.engine_runner import _print_config_info

        args = Mock()
        args.mode = "range"
        args.multi_gpu = True
        args.use_gpu = False
        args.checkpoint = False
        args.dedup = False
        args.duration = 0
        args.gpu_indices = [0, 2]
        args.gpu_count = 2

        with patch("src.cli.engine_runner.CLIOutput") as mock_co:
            mock_out = MagicMock()
            mock_co.get_instance.return_value = mock_out
            _print_config_info(args, {"addr1"}, 0, 100, 101)
            call_args = mock_out.startup_panel.call_args[0][0]
            assert any("指定索引" in str(v) for v in call_args.values())

    def test_multi_gpu_with_count_shows_count(self):
        """多GPU模式 gpu_count>0 无 gpu_indices → 显示设备数 (L341-342)。"""
        from src.cli.engine_runner import _print_config_info

        args = Mock()
        args.mode = "range"
        args.multi_gpu = True
        args.use_gpu = False
        args.checkpoint = False
        args.dedup = False
        args.duration = 0
        args.gpu_indices = None
        args.gpu_count = 4

        with patch("src.cli.engine_runner.CLIOutput") as mock_co:
            mock_out = MagicMock()
            mock_co.get_instance.return_value = mock_out
            _print_config_info(args, {"addr1"}, 0, 100, 101)
            call_args = mock_out.startup_panel.call_args[0][0]
            panel_str = str(call_args)
            assert "4" in panel_str

    def test_cpu_mode_no_optimize_disabled(self):
        """CPU 模式 --no-optimize → 优化状态显示 '已禁用' (L362-363)。"""
        from src.cli.engine_runner import _print_config_info

        args = Mock()
        args.mode = "random"
        args.multi_gpu = False
        args.use_gpu = False
        args.checkpoint = True
        args.dedup = False
        args.duration = 0
        args.workers = 4
        args.no_optimize = True
        args.window_size = 8
        args.no_simd = False
        args.no_memory_pool = False

        with patch("src.cli.engine_runner.CLIOutput") as mock_co:
            mock_out = MagicMock()
            mock_co.get_instance.return_value = mock_out
            _print_config_info(args, {"addr1"}, None, None, None)
            call_args = mock_out.startup_panel.call_args[0][0]
            assert any("已禁用" in str(v) for v in call_args.values())


class TestEngineRunnerModuleCoverage:
    """engine_runner.py 模块级代码覆盖测试 (L20)。"""

    def test_sys_path_insert_when_root_not_in_path(self):
        """模块首次加载时 _project_root 不在 sys.path → sys.path.insert (L20)。"""
        import importlib
        import sys

        mod = sys.modules.get("src.cli.engine_runner")
        if mod is None:
            mod = importlib.import_module("src.cli.engine_runner")
        project_root = mod._project_root

        sys.modules.pop("src.cli.engine_runner", None)
        original_path = list(sys.path)
        sys.path = [p for p in sys.path if p != project_root]
        try:
            new_mod = importlib.import_module("src.cli.engine_runner")
            assert new_mod is not None
            assert hasattr(new_mod, "_project_root")
            assert project_root in sys.path  # 验证 L20 insert 已执行
        finally:
            sys.path[:] = original_path
            sys.modules.pop("src.cli.engine_runner", None)
            importlib.import_module("src.cli.engine_runner")


# ============================================================================
# AlertSystem 成功路径 + handle_signal 执行测试
# ============================================================================


@pytest.mark.unit
class TestAlertSystemSuccess:
    """AlertSystem 成功初始化 → _on_alert 回调 + 规则日志 (L86-92)。"""

    def test_alert_system_success_registers_callback(self):
        """AlertSystem 初始化成功 → add_alert_callback 被调用 (L91)。"""
        from src.cli.engine_runner import _setup_and_start_engine

        args = Mock()
        args.use_gpu = False
        args.multi_gpu = False
        args.mode = "random"
        args.no_optimize = False
        args.window_size = 8
        args.no_simd = False
        args.no_memory_pool = False
        args.workers = 4
        args.checkpoint = False
        args.checkpoint_interval = 30
        args.dedup = False
        args.dedup_max_size = 1000000
        args.sensitive_mode = "full"

        mock_as = MagicMock()
        mock_as.rules = [1, 2, 3]

        with patch("src.cli.engine_runner.build_engine",
                   return_value=(MagicMock(), "cpu")):
            with patch("signal.signal"):
                with patch("builtins.print"):
                    with patch("src.monitoring.alert_system.AlertSystem",
                               return_value=mock_as):
                        engine, etype, alert, stop = _setup_and_start_engine(
                            args, {"addr1"}, {}, None, None)
                        assert alert is mock_as
                        mock_as.setup_default_rules.assert_called_once()
                        mock_as.add_alert_callback.assert_called_once()

    def test_on_alert_callback_body(self):
        """_on_alert 回调 → print 警告信息 (L87-89)。"""
        from src.cli.engine_runner import _setup_and_start_engine

        args = Mock()
        args.use_gpu = False
        args.multi_gpu = False
        args.mode = "random"
        args.no_optimize = False
        args.window_size = 8
        args.no_simd = False
        args.no_memory_pool = False
        args.workers = 4
        args.checkpoint = False
        args.checkpoint_interval = 30
        args.dedup = False
        args.dedup_max_size = 1000000
        args.sensitive_mode = "full"

        mock_as = MagicMock()
        mock_as.rules = [1]

        with patch("src.cli.engine_runner.build_engine",
                   return_value=(MagicMock(), "cpu")):
            with patch("signal.signal"):
                with patch("builtins.print") as mock_print:
                    with patch("src.monitoring.alert_system.AlertSystem",
                               return_value=mock_as):
                        _setup_and_start_engine(
                            args, {"addr1"}, {}, None, None)
                        # 提取注册的 _on_alert 回调
                        callback = mock_as.add_alert_callback.call_args[0][0]
                        mock_record = MagicMock()
                        mock_record.level.value = "WARNING"
                        mock_record.message = "alert message"
                        callback(mock_record)
                        mock_print.assert_called()
                        printed = mock_print.call_args[0][0]
                        assert "alert message" in str(printed)

    def test_on_alert_no_level_value_fallback(self):
        """_on_alert 回调 — level 无 .value 属性时使用 str() 回退 (L87)。"""
        from src.cli.engine_runner import _setup_and_start_engine

        args = Mock()
        args.use_gpu = False
        args.multi_gpu = False
        args.mode = "random"
        args.no_optimize = False
        args.window_size = 8
        args.no_simd = False
        args.no_memory_pool = False
        args.workers = 4
        args.checkpoint = False
        args.checkpoint_interval = 30
        args.dedup = False
        args.dedup_max_size = 1000000
        args.sensitive_mode = "full"

        mock_as = MagicMock()
        mock_as.rules = [1]

        with patch("src.cli.engine_runner.build_engine",
                   return_value=(MagicMock(), "cpu")):
            with patch("signal.signal"):
                with patch("builtins.print") as mock_print:
                    with patch("src.monitoring.alert_system.AlertSystem",
                               return_value=mock_as):
                        _setup_and_start_engine(
                            args, {"addr1"}, {}, None, None)
                        callback = mock_as.add_alert_callback.call_args[0][0]
                        mock_record = MagicMock()
                        del mock_record.level.value
                        mock_record.message = "fallback alert"
                        callback(mock_record)
                        mock_print.assert_called()
                        printed = mock_print.call_args[0][0]
                        assert "[WARN]" in str(printed)


@pytest.mark.unit
class TestHandleSignalExecution:
    """信号处理器 handle_signal 函数体执行 (L100-103)。"""

    def _make_args(self):
        args = Mock()
        args.use_gpu = False
        args.multi_gpu = False
        args.mode = "random"
        args.no_optimize = False
        args.window_size = 8
        args.no_simd = False
        args.no_memory_pool = False
        args.workers = 4
        args.checkpoint = False
        args.checkpoint_interval = 30
        args.dedup = False
        args.dedup_max_size = 1000000
        args.sensitive_mode = "full"
        return args

    def test_signal_handler_stops_engine_and_event(self):
        """handle_signal → print + stop_event.set() + engine.stop() (L101-103)。"""
        from src.cli.engine_runner import _setup_and_start_engine
        import signal as _signal

        args = self._make_args()
        mock_engine = MagicMock()
        sig_handlers = {}

        def fake_signal(sig, handler):
            sig_handlers[sig] = handler

        with patch("src.cli.engine_runner.build_engine",
                   return_value=(mock_engine, "cpu")):
            with patch("signal.signal", fake_signal):
                with patch("builtins.print") as mock_print:
                    engine, etype, alert, stop = _setup_and_start_engine(
                        args, {"addr1"}, {}, None, None)
                    handler = sig_handlers[_signal.SIGINT]
                    handler(_signal.SIGINT, None)
                    assert stop.is_set()
                    mock_engine.stop.assert_called()
                    mock_print.assert_called()

    def test_sigterm_handler_also_registered_and_works(self):
        """SIGTERM handler 也注册并可调用 (L106-107)。"""
        from src.cli.engine_runner import _setup_and_start_engine
        import signal as _signal

        args = self._make_args()
        mock_engine = MagicMock()
        sig_handlers = {}

        def fake_signal(sig, handler):
            sig_handlers[sig] = handler

        with patch("src.cli.engine_runner.build_engine",
                   return_value=(mock_engine, "cpu")):
            with patch("signal.signal", fake_signal):
                with patch("builtins.print"):
                    engine, etype, alert, stop = _setup_and_start_engine(
                        args, {"addr1"}, {}, None, None)
                    if hasattr(_signal, "SIGTERM"):
                        assert _signal.SIGTERM in sig_handlers
                        sig_handlers[_signal.SIGTERM](_signal.SIGTERM, None)
                        assert stop.is_set()


# ============================================================================
# on_key S 异常处理 + hotkey_visible 路径测试
# ============================================================================


@pytest.mark.unit
class TestOnKeySException:
    """on_key S 键异常处理 (L188-189)。"""

    def test_on_key_s_cpu_stats_exception(self):
        """按 S 键时 get_stats 抛异常 → except Exception: pass (L188-189)。"""
        import threading
        from src.cli.engine_runner import _run_collision_loop

        engine = _make_mock_engine()
        engine.get_stats.side_effect = RuntimeError("stats error")
        stop_event = threading.Event()

        args = Mock()
        args.mode = "random"
        args.duration = 0
        args.progress_interval = 5.0

        with patch("src.cli.keyboard_listener.KeyboardListener") as mock_kl:
            mock_kl_instance = MagicMock()
            mock_kl.return_value = mock_kl_instance
            mock_kl_instance._available = False

            with patch("src.cli.engine_runner.CLIOutput") as mock_co:
                mock_out = MagicMock()
                mock_co.get_instance.return_value = mock_out

                _run_collision_loop(
                    engine, "cpu", args, None, None, stop_event)

                reg_cb = mock_kl.call_args[0][0]
                # 不应抛异常
                reg_cb("S")

    def test_on_key_s_multi_gpu_stats_exception(self):
        """按 S 键时 get_combined_stats 抛异常 → except Exception: pass。"""
        import threading
        from src.cli.engine_runner import _run_collision_loop

        engine = _make_mock_engine()
        engine.get_combined_stats = MagicMock(
            side_effect=RuntimeError("combined stats error"))
        stop_event = threading.Event()

        args = Mock()
        args.mode = "range"
        args.duration = 0
        args.progress_interval = 5.0

        with patch("src.cli.keyboard_listener.KeyboardListener") as mock_kl:
            mock_kl_instance = MagicMock()
            mock_kl.return_value = mock_kl_instance
            mock_kl_instance._available = False

            with patch("src.cli.engine_runner.CLIOutput") as mock_co:
                mock_out = MagicMock()
                mock_co.get_instance.return_value = mock_out

                _run_collision_loop(
                    engine, "multi_gpu", args, None, None, stop_event)

                reg_cb = mock_kl.call_args[0][0]
                # 不应抛异常
                reg_cb("S")


@pytest.mark.unit
class TestHotkeyVisible:
    """_run_collision_loop 中 KeyboardListener._available=True 路径 (L203)。"""

    def test_hotkey_visible_set_when_available(self):
        """_available=True → _hotkey_visible=True, 不输出 warning (L202-203)。"""
        import threading
        from src.cli.engine_runner import _run_collision_loop

        engine = _make_mock_engine()
        stop_event = threading.Event()

        args = Mock()
        args.mode = "random"
        args.duration = 0
        args.progress_interval = 5.0

        with patch("src.cli.keyboard_listener.KeyboardListener") as mock_kl:
            mock_kl_instance = MagicMock()
            mock_kl.return_value = mock_kl_instance
            mock_kl_instance._available = True

            with patch("src.cli.engine_runner.CLIOutput") as mock_co:
                mock_out = MagicMock()
                mock_co.get_instance.return_value = mock_out

                _run_collision_loop(
                    engine, "cpu", args, None, None, stop_event)

                # _available=True → warning 不应被调用
                mock_out.warning.assert_not_called()


# ============================================================================
# 主循环体 (while loop) 测试 — 覆盖 L209-287
# ============================================================================


@pytest.mark.unit
class TestMainLoopBody:
    """_run_collision_loop 主循环体 while 内部逻辑测试。"""

    def _run_loop_and_get_callback(self, engine, engine_type, args,
                                   alert_system=None, stop_event=None,
                                   _available=False):
        """运行 _run_collision_loop 并返回 on_key 回调。"""
        import threading
        from src.cli.engine_runner import _run_collision_loop

        if stop_event is None:
            stop_event = threading.Event()

        with patch("src.cli.keyboard_listener.KeyboardListener") as mock_kl:
            mock_kl_instance = MagicMock()
            mock_kl.return_value = mock_kl_instance
            mock_kl_instance._available = _available

            with patch("src.cli.engine_runner.CLIOutput") as mock_co:
                mock_out = MagicMock()
                mock_co.get_instance.return_value = mock_out

                with patch("src.cli.engine_runner._suppress_console_logging"):
                    with patch("src.cli.engine_runner._restore_console_logging"):
                        with patch("builtins.print"):
                            _run_collision_loop(
                                engine, engine_type, args,
                                None, alert_system, stop_event)

                reg_cb = mock_kl.call_args[0][0] if mock_kl.called else None
                return reg_cb, mock_out

    # ── CPU 模式主循环迭代 ────────────────────────────────

    def test_single_cpu_iteration_displays_progress(self):
        """单次 CPU 迭代 → format_progress 被调用, 状态行打印 (L245-259)。"""
        import threading

        engine = _make_mock_engine()
        stop_event = threading.Event()

        args = Mock()
        args.mode = "random"
        args.duration = 0
        args.progress_interval = 5.0

        with patch("src.cli.engine_runner.format_progress",
                   return_value="[CPU] progress line") as mock_fp:
            cb, mock_out = self._run_loop_and_get_callback(
                engine, "cpu", args, None, stop_event, _available=False)

            # format_progress 应被调用
            mock_fp.assert_called()

    def test_single_cpu_iteration_with_hotkey_bar(self):
        """单次 CPU 迭代 _available=True → 快捷键栏输出 (L252-257)。"""
        import threading

        engine = _make_mock_engine()
        stop_event = threading.Event()

        args = Mock()
        args.mode = "random"
        args.duration = 0
        args.progress_interval = 5.0

        # _available=True → hotkey bar 路径覆盖，不抛异常即通过
        with patch("src.cli.engine_runner.format_progress",
                   return_value="[CPU] line"):
            cb, mock_out = self._run_loop_and_get_callback(
                engine, "cpu", args, None, stop_event, _available=True)

    # ── 多GPU 模式主循环迭代 ────────────────────────────

    def test_multi_gpu_iteration_displays_combined_stats(self):
        """多GPU 迭代 → get_combined_stats + 状态行 (L220-244)。"""
        import threading

        engine = _make_mock_engine()
        engine.get_combined_stats = MagicMock(return_value={
            "elapsed_time": 120, "total_keys_checked": 2000000,
            "combined_throughput": 1500000, "total_matches": 2,
            "device_count": 2,
        })
        stop_event = threading.Event()

        args = Mock()
        args.mode = "range"
        args.duration = 0
        args.progress_interval = 5.0

        cb, mock_out = self._run_loop_and_get_callback(
            engine, "multi_gpu", args, None, stop_event, _available=False)

        engine.get_combined_stats.assert_called()

    def test_multi_gpu_iteration_small_throughput(self):
        """多GPU 迭代 throughput < 1000 → 显示原始值 (L236-237)。"""
        import threading

        engine = _make_mock_engine()
        engine.get_combined_stats = MagicMock(return_value={
            "elapsed_time": 120, "total_keys_checked": 500,
            "combined_throughput": 500, "total_matches": 0,
            "device_count": 1,
        })
        stop_event = threading.Event()

        args = Mock()
        args.mode = "range"
        args.duration = 0
        args.progress_interval = 5.0

        cb, mock_out = self._run_loop_and_get_callback(
            engine, "multi_gpu", args, None, stop_event, _available=False)
        engine.get_combined_stats.assert_called()

    def test_multi_gpu_iteration_kilo_throughput(self):
        """多GPU 迭代 1000 <= throughput < 1M → K/s 显示 (L234-236)。"""
        import threading

        engine = _make_mock_engine()
        engine.get_combined_stats = MagicMock(return_value={
            "elapsed_time": 120, "total_keys_checked": 50000,
            "combined_throughput": 50000, "total_matches": 0,
            "device_count": 1,
        })
        stop_event = threading.Event()

        args = Mock()
        args.mode = "range"
        args.duration = 0
        args.progress_interval = 5.0

        cb, mock_out = self._run_loop_and_get_callback(
            engine, "multi_gpu", args, None, stop_event, _available=False)
        engine.get_combined_stats.assert_called()

    # ── 暂停状态 ──────────────────────────────────────────

    def test_paused_state_sleeps_and_continues(self):
        """暂停时 → time.sleep(0.2) + continue (L209-211)。"""
        import threading
        from src.cli.engine_runner import _run_collision_loop

        engine = _make_mock_engine([True, True, True, False])
        stop_event = threading.Event()
        cb_holder = []

        args = Mock()
        args.mode = "random"
        args.duration = 0
        args.progress_interval = 0.1

        class TriggerPauseOnSleep:
            def __init__(self, cb_ref):
                self.cb_ref = cb_ref
                self.count = 0

            def __call__(self, secs):
                self.count += 1
                # 第二次 sleep 时触发暂停
                if self.count == 2 and self.cb_ref:
                    self.cb_ref[0]("P")

        def capture_cb(cb):
            cb_holder.append(cb)
            return mock_kl_instance

        with patch("src.cli.keyboard_listener.KeyboardListener") as mock_kl:
            mock_kl_instance = MagicMock()
            mock_kl.return_value = mock_kl_instance
            mock_kl.side_effect = capture_cb
            mock_kl_instance._available = False

            with patch("src.cli.engine_runner.CLIOutput") as mock_co:
                mock_out = MagicMock()
                mock_co.get_instance.return_value = mock_out

                with patch("src.cli.engine_runner._suppress_console_logging"):
                    with patch("src.cli.engine_runner._restore_console_logging"):
                        with patch("builtins.print"):
                            with patch("src.cli.engine_runner.format_progress",
                                       return_value="line"):
                                with patch("time.sleep",
                                           TriggerPauseOnSleep(cb_holder)):
                                    _run_collision_loop(
                                        engine, "cpu", args,
                                        None, None, stop_event)

    # ── 告警系统 metric check ────────────────────────────

    def test_alert_system_metrics_check(self):
        """告警系统检查 → check_metrics 被调用 (L262-273)。"""
        import threading

        engine = _make_mock_engine()
        stop_event = threading.Event()
        mock_alert = MagicMock()

        args = Mock()
        args.mode = "random"
        args.duration = 0
        args.progress_interval = 5.0

        with patch("src.cli.engine_runner.format_progress",
                   return_value="line"):
            cb, mock_out = self._run_loop_and_get_callback(
                engine, "cpu", args, mock_alert, stop_event, _available=False)
            mock_alert.check_metrics.assert_called()

    def test_alert_system_metrics_check_exception(self):
        """告警系统 check_metrics 抛异常 → except Exception: pass (L272-273)。"""
        import threading

        engine = _make_mock_engine()
        stop_event = threading.Event()
        mock_alert = MagicMock()
        mock_alert.check_metrics.side_effect = RuntimeError("check failed")

        args = Mock()
        args.mode = "random"
        args.duration = 0
        args.progress_interval = 5.0

        # 不应抛异常
        with patch("src.cli.engine_runner.format_progress",
                   return_value="line"):
            cb, mock_out = self._run_loop_and_get_callback(
                engine, "cpu", args, mock_alert, stop_event, _available=False)

    # ── 运行时长限制 ─────────────────────────────────────

    def test_duration_limit_reached_stops_engine(self):
        """运行时长达到限制 → engine.stop() + stop_event.set() (L276-282)。"""
        import threading

        engine = _make_mock_engine()
        stop_event = threading.Event()

        args = Mock()
        args.mode = "random"
        args.duration = 1  # 1 秒限制
        args.progress_interval = 5.0

        with patch("src.cli.engine_runner.format_progress",
                   return_value="line"):
            with patch("time.time", side_effect=[0, 99999]):
                cb, mock_out = self._run_loop_and_get_callback(
                    engine, "cpu", args, None, stop_event, _available=False)

        # duration limit reached → engine stopped
        engine.stop.assert_called()
        assert stop_event.is_set()

    # ── KeyboardInterrupt ─────────────────────────────────

    def test_keyboard_interrupt_stops_engine_and_raises(self):
        """KeyboardInterrupt → engine.stop() + raise (L285-287)。"""
        import threading
        from src.cli.engine_runner import _run_collision_loop

        engine = _make_mock_engine([True, False])
        engine.is_running.side_effect = KeyboardInterrupt()
        stop_event = threading.Event()

        args = Mock()
        args.mode = "random"
        args.duration = 0
        args.progress_interval = 5.0

        with patch("src.cli.keyboard_listener.KeyboardListener") as mock_kl:
            mock_kl_instance = MagicMock()
            mock_kl.return_value = mock_kl_instance
            mock_kl_instance._available = False

            with patch("src.cli.engine_runner.CLIOutput") as mock_co:
                mock_out = MagicMock()
                mock_co.get_instance.return_value = mock_out

                with patch("src.cli.engine_runner._suppress_console_logging"):
                    with patch("src.cli.engine_runner._restore_console_logging"):
                        with patch("builtins.print"):
                            with pytest.raises(KeyboardInterrupt):
                                _run_collision_loop(
                                    engine, "cpu", args,
                                    None, None, stop_event)

        engine.stop.assert_called()

    def test_stop_event_checked_during_sleep_breaks(self):
        """sleep 间隔内 stop_event.is_set() → break (L217-218)。"""
        import threading

        engine = _make_mock_engine([True, False])
        stop_event = threading.Event()

        args = Mock()
        args.mode = "random"
        args.duration = 0
        args.progress_interval = 0.01

        def set_stop_during_sleep(*a, **kw):
            stop_event.set()

        with patch("src.cli.engine_runner.format_progress",
                   return_value="line"):
            with patch("time.sleep", side_effect=set_stop_during_sleep):
                cb, mock_out = self._run_loop_and_get_callback(
                    engine, "cpu", args, None, stop_event, _available=False)

        assert stop_event.is_set()
