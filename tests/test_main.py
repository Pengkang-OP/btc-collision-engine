"""CLI 主入口 (src/cli/main.py) 单元测试。

覆盖: _apply_output_flags, _handle_error, load_targets, _run_main, main() 异常路径
目标: 54% → 85%+
"""

import importlib
import logging
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# 直接导入模块 (避免 __init__.py 中 main 函数覆盖模块名)
import src.cli.main  # noqa: E402,F401

main_mod = sys.modules["src.cli.main"]


# ── _apply_output_flags ────────────────────────────────────────

class TestApplyOutputFlags(unittest.TestCase):
    """_apply_output_flags() 测试。"""

    def setUp(self):
        # 保存原始 NO_COLOR 环境变量
        self._orig_no_color = os.environ.pop("NO_COLOR", None)

    def tearDown(self):
        if self._orig_no_color is not None:
            os.environ["NO_COLOR"] = self._orig_no_color
        elif "NO_COLOR" in os.environ:
            del os.environ["NO_COLOR"]

    def _make_args(self, **kwargs):
        defaults = {"verbose": 0, "quiet": False, "no_color": False}
        defaults.update(kwargs)
        return MagicMock(**defaults)

    def test_no_color_sets_env(self):
        """--no-color → 设置 NO_COLOR 环境变量。"""
        args = self._make_args(no_color=True)
        main_mod._apply_output_flags(args)
        self.assertEqual(os.environ.get("NO_COLOR"), "1")

    def test_quiet_sets_warning_level(self):
        """--quiet → root logger 设为 WARNING。"""
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        args = self._make_args(quiet=True)
        main_mod._apply_output_flags(args)
        self.assertEqual(root.level, logging.WARNING)

    def test_verbose_1_sets_debug(self):
        """-v → root logger 设为 DEBUG。"""
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        args = self._make_args(verbose=1)
        main_mod._apply_output_flags(args)
        self.assertEqual(root.level, logging.DEBUG)

    def test_verbose_2_sets_debug(self):
        """-vv → root logger 设为 DEBUG。"""
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        args = self._make_args(verbose=2)
        main_mod._apply_output_flags(args)
        self.assertEqual(root.level, logging.DEBUG)

    def test_verbose_3_sets_debug(self):
        """-vvv → root logger 设为 DEBUG。"""
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        args = self._make_args(verbose=3)
        main_mod._apply_output_flags(args)
        self.assertEqual(root.level, logging.DEBUG)

    def test_quiet_overrides_verbose(self):
        """--quiet --verbose → quiet 优先 (WARNING)。"""
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        args = self._make_args(quiet=True, verbose=3)
        main_mod._apply_output_flags(args)
        self.assertEqual(root.level, logging.WARNING)


# ── load_targets ───────────────────────────────────────────────

class TestLoadTargets(unittest.TestCase):
    """load_targets() 测试 (缺失分支)。"""

    def test_file_validation_failure_exits(self):
        """validate_file_path 返回 False → SystemExit(1)。"""
        args = MagicMock(file="bad_path.txt", targets=None, quiet=False)
        with patch("src.cli.main.validate_file_path", return_value=False):
            with self.assertRaises(SystemExit) as ctx:
                main_mod.load_targets(args)
            self.assertEqual(ctx.exception.code, 1)

    def test_targets_resolve_failure_exits(self):
        """TargetResolver.resolve_multiple 返回空 → SystemExit(1)。"""
        args = MagicMock(file=None, targets=["invalid"], quiet=False)
        # TargetResolver 是 load_targets 内的 lazy import，需 create=True
        with patch("src.cli.main.TargetResolver", create=True) as mock_resolver:
            mock_instance = MagicMock()
            mock_instance.resolve_multiple.return_value = set()
            mock_resolver.return_value = mock_instance
            with self.assertRaises(SystemExit) as ctx:
                main_mod.load_targets(args)
            self.assertEqual(ctx.exception.code, 1)

    def test_file_load_empty_targets_exits(self):
        """load_from_file 返回空集合 → SystemExit(1)。"""
        args = MagicMock(file="empty.txt", targets=None, quiet=False)
        with patch("src.cli.main.validate_file_path", return_value=True):
            with patch("src.cli.main.TargetResolver", create=True) as mock_resolver:
                mock_instance = MagicMock()
                mock_instance.load_from_file.return_value = set()
                mock_resolver.return_value = mock_instance
                with self.assertRaises(SystemExit) as ctx:
                    main_mod.load_targets(args)
                self.assertEqual(ctx.exception.code, 1)

    def test_targets_loaded_prints_count_when_not_quiet(self):
        """args 加载成功 + quiet=False → 打印加载数量。"""
        args = MagicMock(file=None, targets=["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"], quiet=False)
        # TargetResolver 是 load_targets 内的 lazy import，来自 src.collision
        with patch("src.collision.TargetResolver") as mock_resolver:
            mock_instance = MagicMock()
            mock_instance.resolve_multiple.return_value = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
            mock_resolver.return_value = mock_instance
            with patch("builtins.print") as mock_print:
                result = main_mod.load_targets(args)
                self.assertIsInstance(result, set)
                mock_print.assert_called()

    def test_file_targets_loaded_prints_count_when_not_quiet(self):
        """file 加载成功 + quiet=False → 打印加载数量 (L105-106)。"""
        args = MagicMock(file="targets.txt", targets=None, quiet=False)
        with patch("src.cli.main.validate_file_path", return_value=True):
            with patch("src.collision.TargetResolver") as mock_resolver:
                mock_instance = MagicMock()
                mock_instance.load_from_file.return_value = {"addr1", "addr2"}
                mock_resolver.return_value = mock_instance
                with patch("builtins.print") as mock_print:
                    result = main_mod.load_targets(args)
                    self.assertIsInstance(result, set)
                    self.assertEqual(len(result), 2)
                    mock_print.assert_called()


