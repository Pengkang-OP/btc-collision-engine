"""CLI output formatting utilities."""

import io
import json
import os
import platform
import sys
from typing import Any, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    Console = None
    Panel = None
    Table = None
    Text = None


def _get_utf8_console(stderr: bool = False, no_color: bool = False):
    """获取 UTF-8 兼容的 Console 实例。"""
    if platform.system() == "Windows":
        # Windows 特殊处理：尝试设置 stdout/stderr 为 utf-8
        try:
            if stderr:
                if hasattr(sys.stderr, "reconfigure"):
                    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            elif hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, AttributeError, io.UnsupportedOperation):
            pass  # 静默失败
    # 检查 NO_COLOR 环境变量
    env_no_color = "NO_COLOR" in os.environ
    actual_no_color = no_color or env_no_color
    console_kwargs = {
        "no_color": actual_no_color,
        "stderr": stderr,
    }
    if Console is not None:
        return Console(**console_kwargs)
    # 如果没有安装 rich，返回简单的对象

    class SimpleConsole:
        def __init__(self, **kwargs):
            self.no_color = kwargs.get("no_color", False)
            self.stderr = kwargs.get("stderr", False)

        def print(self, *args, **kwargs):
            print(*args, **kwargs)

        def rule(self, title="", **kwargs):
            out = sys.stderr if self.stderr else sys.stdout
            print(title, file=out)

    return SimpleConsole(**console_kwargs)


