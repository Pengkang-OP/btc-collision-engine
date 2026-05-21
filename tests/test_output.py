"""CLI 输出管理器 (src/cli/output.py) 单元测试。"""

import io
import os
import unittest
from unittest.mock import MagicMock, patch

from src.cli.output import CLIOutput, _get_utf8_console

# ── _get_utf8_console ──────────────────────────────────────────


class TestGetUtf8Console(unittest.TestCase):
    """_get_utf8_console() 端到端测试。"""

    @patch("platform.system", return_value="Linux")
    def test_non_windows_returns_default_console(self, mock_system):
        """非 Windows → 默认 Console (stderr kwarg)。"""
        c = _get_utf8_console(stderr=True)
        self.assertIsNotNone(c)

    @patch("platform.system", return_value="Linux")
    def test_non_windows_no_color(self, mock_system):
        """非 Windows + no_color=True → 默认 Console 带 no_color。"""
        c = _get_utf8_console(no_color=True)
        self.assertIsNotNone(c)

    @patch("platform.system", return_value="Windows")
    def test_windows_reconfigure_success(self, mock_system):
        """Windows + reconfigure 成功 → force_terminal Console。"""
        with patch("sys.stdout.reconfigure") as mock_rec:
            c = _get_utf8_console(stderr=False, no_color=True)
            self.assertIsNotNone(c)
            mock_rec.assert_called_once()

    @patch("platform.system", return_value="Windows")
    def test_windows_stderr_reconfigure(self, mock_system):
        """Windows + stderr=True → 重配 stderr。"""
        with patch("sys.stderr.reconfigure") as mock_rec:
            c = _get_utf8_console(stderr=True)
            self.assertIsNotNone(c)
            mock_rec.assert_called_once()

    @patch("platform.system", return_value="Windows")
    def test_windows_no_reconfigure_fallback_to_default(self, mock_system):
        """Windows 但无 reconfigure (Python<3.7) → 默认 Console。"""
        with patch("sys.stdout", spec=[]):  # 无 reconfigure 属性
            c = _get_utf8_console(stderr=False)
            self.assertIsNotNone(c)

    @patch("platform.system", return_value="Windows")
    def test_windows_reconfigure_oserror_fallback(self, mock_system):
        """Windows + reconfigure 抛出 OSError → 静默降级到默认 Console。"""
        mock_stdout = MagicMock()
        mock_stdout.reconfigure = MagicMock(side_effect=OSError("mock"))
        with patch("sys.stdout", mock_stdout):
            c = _get_utf8_console(stderr=False)
            self.assertIsNotNone(c)

    @patch("platform.system", return_value="Windows")
    def test_windows_reconfigure_attribute_error_fallback(self, mock_system):
        """Windows + reconfigure 调用时抛出 AttributeError → 降级。"""
        mock_stdout = MagicMock()
        mock_stdout.reconfigure = MagicMock(side_effect=AttributeError("mock"))
        with patch("sys.stdout", mock_stdout):
            c = _get_utf8_console(stderr=False)
            self.assertIsNotNone(c)

    @patch("platform.system", return_value="Windows")
    def test_windows_reconfigure_io_unsupported_operation_fallback(self, mock_system):
        """Windows + reconfigure → io.UnsupportedOperation → 降级。"""
        mock_stdout = MagicMock()
        mock_stdout.reconfigure = MagicMock(side_effect=io.UnsupportedOperation("mock"))
        with patch("sys.stdout", mock_stdout):
            c = _get_utf8_console(stderr=False)
            self.assertIsNotNone(c)


# ── CLIOutput 单例管理 ─────────────────────────────────────────


class TestCLIOutputSingleton(unittest.TestCase):
    """get_instance / init / reset_instance 测试。"""

    def tearDown(self):
        CLIOutput.reset_instance()

    def test_get_instance_creates_lazily(self):
        """首次 get_instance → 创建默认实例。"""
        out = CLIOutput.get_instance()
        self.assertIsInstance(out, CLIOutput)

    def test_get_instance_returns_same(self):
        """二次 get_instance → 同一实例。"""
        a = CLIOutput.get_instance()
        b = CLIOutput.get_instance()
        self.assertIs(a, b)

    def test_init_resets_instance(self):
        """init() → 替换为新实例。"""
        old = CLIOutput.get_instance()
        new = CLIOutput.init(quiet=True, compact=True)
        self.assertIsNot(old, new)
        self.assertTrue(new.quiet)
        self.assertTrue(new.compact)

    def test_reset_instance_clears(self):
        """reset_instance → get_instance 创建全新实例。"""
        old = CLIOutput.get_instance()
        CLIOutput.reset_instance()
        new = CLIOutput.get_instance()
        self.assertIsNot(old, new)