# ── _run_main ──────────────────────────────────────────────────

class TestRunMain(unittest.TestCase):
    """_run_main() 函数测试 — 覆盖主流程各分支。"""

    _ER = "src.cli.engine_runner"

    def setUp(self):
        from src.cli.output import CLIOutput
        CLIOutput.reset_instance()

    def tearDown(self):
        from src.cli.output import CLIOutput
        CLIOutput.reset_instance()

    @staticmethod
    def _make_args(**kwargs):
        defaults = {
            "verbose": 0, "quiet": False, "no_color": False,
            "language": None, "config": None,
            "file": None,
            "targets": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
        }
        defaults.update(kwargs)
        return MagicMock(**defaults)

    @staticmethod
    def _make_engine_tuple():
        engine = MagicMock()
        engine.is_running.return_value = True
        return engine, "cpu", MagicMock(), MagicMock()

    def _enter_base(self, stack, args, config, targets, eng,
                    dispatch_ret=False):
        """进入 _run_main 通用 mock (不含 engine_runner 后续阶段)."""
        stack.enter_context(
            patch.object(main_mod, "parse_args", return_value=args))
        mock_cli = stack.enter_context(patch.object(main_mod, "CLIOutput"))
        mock_cli.init = MagicMock()
        stack.enter_context(patch.object(main_mod, "_apply_output_flags"))
        stack.enter_context(patch.object(
            main_mod, "_dispatch_utility_commands",
            return_value=dispatch_ret))

    def _enter_engine_phase(self, stack, config, targets, eng):
        """进入 _run_main 引擎阶段 mock (validate_args 之后)."""
        stack.enter_context(
            patch.object(main_mod, "validate_args", return_value=True))
        stack.enter_context(patch.object(
            main_mod, "load_config_with_validation", return_value=config))
        stack.enter_context(
            patch.object(main_mod, "load_targets", return_value=targets))
        stack.enter_context(patch(
            self._ER + "._setup_and_start_engine", return_value=eng))
        stack.enter_context(patch(
            self._ER + "._compute_range", return_value=(0, 100, 100)))

    def test_language_set_from_args(self):
        """args.language 非空 → 调用 set_language (L122-123)。"""
        from contextlib import ExitStack
        args = self._make_args(language="en")
        with ExitStack() as stack:
            self._enter_base(stack, args, None, None, None,
                             dispatch_ret=True)
            mock_set_lang = stack.enter_context(
                patch.object(main_mod, "set_language"))
            main_mod._run_main()
            mock_set_lang.assert_called_once_with("en")

    def test_utility_dispatch_early_return(self):
        """_dispatch_utility_commands 返回 True → 提前返回 (L135-136)。"""
        from contextlib import ExitStack
        args = self._make_args()
        with ExitStack() as stack:
            self._enter_base(stack, args, None, None, None,
                             dispatch_ret=True)
            mock_validate = stack.enter_context(
                patch.object(main_mod, "validate_args"))
            main_mod._run_main()
            mock_validate.assert_not_called()

    def test_validation_failure_exits(self):
        """validate_args 返回 False → SystemExit(1) (L139-140)。"""
        from contextlib import ExitStack
        args = self._make_args()
        with ExitStack() as stack:
            self._enter_base(stack, args, None, None, None)
            stack.enter_context(
                patch.object(main_mod, "validate_args", return_value=False))
            with self.assertRaises(SystemExit) as ctx:
                main_mod._run_main()
            self.assertEqual(ctx.exception.code, 1)

    def test_config_none_defaults_to_empty_dict(self):
        """load_config_with_validation 返回 None → config = {} (L145-146)。"""
        from contextlib import ExitStack
        args = self._make_args(quiet=True)
        eng = self._make_engine_tuple()
        with ExitStack() as stack:
            self._enter_base(stack, args, None, {"a"}, eng)
            self._enter_engine_phase(stack, None, {"a"}, eng)
            stack.enter_context(patch(
                self._ER + "._run_collision_loop"))
            stack.enter_context(
                patch.object(main_mod, "_print_final_summary"))
            mock_logger = stack.enter_context(
                patch.object(main_mod, "logger"))
            main_mod._run_main()
            mock_logger.warning.assert_called_once()

    def test_full_flow_quiet(self):
        """完整流程 quiet=True → 跳过 _print_config_info (L163)。"""
        from contextlib import ExitStack
        args = self._make_args(quiet=True)
        eng = self._make_engine_tuple()
        with ExitStack() as stack:
            self._enter_base(stack, args, {"k": "v"}, {"a"}, eng)
            self._enter_engine_phase(stack, {"k": "v"}, {"a"}, eng)
            mock_pci = stack.enter_context(patch(
                self._ER + "._print_config_info"))
            stack.enter_context(patch(
                self._ER + "._run_collision_loop"))
            stack.enter_context(
                patch.object(main_mod, "_print_final_summary"))
            main_mod._run_main()
            mock_pci.assert_not_called()

    def test_full_flow_not_quiet(self):
        """完整流程 quiet=False → 调用 _print_config_info (L163-165)。"""
        from contextlib import ExitStack
        args = self._make_args(quiet=False, verbose=0)
        eng = self._make_engine_tuple()
        with ExitStack() as stack:
            self._enter_base(stack, args, {"k": "v"}, {"a"}, eng)
            self._enter_engine_phase(stack, {"k": "v"}, {"a"}, eng)
            mock_pci = stack.enter_context(patch(
                self._ER + "._print_config_info"))
            stack.enter_context(patch(
                self._ER + "._run_collision_loop"))
            stack.enter_context(
                patch.object(main_mod, "_print_final_summary"))
            main_mod._run_main()
            mock_pci.assert_called_once()

    def test_full_flow_verbose_vv_with_config(self):
        """-vv + config 非空 → 打印 JSON 配置详情 (L166-170)。"""
        from contextlib import ExitStack
        args = self._make_args(verbose=2, quiet=False, config="cfg.json")
        eng = self._make_engine_tuple()
        with ExitStack() as stack:
            self._enter_base(stack, args, {"mode": "r"}, {"a"}, eng)
            self._enter_engine_phase(stack, {"mode": "r"}, {"a"}, eng)
            stack.enter_context(patch(
                self._ER + "._print_config_info"))
            stack.enter_context(patch(
                self._ER + "._run_collision_loop"))
            stack.enter_context(
                patch.object(main_mod, "_print_final_summary"))
            mock_print = stack.enter_context(patch("builtins.print"))
            main_mod._run_main()
            json_printed = any(
                '"mode"' in str(c)
                for c in mock_print.call_args_list)
            self.assertTrue(json_printed)

    def test_engine_stop_and_final_summary_called(self):
        """引擎运行时 → stop() + _print_final_summary 被调用 (L181-186)。"""
        from contextlib import ExitStack
        args = self._make_args(quiet=True)
        engine = MagicMock()
        engine.is_running.return_value = True
        eng = (engine, "cpu", MagicMock(), MagicMock())
        with ExitStack() as stack:
            self._enter_base(stack, args, {"k": "v"}, {"a"}, eng)
            self._enter_engine_phase(stack, {"k": "v"}, {"a"}, eng)
            stack.enter_context(patch(
                self._ER + "._run_collision_loop"))
            mock_fs = stack.enter_context(
                patch.object(main_mod, "_print_final_summary"))
            stack.enter_context(patch("time.sleep"))
            main_mod._run_main()
            engine.stop.assert_called_once()
            mock_fs.assert_called_once()

    def test_engine_already_stopped_skip_stop(self):
        """引擎已停止 → 不重复调用 stop() (L181-182)。"""
        from contextlib import ExitStack
        args = self._make_args(quiet=True)
        engine = MagicMock()
        engine.is_running.return_value = False
        eng = (engine, "cpu", MagicMock(), MagicMock())
        with ExitStack() as stack:
            self._enter_base(stack, args, {"k": "v"}, {"a"}, eng)
            self._enter_engine_phase(stack, {"k": "v"}, {"a"}, eng)
            stack.enter_context(patch(
                self._ER + "._run_collision_loop"))
            stack.enter_context(
                patch.object(main_mod, "_print_final_summary"))
            stack.enter_context(patch("time.sleep"))
            main_mod._run_main()
            engine.stop.assert_not_called()


