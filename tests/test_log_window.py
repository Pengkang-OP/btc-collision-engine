#!/usr/bin/env python3
"""独立日志窗口 (log_window) 单元测试

覆盖：
- LogWindow 基本属性与队列
- LogWindowHandler 日志处理器
- reset_log_window_instance 单例重置
- create_log_window 单例模式
"""

import logging
import pytest
from unittest.mock import patch, MagicMock

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_log_window():
    """每个测试后清理日志窗口单例"""
    yield
    from src.cli.log_window import reset_log_window_instance

    reset_log_window_instance()


# ============================================================================
# LogWindow 基本属性测试
# ============================================================================


@pytest.mark.unit
class TestLogWindowBasic:
    """LogWindow 基本属性测试"""

    def test_create_log_window(self):
        from src.cli.log_window import LogWindow

        window = LogWindow(title="Test", width=400, height=300)
        assert window.title == "Test"
        assert window.width == 400
        assert window.height == 300
        assert window.running is False
        assert window.root is None

    def test_default_values(self):
        from src.cli.log_window import LogWindow

        window = LogWindow()
        assert window.title == "引擎日志"
        assert window.width == 800
        assert window.height == 600

    def test_log_queues_message(self):
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.log("test message", "INFO")
        assert not window.log_queue.empty()
        entry = window.log_queue.get_nowait()
        assert "test message" in entry
        assert "[INFO]" in entry

    def test_log_queue_full_drops(self):
        """队列满时不应崩溃"""
        from src.cli.log_window import LogWindow
        import queue

        window = LogWindow()
        # 使用一个很小的队列模拟满的情况
        window.log_queue = queue.Queue(maxsize=2)
        for i in range(5):
            window.log(f"message {i}")
        # 不应崩溃

    def test_stop_when_not_running(self):
        from src.cli.log_window import LogWindow

        window = LogWindow()
        # 未 start 的情况下 stop 不应崩溃
        window.stop()

    def test_stop_sets_running_false(self):
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.running = True
        window.stop()
        assert window.running is False


# ============================================================================
# LogWindowHandler 测试
# ============================================================================


@pytest.mark.unit
class TestLogWindowHandler:
    """日志窗口处理器测试"""

    def test_emit_delegates_to_log_window(self):
        from src.cli.log_window import LogWindowHandler, LogWindow

        window = LogWindow()
        handler = LogWindowHandler(window)
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord("test_logger", logging.INFO, "", 0, "handler test", (), None)
        handler.emit(record)
        # 消息应进入队列
        assert not window.log_queue.empty()

    def test_emit_preserves_level(self):
        from src.cli.log_window import LogWindowHandler, LogWindow

        window = LogWindow()
        handler = LogWindowHandler(window)
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord("test", logging.ERROR, "", 0, "error msg", (), None)
        handler.emit(record)
        entry = window.log_queue.get_nowait()
        assert "[ERROR]" in entry

    def test_emit_handles_format_error(self):
        """格式化错误时不应崩溃"""
        from src.cli.log_window import LogWindowHandler, LogWindow

        window = LogWindow()
        handler = LogWindowHandler(window)
        # 使用一个会出错的 formatter
        handler.setFormatter(MagicMock())
        handler.formatter.format.side_effect = Exception("format error")

        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        handler.emit(record)  # 不应崩溃


# ============================================================================
# reset_log_window_instance 测试
# ============================================================================


@pytest.mark.unit
class TestResetLogWindow:
    """单例重置测试"""

    def test_reset_cleans_global_instance(self):
        from src.cli.log_window import reset_log_window_instance
        import src.cli.log_window as lw

        # 设置一个模拟的单例
        mock_window = MagicMock()
        lw._log_window_instance = mock_window

        reset_log_window_instance()

        assert lw._log_window_instance is None
        mock_window.stop.assert_called_once()

    def test_reset_removes_handler_from_root(self):
        from src.cli.log_window import reset_log_window_instance, LogWindowHandler, LogWindow
        import src.cli.log_window as lw

        window = LogWindow()
        handler = LogWindowHandler(window)
        root = logging.getLogger()
        root.addHandler(handler)

        lw._log_window_instance = window

        reset_log_window_instance()

        # handler 应被移除
        assert handler not in root.handlers
        assert lw._log_window_instance is None

    def test_reset_when_none_is_safe(self):
        from src.cli.log_window import reset_log_window_instance

        # 重复 reset 应安全
        reset_log_window_instance()
        reset_log_window_instance()  # 不应崩溃