# ── CLIOutput 初始化 ───────────────────────────────────────────


class TestCLIOutputInit(unittest.TestCase):
    """__init__ 参数测试。"""

    def setUp(self):
        # 每次测试前重置单例，避免污染
        CLIOutput.reset_instance()

    def tearDown(self):
        CLIOutput.reset_instance()

    @patch("platform.system", return_value="Linux")
    def test_defaults(self, mock_system):
        """默认参数 → quiet=False, compact=False, no_color 从环境变量。"""
        with patch.dict(os.environ, {}, clear=True):
            out = CLIOutput()
            self.assertFalse(out.quiet)
            self.assertFalse(out.compact)
            self.assertIsNotNone(out.console)
            self.assertIsNotNone(out.err_console)

    @patch("platform.system", return_value="Linux")
    def test_no_color_flag(self, mock_system):
        """no_color=True → 禁用颜色，传递给 Console。"""
        with patch.dict(os.environ, {}, clear=True):
            out = CLIOutput(no_color=True)
            self.assertTrue(out.console.no_color)
            self.assertTrue(out.err_console.no_color)

    @patch("platform.system", return_value="Linux")
    def test_no_color_env_var(self, mock_system):
        """NO_COLOR 环境变量 → 强制禁用颜色 (即使 no_color=False)。"""
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            out = CLIOutput(no_color=False)
            self.assertTrue(out.console.no_color)
            self.assertTrue(out.err_console.no_color)

    @patch("platform.system", return_value="Linux")
    def test_quiet_mode(self, mock_system):
        """quiet=True → 实例记录 but 不影响 console 创建。"""
        out = CLIOutput(quiet=True)
        self.assertTrue(out.quiet)

    @patch("platform.system", return_value="Linux")
    def test_compact_mode(self, mock_system):
        """compact=True。"""
        out = CLIOutput(compact=True)
        self.assertTrue(out.compact)


# ── CLIOutput 消息输出 ─────────────────────────────────────────


class TestCLIOutputMessages(unittest.TestCase):
    """info / success / hint / warning / error / print 测试。"""

    def setUp(self):
        CLIOutput.reset_instance()
        self.out = CLIOutput()
        # Mock 底层 console 和 err_console
        self.out.console = MagicMock()
        self.out.err_console = MagicMock()

    def tearDown(self):
        CLIOutput.reset_instance()

    # ── info ──

    def test_info_suppressed_when_quiet(self):
        """info + quiet=True → 不输出。"""
        self.out.quiet = True
        self.out.info("test")
        self.out.console.print.assert_not_called()

    def test_info_output_when_not_quiet(self):
        """info + quiet=False → 蓝色 [INFO]。"""
        self.out.quiet = False
        self.out.info("hello")
        self.out.console.print.assert_called_once()
        call_arg = self.out.console.print.call_args[0][0]
        self.assertIn("[INFO]", call_arg)
        self.assertIn("hello", call_arg)

    # ── success ──

    def test_success_always_displays(self):
        """success → 始终输出绿色 [OK]。"""
        self.out.success("done")
        self.out.console.print.assert_called_once()
        call_arg = self.out.console.print.call_args[0][0]
        self.assertIn("[OK]", call_arg)
        self.assertIn("done", call_arg)

    def test_success_even_in_quiet(self):
        """success + quiet → 仍输出。"""
        self.out.quiet = True
        self.out.success("done")
        self.out.console.print.assert_called_once()

    # ── hint ──

    def test_hint_always_displays(self):
        """hint → 始终输出蓝色 [HINT]。"""
        self.out.hint("tip")
        self.out.console.print.assert_called_once()
        call_arg = self.out.console.print.call_args[0][0]
        self.assertIn("[HINT]", call_arg)

    def test_hint_even_in_quiet(self):
        """hint + quiet → 仍输出。"""
        self.out.quiet = True
        self.out.hint("tip")
        self.out.console.print.assert_called_once()

    # ── warning ──

    def test_warning_without_details(self):
        """warning 无 details → 只输出 [WARN] 到 stderr。"""
        self.out.warning("caution")
        self.out.err_console.print.assert_called_once()
        call_arg = self.out.err_console.print.call_args[0][0]
        self.assertIn("[WARN]", call_arg)
        self.assertIn("caution", call_arg)

    def test_warning_with_details(self):
        """warning 有 details → 追加详细行。"""
        self.out.warning("caution", details="extra info")
        self.assertEqual(self.out.err_console.print.call_count, 2)
        second_call_arg = self.out.err_console.print.call_args_list[1][0][0]
        self.assertIn("extra info", second_call_arg)

    # ── error ──

    def test_error_without_details(self):
        """error 无 details → 只输出 [ERROR] 到 stderr。"""
        self.out.error("fail")
        self.out.err_console.print.assert_called_once()
        call_arg = self.out.err_console.print.call_args[0][0]
        self.assertIn("[ERROR]", call_arg)
        self.assertIn("fail", call_arg)

    def test_error_with_details(self):
        """error 有 details → 追加详细行。"""
        self.out.error("fail", details="stack trace")
        self.assertEqual(self.out.err_console.print.call_count, 2)
        second_call_arg = self.out.err_console.print.call_args_list[1][0][0]
        self.assertIn("stack trace", second_call_arg)

    # ── print ──

    def test_print_suppressed_when_quiet(self):
        """print + quiet=True → 不输出。"""
        self.out.quiet = True
        self.out.print("hidden")
        self.out.console.print.assert_not_called()

    def test_print_output_when_not_quiet(self):
        """print + quiet=False → 输出。"""
        self.out.quiet = False
        self.out.print("visible")
        self.out.console.print.assert_called_once_with("visible")

    def test_print_empty_message(self):
        """print 空消息 → 输出空字符串。"""
        self.out.quiet = False
        self.out.print()
        self.out.console.print.assert_called_once_with("")

    # ── print_always ──

    def test_print_always_ignores_quiet(self):
        """print_always + quiet=True → 仍输出。"""
        self.out.quiet = True
        self.out.print_always("always")
        self.out.console.print.assert_called_once_with("always")

    def test_print_always_passes_kwargs(self):
        """print_always 传递 kwargs。"""
        self.out.print_always("styled", style="bold")
        self.out.console.print.assert_called_once_with("styled", style="bold")