class TestHandleError(unittest.TestCase):
    """_handle_error() 测试 — 所有异常类型分支。"""

    def setUp(self):
        from src.cli.output import CLIOutput
        CLIOutput.reset_instance()

    def tearDown(self):
        from src.cli.output import CLIOutput
        CLIOutput.reset_instance()

    def test_file_not_found_error(self):
        """FileNotFoundError → 输出文件未找到提示。"""
        with patch.object(main_mod, "CLIOutput") as mock_cls:
            mock_out = MagicMock()
            mock_cls.get_instance.return_value = mock_out
            main_mod._handle_error(FileNotFoundError("test.txt"))
            mock_out.error.assert_called_once()
            self.assertIn("文件未找到", mock_out.error.call_args[0][0])

    def test_permission_error(self):
        """PermissionError → 输出权限不足提示。"""
        with patch.object(main_mod, "CLIOutput") as mock_cls:
            mock_out = MagicMock()
            mock_cls.get_instance.return_value = mock_out
            main_mod._handle_error(PermissionError("access denied"))
            mock_out.error.assert_called_once()
            self.assertIn("权限不足", mock_out.error.call_args[0][0])

    def test_memory_error(self):
        """MemoryError → 输出内存不足提示。"""
        with patch.object(main_mod, "CLIOutput") as mock_cls:
            mock_out = MagicMock()
            mock_cls.get_instance.return_value = mock_out
            main_mod._handle_error(MemoryError("oom"))
            mock_out.error.assert_called_once()
            self.assertIn("内存不足", mock_out.error.call_args[0][0])

    def test_import_error(self):
        """ImportError → 输出缺少依赖提示。"""
        with patch.object(main_mod, "CLIOutput") as mock_cls:
            mock_out = MagicMock()
            mock_cls.get_instance.return_value = mock_out
            main_mod._handle_error(ImportError("numpy not found"))
            mock_out.error.assert_called_once()
            self.assertIn("缺少依赖", mock_out.error.call_args[0][0])

    def test_value_error(self):
        """ValueError → 输出参数错误提示。"""
        with patch.object(main_mod, "CLIOutput") as mock_cls:
            mock_out = MagicMock()
            mock_cls.get_instance.return_value = mock_out
            main_mod._handle_error(ValueError("invalid value"))
            mock_out.error.assert_called_once()
            self.assertIn("参数错误", mock_out.error.call_args[0][0])

    def test_type_error(self):
        """TypeError → 输出参数错误提示。"""
        with patch.object(main_mod, "CLIOutput") as mock_cls:
            mock_out = MagicMock()
            mock_cls.get_instance.return_value = mock_out
            main_mod._handle_error(TypeError("type mismatch"))
            mock_out.error.assert_called_once()
            self.assertIn("参数错误", mock_out.error.call_args[0][0])

    def test_os_error(self):
        """OSError → 输出系统错误提示。"""
        with patch.object(main_mod, "CLIOutput") as mock_cls:
            mock_out = MagicMock()
            mock_cls.get_instance.return_value = mock_out
            main_mod._handle_error(OSError("disk error"))
            mock_out.error.assert_called_once()
            self.assertIn("系统错误", mock_out.error.call_args[0][0])

    def test_generic_exception(self):
        """其他异常 → 输出运行时错误 + 日志路径。"""
        with patch.object(main_mod, "CLIOutput") as mock_cls:
            mock_out = MagicMock()
            mock_cls.get_instance.return_value = mock_out
            main_mod._handle_error(KeyError("missing key"))
            mock_out.error.assert_called_once()
            self.assertIn("运行时错误", mock_out.error.call_args[0][0])

    def test_logs_exception_stack(self):
        """所有异常 → logger.exception 记录完整堆栈。"""
        with patch.object(main_mod, "CLIOutput") as mock_cls:
            with patch.object(main_mod, "logger") as mock_logger:
                mock_out = MagicMock()
                mock_cls.get_instance.return_value = mock_out
                main_mod._handle_error(RuntimeError("test"))
                mock_logger.exception.assert_called_once()


