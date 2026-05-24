#!/usr/bin/env python3
"""LogWindow 单元测试 — 对齐 src/cli/log_window.py 实际实现.

LogWindow 是一个轻量级 CLI 内存日志缓冲区：
- __init__(max_lines=100): 初始化，max_lines 控制最大行数
- add_line(line): 追加日志行，超出 max_lines 时丢弃旧行
- render(): 返回最近 20 行，用换行符拼接

注意：src/cli/log_window.py 没有 tkinter/GUI、没有 LogWindowHandler、
没有 create_log_window/reset_log_window_instance 等单例函数。
"""

import logging

import pytest

from src.cli.log_window import LogWindow

logger = logging.getLogger(__name__)


# ============================================================================
# __init__ 测试
# ============================================================================


@pytest.mark.unit
class TestLogWindowInit:
    """LogWindow.__init__ 测试"""

    def test_default_max_lines(self):
        window = LogWindow()
        assert window._max_lines == 100
        assert window._lines == []

    def test_custom_max_lines(self):
        window = LogWindow(max_lines=50)
        assert window._max_lines == 50

    def test_zero_max_lines(self):
        window = LogWindow(max_lines=0)
        assert window._max_lines == 0


# ============================================================================
# add_line 测试
# ============================================================================


@pytest.mark.unit
class TestLogWindowAddLine:
    """LogWindow.add_line() 测试"""

    def test_add_single_line(self):
        window = LogWindow()
        window.add_line("hello")
        assert window._lines == ["hello"]

    def test_add_multiple_lines(self):
        window = LogWindow()
        for i in range(5):
            window.add_line(f"line {i}")
        assert len(window._lines) == 5
        assert window._lines == [f"line {i}" for i in range(5)]

    def test_respects_max_lines(self):
        """超出 max_lines 时丢弃最早的旧行"""
        window = LogWindow(max_lines=3)
        window.add_line("a")
        window.add_line("b")
        window.add_line("c")
        window.add_line("d")  # 触发丢弃 "a"
        assert window._lines == ["b", "c", "d"]
        assert len(window._lines) == 3

    def test_max_lines_zero_discards_all(self):
        """max_lines=0 时所有行立即被丢弃"""
        window = LogWindow(max_lines=0)
        window.add_line("hello")
        assert window._lines == []

    def test_empty_string(self):
        window = LogWindow()
        window.add_line("")
        assert window._lines == [""]

    def test_preserves_order(self):
        window = LogWindow(max_lines=5)
        for i in range(10):
            window.add_line(f"line {i}")
        # 保留最后 5 行
        assert window._lines == [f"line {i}" for i in range(5, 10)]


# ============================================================================
# render 测试
# ============================================================================


@pytest.mark.unit
class TestLogWindowRender:
    """LogWindow.render() 测试"""

    def test_render_empty(self):
        window = LogWindow()
        assert window.render() == ""

    def test_render_single_line(self):
        window = LogWindow()
        window.add_line("hello world")
        assert window.render() == "hello world"

    def test_render_multiple_lines(self):
        window = LogWindow()
        window.add_line("first")
        window.add_line("second")
        assert window.render() == "first\nsecond"

    def test_render_respects_last_20(self):
        """render() 只返回最近 20 行"""
        window = LogWindow(max_lines=100)
        for i in range(30):
            window.add_line(f"line {i:02d}")
        result = window.render()
        lines = result.split("\n")
        assert len(lines) == 20
        assert lines[0] == "line 10"
        assert lines[-1] == "line 29"

    def test_render_when_total_less_than_20(self):
        """总行数 < 20 时返回所有行"""
        window = LogWindow()
        for i in range(5):
            window.add_line(f"line {i}")
        result = window.render()
        assert len(result.split("\n")) == 5

    def test_render_exactly_20(self):
        window = LogWindow()
        for i in range(20):
            window.add_line(f"line {i}")
        result = window.render()
        assert len(result.split("\n")) == 20
        assert result.startswith("line 0")

    def test_render_not_affected_by_max_lines(self):
        """render() 取 _lines[-20:] 而非 _max_lines"""
        window = LogWindow(max_lines=200)
        for i in range(30):
            window.add_line(f"line {i:02d}")
        # _max_lines=200 所以内部保留了全部 30 行，但 render 只取最近 20
        assert len(window._lines) == 30
        result = window.render()
        assert len(result.split("\n")) == 20


# ============================================================================
# 集成测试
# ============================================================================


@pytest.mark.unit
class TestLogWindowIntegration:
    """add_line + render 组合测试"""

    def test_add_and_render_cycle(self):
        window = LogWindow(max_lines=10)
        window.add_line("start")
        assert window.render() == "start"
        window.add_line("end")
        assert window.render() == "start\nend"

    def test_log_simulation(self):
        """模拟真实日志场景"""
        window = LogWindow(max_lines=50)
        messages = [
            "2024-01-01 10:00:00 [INFO] Engine started",
            "2024-01-01 10:00:01 [INFO] Loading config",
            "2024-01-01 10:00:02 [WARNING] No GPU detected",
            "2024-01-01 10:00:03 [INFO] Using CPU backend",
            "2024-01-01 10:00:04 [ERROR] Connection timeout",
        ]
        for msg in messages:
            window.add_line(msg)
        result = window.render()
        assert "Engine started" in result
        assert "Connection timeout" in result
        assert len(result.split("\n")) == 5

    def test_overflow_then_render(self):
        """溢出后 render 只取最近 20 行"""
        window = LogWindow(max_lines=100)
        for i in range(100):
            window.add_line(f"msg {i}")
        # 内部有 100 行，render 取最近 20
        result = window.render()
        lines = result.split("\n")
        assert len(lines) == 20
        assert lines[0] == "msg 80"
        assert lines[-1] == "msg 99"