# ── CLIOutput 结构化输出 ───────────────────────────────────────


class TestCLIOutputStructured(unittest.TestCase):
    """rule / header / startup_panel / final_summary / stats_panel 测试。"""

    def setUp(self):
        CLIOutput.reset_instance()
        self.out = CLIOutput()
        self.out.console = MagicMock()
        self.out.err_console = MagicMock()

    def tearDown(self):
        CLIOutput.reset_instance()

    # ── rule ──

    def test_rule_suppressed_when_quiet(self):
        """rule + quiet=True → 不输出。"""
        self.out.quiet = True
        self.out.rule("section")
        self.out.console.rule.assert_not_called()

    def test_rule_output_when_not_quiet(self):
        """rule + quiet=False → 调用 console.rule。"""
        self.out.quiet = False
        self.out.rule("section", style="bold")
        self.out.console.rule.assert_called_once_with("section", style="bold")

    def test_rule_empty_title(self):
        """rule 空标题 → 正常传递。"""
        self.out.quiet = False
        self.out.rule()
        self.out.console.rule.assert_called_once_with("", style="dim")

    # ── header ──

    def test_header_suppressed_when_quiet(self):
        """header + quiet=True → 不输出。"""
        self.out.quiet = True
        self.out.header("Title")
        self.out.console.print.assert_not_called()
        self.out.console.rule.assert_not_called()

    def test_header_normal_mode(self):
        """header + compact=False → 先空行，再 rule，再空行。"""
        self.out.quiet = False
        self.out.compact = False
        self.out.header("Title")
        # print() 调用次数 ≥ 2 (空行 + 空行)
        self.assertEqual(self.out.console.print.call_count, 2)
        self.out.console.rule.assert_called_once()

    def test_header_compact_mode(self):
        """header + compact=True → 无空行。"""
        self.out.quiet = False
        self.out.compact = True
        self.out.header("Title")
        self.out.console.print.assert_not_called()
        self.out.console.rule.assert_called_once()

    # ── startup_panel ──

    def test_startup_panel_suppressed_when_quiet(self):
        """startup_panel + quiet=True → 不输出。"""
        self.out.quiet = True
        self.out.startup_panel({"key": "value"})
        self.out.console.print.assert_not_called()

    def test_startup_panel_output_when_not_quiet(self):
        """startup_panel + quiet=False → 输出 Panel+Table。"""
        self.out.quiet = False
        self.out.startup_panel({"Threads": "4", "GPU": "OFF"})
        self.out.console.print.assert_called_once()

    # ── final_summary ──

    def test_final_summary_always_displays(self):
        """final_summary → 始终输出。"""
        self.out.final_summary("Results", {"Total": "1M", "Found": "3"})
        self.out.console.print.assert_called_once()

    def test_final_summary_even_in_quiet(self):
        """final_summary + quiet → 仍输出。"""
        self.out.quiet = True
        self.out.final_summary("Results", {"Total": "1M"})
        self.out.console.print.assert_called_once()

    # ── stats_panel ──

    def test_stats_panel_two_tuple_rows(self):
        """stats_panel 2 元组行 → 无样式。"""
        self.out.stats_panel("Stats", [("CPU", "80%"), ("Mem", "512MB")])
        self.out.console.print.assert_called_once()

    def test_stats_panel_three_tuple_rows(self):
        """stats_panel 3 元组行 → 带样式。"""
        self.out.stats_panel(
            "GPU Stats",
            [("GPU0", "95%", "green"), ("GPU1", "30%", "yellow")],
        )
        self.out.console.print.assert_called_once()

    def test_stats_panel_even_in_quiet(self):
        """stats_panel + quiet=True → 仍然输出（无 quiet 守卫）。"""
        self.out.quiet = True
        self.out.stats_panel("Stats", [("Key", "Val")])
        self.out.console.print.assert_called_once()