# ── main() 异常路径 ────────────────────────────────────────────

class TestMainErrorHandling(unittest.TestCase):
    """main() 入口异常处理分支测试。"""

    def setUp(self):
        from src.cli.output import CLIOutput
        CLIOutput.reset_instance()

    def tearDown(self):
        from src.cli.output import CLIOutput
        CLIOutput.reset_instance()

    def test_keyboard_interrupt_exits_130(self):
        """Ctrl+C → SystemExit(130)。"""
        with patch.object(main_mod, "_run_main", side_effect=KeyboardInterrupt):
            with patch("builtins.print"):
                with self.assertRaises(SystemExit) as ctx:
                    main_mod.main()
                self.assertEqual(ctx.exception.code, 130)

    def test_system_exit_passthrough(self):
        """SystemExit(42) → 透传 SystemExit(42)。"""
        with patch.object(main_mod, "_run_main", side_effect=SystemExit(42)):
            with self.assertRaises(SystemExit) as ctx:
                main_mod.main()
            self.assertEqual(ctx.exception.code, 42)

    def test_generic_exception_handles_and_exits(self):
        """运行异常 → _handle_error → SystemExit(1)。"""
        with patch.object(main_mod, "_run_main", side_effect=RuntimeError("boom")):
            with patch.object(main_mod, "_handle_error") as mock_handler:
                with self.assertRaises(SystemExit) as ctx:
                    main_mod.main()
                self.assertEqual(ctx.exception.code, 1)
                mock_handler.assert_called_once()