# ============================================================================
# create_log_window 测试
# ============================================================================


@pytest.mark.unit
class TestCreateLogWindow:
    """create_log_window 函数测试"""

    def test_returns_same_instance(self):
        """单例模式：重复调用返回同一实例"""
        from src.cli.log_window import create_log_window
        import src.cli.log_window as lw

        # 确保单例为空
        lw._log_window_instance = None

        # 使用 mock 避免实际创建 tkinter 窗口
        with (
            patch("src.cli.log_window.LogWindow.start") as mock_start,  # noqa: F841
            patch("src.cli.log_window.LogWindow") as mock_log_window_cls,
        ):
            mock_instance1 = MagicMock()
            mock_instance2 = MagicMock()
            mock_log_window_cls.side_effect = [mock_instance1, mock_instance2]

            w1 = create_log_window()
            w2 = create_log_window()

            assert w1 is w2
            # start 应只被调用一次（第二次是重复调用，单例已存在）
            mock_instance1.start.assert_called_once()
            mock_instance2.start.assert_not_called()

    def test_adds_handler_to_root(self):
        """应添加 LogWindowHandler 到根日志器"""
        from src.cli.log_window import create_log_window
        import src.cli.log_window as lw

        lw._log_window_instance = None

        with (
            patch("src.cli.log_window.LogWindow.start") as mock_start,  # noqa: F841
            patch("src.cli.log_window.LogWindow") as mock_log_window_cls,
        ):
            mock_instance = MagicMock()
            mock_log_window_cls.return_value = mock_instance

            root = logging.getLogger()
            original_handler_count = len(root.handlers)

            create_log_window()

            # 应添加了一个 LogWindowHandler
            assert len(root.handlers) == original_handler_count + 1
            assert any(isinstance(h, lw.LogWindowHandler) for h in root.handlers)

            # 清理
            for h in list(root.handlers):
                if isinstance(h, lw.LogWindowHandler):
                    root.removeHandler(h)


# ============================================================================
# start() 测试
# ============================================================================


@pytest.mark.unit
class TestLogWindowStart:
    """LogWindow.start() 测试"""

    def test_start_creates_thread_and_sets_running(self):
        """start() 应创建 daemon 线程并设置 running=True"""
        from src.cli.log_window import LogWindow

        window = LogWindow()

        with patch("threading.Thread") as mock_thread_cls:
            with patch("time.sleep"):  # 跳过等待
                window.start()

        assert window.running is True
        mock_thread_cls.return_value.start.assert_called_once()
        # 验证 daemon=True
        call_kwargs = mock_thread_cls.call_args
        assert call_kwargs[1].get("daemon") is True

    def test_start_calls_run_window(self):
        """start() 线程 target 应为 _run_window"""
        from src.cli.log_window import LogWindow

        window = LogWindow()

        with patch("threading.Thread") as mock_thread_cls:
            with patch("time.sleep"):
                window.start()

        call_kwargs = mock_thread_cls.call_args
        assert call_kwargs[1]["target"] == window._run_window


# ============================================================================
# stop() 完整路径测试
# ============================================================================


@pytest.mark.unit
class TestLogWindowStopComplete:
    """LogWindow.stop() 含 root/thread 的完整路径测试"""

    def test_stop_with_root_and_thread(self):
        """root 存在时调用 destroy，thread 存在时调用 join"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.running = True
        window.root = MagicMock()
        window.update_thread = MagicMock()

        window.stop()

        assert window.running is False
        window.root.after.assert_called_once_with(0, window.root.destroy)
        window.update_thread.join.assert_called_once_with(timeout=2.0)

    def test_stop_root_destroy_after(self):
        """验证 root.destroy 通过 after(0, ...) 调度"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.running = True
        window.root = MagicMock()

        window.stop()

        window.root.after.assert_called_once()
        call_args = window.root.after.call_args[0]
        assert call_args[0] == 0
        assert call_args[1] == window.root.destroy