# ── CLIOutput 运行时状态 ───────────────────────────────────────


class TestCLIOutputRuntime(unittest.TestCase):
    """status_line / performance_status 测试。"""

    def setUp(self):
        CLIOutput.reset_instance()
        self.out = CLIOutput()
        self.out.console = MagicMock()
        self.out.err_console = MagicMock()

    def tearDown(self):
        CLIOutput.reset_instance()

    # ── status_line ──

    def test_status_line_suppressed_when_quiet(self):
        """status_line + quiet=True → 不输出。"""
        self.out.quiet = True
        with patch("sys.stdout.write") as mock_write:
            self.out.status_line("running...")
            mock_write.assert_not_called()

    def test_status_line_output_when_not_quiet(self):
        """status_line + quiet=False → 写入 stdout 并 flush。"""
        self.out.quiet = False
        with (
            patch("sys.stdout.write") as mock_write,
            patch("sys.stdout.flush") as mock_flush,
        ):
            self.out.status_line("running...")
            mock_write.assert_called_once()
            mock_flush.assert_called_once()
            self.assertIn("running...", mock_write.call_args[0][0])

    # ── performance_status ──

    def test_performance_status_suppressed_when_quiet(self):
        """performance_status + quiet=True → 不输出。"""
        self.out.quiet = True
        with patch.object(self.out, "status_line") as mock_sl:
            self.out.performance_status({"speed": 1000})
            mock_sl.assert_not_called()

    def test_performance_status_all_fields(self):
        """performance_status 全部字段 → 组合输出。"""
        self.out.quiet = False
        with patch.object(self.out, "status_line") as mock_sl:
            self.out.performance_status(
                {
                    "speed": 5000,
                    "keys_total": 100000,
                    "gpu_usage": 85,
                    "memory_used": 2048,
                }
            )
            mock_sl.assert_called_once()
            status_text = mock_sl.call_args[0][0]
            self.assertIn("速度:", status_text)
            self.assertIn("5,000/s", status_text)
            self.assertIn("总尝试:", status_text)
            self.assertIn("GPU:", status_text)
            self.assertIn("85%", status_text)
            self.assertIn("内存:", status_text)
            self.assertIn("2048MB", status_text)

    def test_performance_status_partial_fields(self):
        """performance_status 部分字段 → 只输出存在的。"""
        self.out.quiet = False
        with patch.object(self.out, "status_line") as mock_sl:
            self.out.performance_status({"speed": 2000})
            mock_sl.assert_called_once()
            status_text = mock_sl.call_args[0][0]
            self.assertIn("2,000/s", status_text)
            self.assertNotIn("GPU", status_text)

    def test_performance_status_empty_stats(self):
        """performance_status 空字典 → 不调用 status_line。"""
        self.out.quiet = False
        with patch.object(self.out, "status_line") as mock_sl:
            self.out.performance_status({})
            mock_sl.assert_not_called()
