#!/usr/bin/env python3
"""
CLI 统一输出管理器 - 基于 Rich 库

提供格式统一、支持颜色控制和静默模式的 CLI 输出功能。
管道输出（非 tty）时自动禁用 ANSI 转义码。
"""

import io
import os
import platform
import sys
import threading
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def _get_utf8_console(stderr: bool = False, no_color: bool = False) -> Console:
    """创建强制 UTF-8 编码的 Rich Console，解决 Windows GBK 终端乱码问题。

    优先使用 Python 3.7+ 的 reconfigure() 接口（不会关闭底层 buffer），
    失败则静默降级为默认 Console，避免 TextIOWrapper 关闭底层句柄。
    """
    if platform.system() == "Windows":
        try:
            target_stream = sys.stderr if stderr else sys.stdout
            # Python 3.7+: reconfigure 不会创建新 wrapper，不会关闭底层 fd
            if hasattr(target_stream, "reconfigure"):
                target_stream.reconfigure(encoding="utf-8", errors="replace")
                return Console(
                    file=target_stream,
                    highlight=False,
                    no_color=no_color,
                    force_terminal=True,
                )
        except (AttributeError, io.UnsupportedOperation, OSError):
            pass
    # 非 Windows 或 reconfigure 失败：使用默认 Console
    # 管道/重定向场景下强制终端模式以保留颜色输出
    target_stream = sys.stderr if stderr else sys.stdout
    is_tty = target_stream.isatty() if hasattr(target_stream, "isatty") else True
    return Console(
        highlight=False,
        no_color=no_color,
        stderr=stderr,
        force_terminal=not is_tty,
    )