# ============================================================================
# _run_window() 测试
# ============================================================================


@pytest.mark.unit
class TestLogWindowRunWindow:
    """LogWindow._run_window() 测试 — mock 整个 Tkinter 栈"""

    def _setup_window_for_run(self):
        """创建 LogWindow 并设置 mock root 以测试 _run_window"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.running = True
        return window

    @patch("src.cli.log_window.scrolledtext.ScrolledText")
    @patch("src.cli.log_window.ttk.Button")
    @patch("src.cli.log_window.ttk.Checkbutton")
    @patch("src.cli.log_window.ttk.Combobox")
    @patch("src.cli.log_window.ttk.Label")
    @patch("src.cli.log_window.ttk.Frame")
    @patch("src.cli.log_window.tk.StringVar")
    @patch("src.cli.log_window.tk.BooleanVar")
    def test_run_window_creates_widgets(
        self, mock_boolvar, mock_strvar,
        mock_frame, mock_label, mock_combo,
        mock_check, mock_button, mock_text,
    ):
        """_run_window 应创建所有 Tkinter 组件"""
        from src.cli.log_window import LogWindow
        import tkinter as tk

        window = LogWindow()
        window.running = True
        mock_root = MagicMock()
        # 阻止 mainloop
        mock_root.mainloop.side_effect = lambda: None

        with patch.object(tk, "Tk", return_value=mock_root):
            window._run_window()

        # 验证窗口配置
        mock_root.title.assert_called_once_with(window.title)
        mock_root.geometry.assert_called_once()
        mock_root.protocol.assert_called_once()

        # 验证组件创建
        assert mock_frame.called
        assert mock_label.called
        assert mock_combo.called
        assert mock_check.called
        assert mock_button.called
        assert mock_text.called

    @patch("src.cli.log_window.scrolledtext.ScrolledText")
    @patch("src.cli.log_window.ttk.Button")
    @patch("src.cli.log_window.ttk.Checkbutton")
    @patch("src.cli.log_window.ttk.Combobox")
    @patch("src.cli.log_window.ttk.Label")
    @patch("src.cli.log_window.ttk.Frame")
    @patch("src.cli.log_window.tk.StringVar")
    @patch("src.cli.log_window.tk.BooleanVar")
    def test_run_window_sets_filter_and_autoscroll(
        self, mock_boolvar, mock_strvar,
        mock_frame, mock_label, mock_combo,
        mock_check, mock_button, mock_text,
    ):
        """_run_window 应正确设置 filter_var 和 auto_scroll_var"""
        from src.cli.log_window import LogWindow
        import tkinter as tk

        window = LogWindow()
        window.running = True
        mock_root = MagicMock()
        mock_root.mainloop.side_effect = lambda: None

        with patch.object(tk, "Tk", return_value=mock_root):
            window._run_window()

        assert window.filter_var is not None
        assert window.auto_scroll_var is not None
        assert window.text_area is not None

    @patch("src.cli.log_window.scrolledtext.ScrolledText")
    @patch("src.cli.log_window.ttk.Button")
    @patch("src.cli.log_window.ttk.Checkbutton")
    @patch("src.cli.log_window.ttk.Combobox")
    @patch("src.cli.log_window.ttk.Label")
    @patch("src.cli.log_window.ttk.Frame")
    @patch("src.cli.log_window.tk.StringVar")
    @patch("src.cli.log_window.tk.BooleanVar")
    def test_run_window_tags_configured(
        self, mock_boolvar, mock_strvar,
        mock_frame, mock_label, mock_combo,
        mock_check, mock_button, mock_text,
    ):
        """_run_window 应配置所有日志级别标签颜色"""
        from src.cli.log_window import LogWindow
        import tkinter as tk

        window = LogWindow()
        window.running = True
        mock_root = MagicMock()
        mock_root.mainloop.side_effect = lambda: None
        mock_text_instance = mock_text.return_value

        with patch.object(tk, "Tk", return_value=mock_root):
            window._run_window()

        # 验证 5 个日志级别标签
        assert mock_text_instance.tag_config.call_count >= 5

    @patch("src.cli.log_window.scrolledtext.ScrolledText")
    @patch("src.cli.log_window.ttk.Button")
    @patch("src.cli.log_window.ttk.Checkbutton")
    @patch("src.cli.log_window.ttk.Combobox")
    @patch("src.cli.log_window.ttk.Label")
    @patch("src.cli.log_window.ttk.Frame")
    @patch("src.cli.log_window.tk.StringVar")
    @patch("src.cli.log_window.tk.BooleanVar")
    def test_run_window_handles_mainloop_exception(
        self, mock_boolvar, mock_strvar,
        mock_frame, mock_label, mock_combo,
        mock_check, mock_button, mock_text,
    ):
        """mainloop 抛异常 → 被 except 吞掉不崩溃"""
        from src.cli.log_window import LogWindow
        import tkinter as tk

        window = LogWindow()
        window.running = True
        mock_root = MagicMock()
        mock_root.mainloop.side_effect = RuntimeError("Tcl error")

        with patch.object(tk, "Tk", return_value=mock_root):
            window._run_window()  # 不应崩溃


# ============================================================================
# _update_logs() 测试
# ============================================================================


@pytest.mark.unit
class TestLogWindowUpdateLogs:
    """LogWindow._update_logs() 测试"""

    def test_update_logs_stops_when_not_running(self):
        """running=False → 直接返回，不处理队列"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.running = False
        window.log("test")  # 加入队列

        # 不应调用 root.after
        window._update_logs()
        # 队列应仍包含消息（未被处理）
        assert not window.log_queue.empty()

    def test_update_logs_stops_when_no_root(self):
        """root=None → 直接返回"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.running = True
        window.root = None
        window.log("test")

        window._update_logs()
        assert not window.log_queue.empty()

    def test_update_logs_processes_queue(self):
        """正常处理队列中的所有日志"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.running = True
        window.root = MagicMock()
        window.text_area = MagicMock()
        window.filter_var = MagicMock()
        window.filter_var.get.return_value = "ALL"
        window.auto_scroll_var = MagicMock()
        window.auto_scroll_var.get.return_value = True

        window.log("msg1", "INFO")
        window.log("msg2", "WARNING")

        window._update_logs()

        # 队列应被清空
        assert window.log_queue.empty()
        # text_area.insert 被调用 2 次
        assert window.text_area.insert.call_count == 2

    def test_update_logs_schedules_next(self):
        """处理完毕后应通过 root.after 调度下一次更新"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.running = True
        window.root = MagicMock()
        window.text_area = MagicMock()
        window.filter_var = MagicMock()
        window.filter_var.get.return_value = "ALL"
        window.auto_scroll_var = MagicMock()
        window.auto_scroll_var.get.return_value = True

        window._update_logs()

        window.root.after.assert_called_with(100, window._update_logs)

    def test_update_logs_handles_queue_empty_race(self):
        """empty() 返回 False 但 get_nowait() 抛 Empty → break 不崩溃"""
        from src.cli.log_window import LogWindow
        import queue

        window = LogWindow()
        window.running = True
        window.root = MagicMock()
        window.text_area = MagicMock()
        window.filter_var = MagicMock()
        window.filter_var.get.return_value = "ALL"
        window.auto_scroll_var = MagicMock()
        window.auto_scroll_var.get.return_value = True

        # 模拟竞态：empty() 返回 False，但 get_nowait() 抛 Empty
        window.log_queue.empty = MagicMock(side_effect=[False, True])
        window.log_queue.get_nowait = MagicMock(side_effect=queue.Empty)

        window._update_logs()  # 不应崩溃
        window.root.after.assert_called_with(100, window._update_logs)


# ============================================================================
# _display_log() 测试
# ============================================================================


@pytest.mark.unit
class TestLogWindowDisplayLog:
    """LogWindow._display_log() 测试"""

    def test_display_log_no_text_area(self):
        """text_area=None → 直接返回"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.text_area = None
        window._display_log("[2024-01-01 00:00:00] [INFO] test")
        # 不应崩溃

    def test_display_log_inserts_with_level_tag(self):
        """正常显示日志，插入时带级别标签"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.text_area = MagicMock()
        window.filter_var = MagicMock()
        window.filter_var.get.return_value = "ALL"
        window.auto_scroll_var = MagicMock()
        window.auto_scroll_var.get.return_value = True

        log_entry = "[2024-01-01 00:00:00] [ERROR] something broke"
        window._display_log(log_entry)

        window.text_area.insert.assert_called_once()
        # 第二个参数是日志内容，第三个是 level 标签
        args = window.text_area.insert.call_args[0]
        assert args[1] == log_entry + "\n"
        assert args[2] == "ERROR"

    def test_display_log_filters_by_level(self):
        """过滤级别不匹配 → 不显示"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.text_area = MagicMock()
        window.filter_var = MagicMock()
        window.filter_var.get.return_value = "ERROR"
        window.auto_scroll_var = MagicMock()

        log_entry = "[2024-01-01 00:00:00] [INFO] not important"
        window._display_log(log_entry)

        # 被过滤，不应插入
        window.text_area.insert.assert_not_called()

    def test_display_log_filter_all_shows_everything(self):
        """ALL 过滤 → 所有级别都显示"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.text_area = MagicMock()
        window.filter_var = MagicMock()
        window.filter_var.get.return_value = "ALL"
        window.auto_scroll_var = MagicMock()
        window.auto_scroll_var.get.return_value = True

        for level in ["DEBUG", "INFO", "WARNING"]:
            window._display_log(f"[2024-01-01 00:00:00] [{level}] msg")

        assert window.text_area.insert.call_count == 3

    def test_display_log_autoscroll_disabled(self):
        """auto_scroll=False → 不调用 see()"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.text_area = MagicMock()
        window.filter_var = MagicMock()
        window.filter_var.get.return_value = "ALL"
        window.auto_scroll_var = MagicMock()
        window.auto_scroll_var.get.return_value = False

        window._display_log("[2024-01-01 00:00:00] [INFO] msg")

        window.text_area.see.assert_not_called()

    def test_display_log_extracts_level_from_brackets(self):
        """正确从 [LEVEL] 格式提取级别"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.text_area = MagicMock()
        window.filter_var = MagicMock()
        window.filter_var.get.return_value = "WARNING"
        window.auto_scroll_var = MagicMock()
        window.auto_scroll_var.get.return_value = True

        # WARNING 级别，过滤器设为 WARNING → 应显示
        window._display_log("[2024-01-01 00:00:00] [WARNING] caution")
        window.text_area.insert.assert_called_once()
        assert window.text_area.insert.call_args[0][2] == "WARNING"

    def test_display_log_no_filter_var_defaults_all(self):
        """filter_var=None → 默认 ALL"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.text_area = MagicMock()
        window.filter_var = None
        window.auto_scroll_var = MagicMock()
        window.auto_scroll_var.get.return_value = True

        window._display_log("[2024-01-01 00:00:00] [DEBUG] detail")
        window.text_area.insert.assert_called_once()

    def test_display_log_malformed_entry_defaults_info(self):
        """格式异常的日志 → 默认 INFO 级别"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.text_area = MagicMock()
        window.filter_var = MagicMock()
        window.filter_var.get.return_value = "ALL"
        window.auto_scroll_var = MagicMock()
        window.auto_scroll_var.get.return_value = True

        # 没有正确的 [LEVEL] 格式
        window._display_log("just a plain message")

        window.text_area.insert.assert_called_once()
        assert window.text_area.insert.call_args[0][2] == "INFO"


# ============================================================================
# _clear_log() 测试
# ============================================================================


@pytest.mark.unit
class TestLogWindowClearLog:
    """LogWindow._clear_log() 测试"""

    def test_clear_log_deletes_content(self):
        """清空日志区域内容"""
        from src.cli.log_window import LogWindow
        import tkinter as tk

        window = LogWindow()
        window.text_area = MagicMock()

        window._clear_log()

        window.text_area.delete.assert_called_once_with(1.0, tk.END)

    def test_clear_log_no_text_area_safe(self):
        """text_area=None → 安全跳过"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.text_area = None

        window._clear_log()  # 不应崩溃