class CLIOutput:
    """CLI 输出管理器单例类。"""

    _instance: Optional["CLIOutput"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "CLIOutput":
        """获取单例实例。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def init(cls, quiet: bool = False, no_color: bool = False, compact: bool = False) -> "CLIOutput":
        """初始化/重置单例（绕过 `__new__` 的单例限制，确保创建全新实例）。"""
        instance = object.__new__(cls)
        instance.__init__(quiet=quiet, no_color=no_color, compact=compact)
        cls._instance = instance
        return instance

    @classmethod
    def reset_instance(cls):
        """重置单例（仅用于测试。"""
        cls._instance = None

    def __init__(self, quiet: bool = False, no_color: bool = False, compact: bool = False):
        self.quiet = quiet
        self.compact = compact
        self.console = _get_utf8_console(stderr=False, no_color=no_color)
        self.err_console = _get_utf8_console(stderr=True, no_color=no_color)

    def print(self, message: Any = "", **kwargs):
        """普通打印（受 quiet 模式影响。"""
        if not self.quiet:
            self.console.print(message, **kwargs)

    def print_always(self, message: Any = "", **kwargs):
        """总是打印（不受 quiet 影响）。"""
        self.console.print(message, **kwargs)

    def info(self, message: str):
        """打印 INFO 级别消息。"""
        if not self.quiet:
            if Text is not None:
                self.console.print(Text.assemble(("[INFO] ", "blue"), message))
            else:
                self.console.print(f"[INFO] {message}")

    def success(self, message: str):
        """打印 SUCCESS 级别消息。"""
        if Text is not None:
            self.console.print(Text.assemble(("[OK] ", "green"), message))
        else:
            self.console.print(f"[OK] {message}")

    def hint(self, message: str):
        """打印 HINT 级别消息。"""
        if Text is not None:
            self.console.print(Text.assemble(("[HINT] ", "cyan"), message))
        else:
            self.console.print(f"[HINT] {message}")

    def warning(self, message: str, details: Optional[str] = None):
        """打印 WARNING 级别消息。"""
        if Text is not None:
            self.err_console.print(Text.assemble(("[WARN] ", "yellow"), message))
        else:
            self.err_console.print(f"[WARN] {message}")
        if details:
            if Text is not None:
                self.err_console.print(Text(details, style="dim"))
            else:
                self.err_console.print(details)

    def error(self, message: str, details: Optional[str] = None):
        """打印 ERROR 级别消息。"""
        if Text is not None:
            self.err_console.print(Text.assemble(("[ERROR] ", "red"), message))
        else:
            self.err_console.print(f"[ERROR] {message}")
        if details:
            if Text is not None:
                self.err_console.print(Text(details, style="dim"))
            else:
                self.err_console.print(details)

    def rule(self, title: str = "", style: str = "dim"):
        """打印分隔线。"""
        if not self.quiet:
            if self.console and hasattr(self.console, "rule"):
                self.console.rule(title, style=style)
            else:
                self.console.print(title)

    def header(self, title: str):
        """打印标题头。"""
        if not self.quiet:
            if not self.compact:
                self.print()
            self.rule(title, style="bold cyan")
            if not self.compact:
                self.print()

    def startup_panel(self, config: dict):
        """打印启动配置面板。"""
        if not self.quiet:
            if Panel is not None and Table is not None:
                table = Table(show_header=False, box=None)
                for k, v in config.items():
                    table.add_row(f"{k}:", str(v))
                panel = Panel(table, title="[bold]配置[/bold]", border_style="cyan")
                self.console.print(panel)
            else:
                # 降级方案
                self.console.print("配置:")
                for k, v in config.items():
                    self.console.print(f"  {k}: {v}")

    def final_summary(self, title: str, stats: dict):
        """打印最终摘要。"""
        if Panel is not None and Table is not None:
            table = Table(show_header=False, box=None)
            for k, v in stats.items():
                table.add_row(f"{k}:", str(v))
            panel = Panel(table, title=f"[bold]{title}[/bold]", border_style="green")
            self.console.print(panel)
        else:
            self.console.print(title)
            for k, v in stats.items():
                self.console.print(f"  {k}: {v}")

    def stats_panel(self, title: str, rows: list):
        """打印统计面板。"""
        if Panel is not None and Table is not None:
            table = Table(show_header=False, box=None)
            for row in rows:
                if len(row) == 3:
                    k, v, style = row
                    table.add_row(f"{k}:", Text(str(v), style=style))
                elif len(row) == 2:
                    k, v = row
                    table.add_row(f"{k}:", str(v))
            panel = Panel(table, title=f"[bold]{title}[/bold]", border_style="blue")
            self.console.print(panel)
        else:
            self.console.print(title)
            for row in rows:
                if len(row) == 3:
                    k, v, _ = row
                    self.console.print(f"  {k}: {v}")
                elif len(row) == 2:
                    k, v = row
                    self.console.print(f"  {k}: {v}")

    def status_line(self, text: str):
        """打印状态行（覆盖式）。"""
        if not self.quiet:
            sys.stdout.write(f"\r{text}")
            sys.stdout.flush()

    def performance_status(self, stats: dict):
        """打印性能状态行。"""
        if not self.quiet and stats:
            parts = []
            if "speed" in stats:
                speed = stats["speed"]
                if speed >= 1000000:
                    parts.append(f"速度: {speed / 1000000:.1f}M/s")
                elif speed >= 1000:
                    parts.append(f"速度: {speed / 1000:.1f}K/s")
                else:
                    parts.append(f"速度: {speed:.0f}/s")
            if "keys_total" in stats:
                parts.append(f"总尝试: {stats['keys_total']:,}")
            if "gpu_usage" in stats:
                parts.append(f"GPU: {stats['gpu_usage']}%")
            if "memory_used" in stats:
                parts.append(f"内存: {stats['memory_used']}MB")
            if parts:
                self.status_line(" | ".join(parts))


def format_results(results: list[dict]) -> str:
    """Format collision results for console output.

    Args:
        results: List of match result dicts

    Returns:
        Formatted output string

    """
    if not results:
        return "No matches found."

    lines = ["=== Collision Results ==="]
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. Address: {r.get('address', 'N/A')}",
        )
    return "\n".join(lines)


def format_json(data) -> str:
    """Format data as pretty JSON.

    Args:
        data: Data to format

    Returns:
        Pretty JSON string

    """
    return json.dumps(data, indent=2, default=str)
