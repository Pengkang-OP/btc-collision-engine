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