# ============================================================================
# _save_log() 测试
# ============================================================================


@pytest.mark.unit
class TestLogWindowSaveLog:
    """LogWindow._save_log() 测试"""

    def test_save_log_no_text_area(self):
        """text_area=None → 直接返回"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.text_area = None

        window._save_log()  # 不应崩溃

    def test_save_log_no_file_selected(self):
        """用户取消文件选择 → 不写入"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.text_area = MagicMock()
        window.text_area.get.return_value = "log content"

        with patch("tkinter.filedialog.asksaveasfilename", return_value=""):
            with patch("builtins.open") as mock_open:
                window._save_log()
                mock_open.assert_not_called()

    def test_save_log_writes_to_file(self):
        """选择文件路径 → 写入日志内容"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.text_area = MagicMock()
        window.text_area.get.return_value = "log content here\n"

        mock_file = MagicMock()
        with patch("tkinter.filedialog.asksaveasfilename",
                   return_value="/tmp/test.log"):
            with patch("builtins.open", return_value=mock_file):
                window._save_log()
                mock_file.__enter__().write.assert_called_once_with("log content here\n")

    def test_save_log_handles_write_error(self):
        """写入失败 → 调用 self.log 记录错误"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.text_area = MagicMock()
        window.text_area.get.return_value = "content"

        with patch("tkinter.filedialog.asksaveasfilename",
                   return_value="/tmp/test.log"):
            with patch("builtins.open", side_effect=IOError("disk full")):
                with patch.object(window, "log") as mock_log:
                    window._save_log()
                    mock_log.assert_called_once()
                    assert "保存日志失败" in mock_log.call_args[0][0]
                    assert mock_log.call_args[0][1] == "ERROR"