# ── 模块级启动行为 ────────────────────────────────────────────

class TestModuleStartup(unittest.TestCase):
    """模块导入时的 sys.path 操作 + main() 启动异常路径。"""

    def test_project_root_added_to_sys_path(self):
        """项目根不在 sys.path 时自动插入 (L29)。"""
        # 计算 main.py 所在的项目根
        main_file = main_mod.__file__
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(main_file))))
        # 确保项目根已在 path 中 (正常情况下已存在)
        self.assertIn(project_root, sys.path)
        # 移除后重新加载，验证自动补回
        saved_path = list(sys.path)
        try:
            while project_root in sys.path:
                sys.path.remove(project_root)
            # 清理模块缓存
            mod_keys = [k for k in list(sys.modules.keys())
                        if k == "src.cli.main" or k.startswith("src.cli.main.")]
            saved_mods = {k: sys.modules.pop(k, None) for k in mod_keys}
            try:
                # 放回 main_mod 以便 reload 能找到
                sys.modules["src.cli.main"] = main_mod
                importlib.reload(main_mod)
                self.assertIn(project_root, sys.path)
            finally:
                for k, v in saved_mods.items():
                    if v is not None:
                        sys.modules[k] = v
        finally:
            sys.path[:] = saved_path

    def test_stdout_reconfigure_exception_handled(self):
        """sys.stdout.reconfigure 抛异常 → 静默忽略 (L227-228)。"""
        with patch.object(main_mod, "_run_main"):
            with patch.object(
                sys.stdout, "reconfigure", side_effect=OSError("bad fd")
            ) as mock_rec:
                # 不应抛出异常
                try:
                    main_mod.main()
                except Exception as e:
                    self.fail(
                        f"main() should not raise on reconfigure error: {e}"
                    )
                mock_rec.assert_called()  # 确认 except 路径被执行


if __name__ == "__main__":
    unittest.main()