class CLIOutput:
    """统一的 CLI 输出管理器，支持颜色控制和静默模式。

    遵循 https://no-color.org/ 规范：环境变量 NO_COLOR 存在时强制禁色。
    Rich 库会自动检测非 tty（管道/重定向）并禁用 ANSI 转义码。
    """

    _instance: Optional["CLIOutput"] = None  # 单例
    _lock: threading.Lock = threading.Lock()  # 线程安全锁

    def __init__(self, no_color: bool = False, quiet: bool = False, compact: bool = False) -> None:
        # NO_COLOR 环境变量优先（https://no-color.org/）
        force_no_color = no_color or os.environ.get("NO_COLOR") is not None

        self.quiet = quiet
        self.compact = compact
        self.console = _get_utf8_console(stderr=False, no_color=force_no_color)
        self.err_console = _get_utf8_console(stderr=True, no_color=force_no_color)

    # ── 单例管理 ──────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "CLIOutput":
        """获取单例实例；若未初始化则以默认参数创建。

        线程安全：使用 double-checked locking 防止并发创建多个实例。
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def init(cls, no_color: bool = False, quiet: bool = False, compact: bool = False) -> "CLIOutput":
        """初始化单例（应在程序入口处调用一次）。

        线程安全：持锁替换实例，调用方应确保在单线程初始化阶段调用。
        """
        with cls._lock:
            cls._instance = cls(no_color=no_color, quiet=quiet, compact=compact)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（测试用：允许 capsys/monkeypatch 替换 stdout 后重新创建）。

        线程安全：持锁清空实例。
        """
        with cls._lock:
            cls._instance = None

    # ── 消息级别输出 ──────────────────────────────────────────────────

    def info(self, msg: str) -> None:
        """蓝色 [INFO] 信息，quiet 模式下不显示。"""
        if not self.quiet:
            self.console.print(f"[blue][INFO][/blue] {msg}")

    def success(self, msg: str) -> None:
        """绿色 [OK] 成功消息，始终显示。"""
        self.console.print(f"[green][OK][/green] {msg}")

    def hint(self, msg: str) -> None:
        """蓝色 [HINT] 提示信息，始终显示。"""
        self.console.print(f"[blue][HINT][/blue] {msg}")

    def warning(self, msg: str, details: str | None = None) -> None:
        """黄色 [WARN] 警告，输出到 stderr。

        Args:
            msg: 警告消息
            details: 可选的警告详细信息
        """
        self.err_console.print(f"[yellow][WARN][/yellow] {msg}")
        if details:
            self.err_console.print(f"[yellow]└─ 详细:[/yellow] {details}")

    def error(self, msg: str, details: str | None = None) -> None:
        """红色 [ERROR] 错误，输出到 stderr。

        Args:
            msg: 错误消息
            details: 可选的错误详细信息
        """
        self.err_console.print(f"[red][ERROR][/red] {msg}")
        if details:
            self.err_console.print(f"[red]└─ 详细:[/red] {details}")

    def print(self, msg: str = "", **kwargs) -> None:
        """普通输出，quiet 模式下不显示。"""
        if not self.quiet:
            self.console.print(msg, **kwargs)

    def print_always(self, msg: str = "", **kwargs) -> None:
        """始终输出（不受 quiet 影响）。"""
        self.console.print(msg, **kwargs)

    # ── 结构化输出 ────────────────────────────────────────────────────

    def rule(self, title: str = "", style: str = "dim") -> None:
        """水平分隔线，quiet 模式下不显示。"""
        if not self.quiet:
            self.console.rule(title, style=style)

    def header(self, title: str) -> None:
        """大标题分隔线，quiet 模式下不显示。"""
        if not self.quiet:
            if not self.compact:
                self.console.print()
            self.console.rule(f"[bold]{title}[/bold]", style="bright_blue")
            if not self.compact:
                self.console.print()

    def startup_panel(self, config: dict) -> None:
        """使用 Rich Panel + Table 展示启动配置，quiet 模式下不显示。

        Args:
            config: 有序字典，key 为配置项名称，value 为配置值。
        """
        if self.quiet:
            return
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("项目", style="cyan", min_width=14)
        table.add_column("值", style="white")
        for key, value in config.items():
            table.add_row(str(key), str(value))
        self.console.print(Panel(table, title="[bold]启动配置[/bold]", border_style="blue"))

    def final_summary(self, title: str, stats: dict) -> None:
        """使用 Rich Panel + Table 展示最终统计，始终显示。

        Args:
            title: 面板标题。
            stats: 有序字典，key 为指标名，value 为指标值。
        """
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("指标", style="cyan", min_width=12)
        table.add_column("值", style="bold white")
        for key, value in stats.items():
            table.add_row(str(key), str(value))
        self.console.print(Panel(table, title=f"[bold]{title}[/bold]", border_style="green"))

    def stats_panel(self, title: str, rows: list) -> None:
        """通用统计面板（支持自定义行样式）。

        Args:
            title: 面板标题。
            rows:  列表，每个元素为 (label, value) 或 (label, value, style) 元组。
        """
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("指标", style="cyan", min_width=14)
        table.add_column("值", style="bold white")
        for row in rows:
            if len(row) == 3:
                label, value, style = row
                table.add_row(str(label), f"[{style}]{value}[/{style}]")
            else:
                label, value = row[0], row[1]
                table.add_row(str(label), str(value))
        self.console.print(Panel(table, title=f"[bold]{title}[/bold]", border_style="cyan"))

    def status_line(self, text: str) -> None:
        """单行状态更新（\r 覆盖式）— 用于运行时进度显示。

        quiet 模式下不显示。保持与 engine_runner 原有实现兼容。

        修复光标乱跳问题：
        - 使用 ANSI 转义序列隐藏光标
        - 正确处理终端刷新
        """
        if self.quiet:
            return

        # ANSI转义序列：
        # \033[?25l - 隐藏光标
        # \r - 回到行首
        # {text} - 显示文本
        # \033[K - 清除到行尾
        # \033[?25h - 显示光标（恢复）
        cursor_hide = "\033[?25l"
        cursor_show = "\033[?25h"
        clear_eol = "\033[K"

        sys.stdout.write(f"{cursor_hide}\r{text}{clear_eol}{cursor_show}")
        sys.stdout.flush()

    def performance_status(self, stats: dict) -> None:
        """性能状态显示，使用单行实时更新。

        Args:
            stats: 性能统计数据，包含以下键:
                - speed: 每秒尝试次数
                - keys_total: 总尝试次数
                - gpu_usage: GPU使用率 (可选)
                - memory_used: 内存使用量 (可选)
        """
        if self.quiet:
            return

        parts = []
        if "speed" in stats:
            parts.append(f"速度: {stats['speed']:,}/s")
        if "keys_total" in stats:
            parts.append(f"总尝试: {stats['keys_total']:,}")
        if "gpu_usage" in stats:
            parts.append(f"GPU: {stats['gpu_usage']}%")
        if "memory_used" in stats:
            parts.append(f"内存: {stats['memory_used']}MB")

        if parts:
            status_text = " | ".join(parts)
            self.status_line(f"[cyan]性能状态:[/cyan] {status_text}")