# ============================================================================
# _on_close() 测试
# ============================================================================


@pytest.mark.unit
class TestLogWindowOnClose:
    """LogWindow._on_close() 测试"""

    def test_on_close_stops_and_destroys(self):
        """关闭时应设置 running=False 并销毁窗口"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.running = True
        window.root = MagicMock()

        window._on_close()

        assert window.running is False
        window.root.destroy.assert_called_once()

    def test_on_close_no_root_safe(self):
        """root 不存在时 _on_close 仍安全"""
        from src.cli.log_window import LogWindow

        window = LogWindow()
        window.running = True
        window.root = None

        window._on_close()  # 不应崩溃
        assert window.running is False


# ============================================================================
# reset_log_window_instance 异常路径
# ============================================================================


@pytest.mark.unit
class TestResetLogWindowStopException:
    """reset_log_window_instance stop() 异常路径测试"""

    def test_reset_handles_stop_exception(self):
        """stop() 抛异常 → 被 except 捕获，单例仍被清理"""
        from src.cli.log_window import reset_log_window_instance
        import src.cli.log_window as lw

        mock_window = MagicMock()
        mock_window.stop.side_effect = RuntimeError("Tcl error during stop")
        lw._log_window_instance = mock_window

        # 不应崩溃
        reset_log_window_instance()

        assert lw._log_window_instance is None
        mock_window.stop.assert_called_once()

    def test_reset_removes_multiple_handlers(self):
        """移除根日志器中所有 LogWindowHandler"""
        from src.cli.log_window import reset_log_window_instance, LogWindowHandler, LogWindow
        import src.cli.log_window as lw

        window = LogWindow()
        root = logging.getLogger()
        handler1 = LogWindowHandler(window)
        handler2 = LogWindowHandler(window)
        root.addHandler(handler1)
        root.addHandler(handler2)

        lw._log_window_instance = window

        reset_log_window_instance()

        assert handler1 not in root.handlers
        assert handler2 not in root.handlers
