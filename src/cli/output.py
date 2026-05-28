"""CLI output formatting utilities."""

import io
import json
import os
import platform
import sys
import threading
from typing import TYPE_CHECKING, Any, cast

from ..utils import get_configured_logger

logger = get_configured_logger(__name__)

if TYPE_CHECKING:
    from rich.console import Console as _RichConsole
    from rich.panel import Panel as _RichPanel
    from rich.table import Table as _RichTable
    from rich.text import Text as _RichText

    Console: type = _RichConsole  # type: ignore[misc]  # in TYPE_CHECKING block
    Panel: type = _RichPanel  # type: ignore[misc]
    Table: type = _RichTable  # type: ignore[misc]
    Text: type = _RichText  # type: ignore[misc]
else:
    try:
        from rich.console import Console as _RichConsole
        from rich.panel import Panel as _RichPanel
        from rich.table import Table as _RichTable
        from rich.text import Text as _RichText

        Console: type = _RichConsole  # type: ignore[misc]  # in try block
        Panel: type = _RichPanel  # type: ignore[misc]
        Table: type = _RichTable  # type: ignore[misc]
        Text: type = _RichText  # type: ignore[misc]
    except ImportError:
        Console = cast("type", None)
        Panel = cast("type", None)
        Table = cast("type", None)
        Text = cast("type", None)


def _get_utf8_console(stderr: bool = False, no_color: bool = False) -> Any:
    """获取 UTF-8 兼容的 Console 实例。."""
    if platform.system() == "Windows":
        # Windows 特殊处理：尝试设置 stdout/stderr 为 utf-8
        try:
            stream: Any = sys.stderr if stderr else sys.stdout
            _reconfigure = getattr(stream, "reconfigure", None)
            if _reconfigure is not None:
                _reconfigure(encoding="utf-8", errors="replace")
        except (OSError, AttributeError, io.UnsupportedOperation) as e:
            logger.debug("Failed to reconfigure stdout/stderr encoding: %s", e)
    # 检查 NO_COLOR 环境变量
    env_no_color = "NO_COLOR" in os.environ
    actual_no_color = no_color or env_no_color
    if Console is not None:
        return Console(no_color=actual_no_color, stderr=stderr)
    # 如果没有安装 rich，返回简单的对象

    class SimpleConsole:
        def __init__(
            self: "SimpleConsole",
            no_color: bool = False,
            stderr: bool = False,
        ) -> None:
            self.no_color: bool = no_color
            self.stderr: bool = stderr

        def print(self: "SimpleConsole", *args: Any, **kwargs: Any) -> None:
            print(*args, **kwargs)

        def rule(self: "SimpleConsole", title: str = "") -> None:
            out = sys.stderr if self.stderr else sys.stdout
            print(title, file=out)

    return SimpleConsole(no_color=actual_no_color, stderr=stderr)


class CLIOutput:
    """CLI 输出管理器单例类。."""

    _instance: "CLIOutput | None" = None
    _instance_lock: threading.Lock = threading.Lock()
    _adaptive_console: Any | None = None  # 缓存用于自适应宽度的 Console 实例

    def __new__(cls, *args: Any, **kwargs: Any) -> "CLIOutput":
        """创建单例实例。."""
        # __new__ 不抢占锁：get_instance() 已在外层加锁，
        # 若此处再次 acquire 同一把 Lock 会导致死锁。
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "CLIOutput":
        """获取单例实例（线程安全）。."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def init(
        cls,
        quiet: bool = False,
        no_color: bool = False,
        compact: bool = False,
    ) -> "CLIOutput":
        """初始化/重置单例（创建全新实例）。."""
        # v5.2.2: 使用 reset_instance 后通过正常构造创建，避免绕过 __new__
        cls.reset_instance()
        instance = cls(quiet=quiet, no_color=no_color, compact=compact)
        return instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（仅用于测试）。."""
        cls._instance = None
        cls._adaptive_console = None

    def __init__(self, quiet: bool = False, no_color: bool = False, compact: bool = False) -> None:
        """初始化 CLI 输出管理器."""
        if getattr(self, "_initialized", False):
            return  # 单例已初始化，跳过
        self._initialized: bool = True
        self.quiet: bool = quiet
        self.compact: bool = compact
        self.console: Any = _get_utf8_console(stderr=False, no_color=no_color)
        self.err_console: Any = _get_utf8_console(stderr=True, no_color=no_color)

    def print(self, message: Any = "", **kwargs: Any) -> None:
        """普通打印（受 quiet 模式影响。."""
        if not self.quiet:
            self.console.print(message, **kwargs)

    def print_always(self, message: Any = "", **kwargs: Any) -> None:
        """总是打印（不受 quiet 影响）。."""
        self.console.print(message, **kwargs)

    def info(self, message: str) -> None:
        """打印 INFO 级别消息。."""
        if not self.quiet:
            if Text is not None:
                self.console.print(Text.assemble(("[INFO] ", "blue"), message))  # type: ignore[attr-defined]
            else:
                self.console.print(f"[INFO] {message}")

    def success(self, message: str) -> None:
        """打印 SUCCESS 级别消息。."""
        if Text is not None:
            self.console.print(Text.assemble(("[OK] ", "green"), message))  # type: ignore[attr-defined]
        else:
            self.console.print(f"[OK] {message}")

    def hint(self, message: str) -> None:
        """打印 HINT 级别消息。."""
        if Text is not None:
            self.console.print(Text.assemble(("[HINT] ", "cyan"), message))  # type: ignore[attr-defined]
        else:
            self.console.print(f"[HINT] {message}")

    def warning(self, message: str, details: str | None = None) -> None:
        """打印 WARNING 级别消息。."""
        if Text is not None:
            self.err_console.print(
                Text.assemble(("[WARN] ", "yellow"), message),  # type: ignore[attr-defined]
            )
        else:
            self.err_console.print(f"[WARN] {message}")
        if details:
            if Text is not None:
                self.err_console.print(Text(details, style="dim"))
            else:
                self.err_console.print(details)

    def error(self, message: str, details: str | None = None) -> None:
        """打印 ERROR 级别消息。."""
        if Text is not None:
            self.err_console.print(Text.assemble(("[ERROR] ", "red"), message))  # type: ignore[attr-defined]
        else:
            self.err_console.print(f"[ERROR] {message}")
        if details:
            if Text is not None:
                self.err_console.print(Text(details, style="dim"))
            else:
                self.err_console.print(details)

    def rule(self, title: str = "", style: str = "dim") -> None:
        """打印分隔线。."""
        if not self.quiet:
            if self.console and hasattr(self.console, "rule"):
                self.console.rule(title, style=style)
            else:
                self.console.print(title)

    def header(self, title: str) -> None:
        """打印标题头。."""
        if not self.quiet:
            if not self.compact:
                self.print()
            self.rule(title, style="bold cyan")
            if not self.compact:
                self.print()

    def startup_panel(
        self,
        title_or_config: str | dict[str, str],
        rows: list[tuple[str, str]] | None = None,
    ) -> None:
        """打印启动配置面板 (Rich Panel + Table)，自适应终端宽度。.

        支持两种调用方式:
            startup_panel("标题", [("key", "value"), ...])  # 新版
            startup_panel({"key": "value", ...})               # 旧版兼容

        Args:
            title_or_config: 面板标题(str) 或 配置字典(dict)
            rows: 可选的行列表

        """
        if self.quiet:
            return

        # 兼容旧版单参数调用：startup_panel(dict_config)
        if isinstance(title_or_config, dict):
            config = title_or_config
            title = "配置"
            rows = [(k, str(v)) for k, v in config.items()]
        else:
            title = title_or_config

        if not rows:
            return
        if Panel is not None and Table is not None:
            from rich.box import ROUNDED

            # 自适应宽度：根据终端宽度计算面板最大宽度
            panel_width = self._adaptive_width()

            table = Table(
                show_header=False,
                box=None,
                padding=(0, 1),
                expand=False,
                width=panel_width - 8 if panel_width else None,
            )
            table.add_column("key", style="dim", width=12)
            table.add_column("value", style="white")
            for k, v in rows:
                table.add_row(f"{k}:", v)
            panel = Panel(
                table,
                title=f"[bold cyan]{title}[/bold cyan]",
                border_style="cyan",
                box=ROUNDED,
                padding=(1, 2),
                width=panel_width,
            )
            self.console.print(panel)
        else:
            self.console.print(f"\n  {title}")
            for k, v in rows:
                self.console.print(f"    {k}: {v}")

    def dynamic_stats_panel(
        self,
        stats: dict[str, str],
        title: str = "System Status",
    ) -> None:
        """打印动态统计面板（自适应宽度）。.

        Args:
            stats: 统计数据字典，key 为标签，value 为值
            title: 面板标题

        """
        if self.quiet or not stats:
            return

        panel_width = self._adaptive_width()
        if Panel is not None and Table is not None:
            from rich.box import ROUNDED

            table = Table(
                show_header=False,
                box=None,
                padding=(0, 1),
                expand=False,
                width=panel_width - 8 if panel_width else None,
            )
            table.add_column("label", style="dim", width=14)
            table.add_column("value", style="white")
            for k, v in stats.items():
                table.add_row(f"  {k}:", v)

            panel = Panel(
                table,
                title=f"[bold cyan]{title}[/bold cyan]",
                border_style="cyan",
                box=ROUNDED,
                padding=(1, 2),
                width=panel_width,
            )
            self.console.print(panel)
        else:
            print(f"\n  {title}")
            for k, v in stats.items():
                print(f"    {k}: {v}")

    @classmethod
    def _adaptive_width(cls) -> int | None:
        """获取自适应面板宽度（缓存 Console 实例）。返回 None 表示不限制。."""
        try:
            if Console is not None:
                con = cls._adaptive_console
                if con is None:
                    con = Console()
                    cls._adaptive_console = con
                if con is not None:
                    w = con.width
                    if w and w > 40:
                        return max(56, min(w - 4, 100))
        except Exception:
            logger.debug("Failed to create adaptive console, using fallback")
        return None

    def final_summary(self, title: str, stats: dict[str, str]) -> None:
        """打印最终摘要（自适应宽度）。."""
        panel_width = self._adaptive_width()
        if Panel is not None and Table is not None:
            table = Table(
                show_header=False,
                box=None,
                width=panel_width - 8 if panel_width else None,
            )
            for k, v in stats.items():
                table.add_row(f"{k}:", str(v))
            panel = Panel(
                table,
                title=f"[bold]{title}[/bold]",
                border_style="green",
                width=panel_width,
            )
            self.console.print(panel)
        else:
            self.console.print(title)
            for k, v in stats.items():
                self.console.print(f"  {k}: {v}")

    def stats_panel(
        self,
        title: str,
        rows: list[tuple[str, str] | tuple[str, str, str]],
    ) -> None:
        """打印统计面板（自适应宽度）。."""
        panel_width = self._adaptive_width()
        if Panel is not None and Table is not None:
            table = Table(
                show_header=False,
                box=None,
                width=panel_width - 8 if panel_width else None,
            )
            for row in rows:
                if len(row) == 3:
                    k, v, style = row
                    if Text is not None:
                        table.add_row(f"{k}:", Text(str(v), style=style))
                    else:
                        table.add_row(f"{k}:", str(v))
                elif len(row) == 2:
                    k, v = row
                    table.add_row(f"{k}:", str(v))
            panel = Panel(
                table,
                title=f"[bold]{title}[/bold]",
                border_style="blue",
                width=panel_width,
            )
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

    def status_line(self, text: str) -> None:
        """打印状态行（覆盖式）。."""
        if not self.quiet:
            _ = sys.stdout.write(f"\r{text}")
            sys.stdout.flush()

    def performance_status(self, stats: dict[str, str | int | float]) -> None:
        """打印性能状态行。."""
        if not self.quiet and stats:
            parts: list[str] = []
            if "speed" in stats:
                speed = stats["speed"]
                if isinstance(speed, (int, float)):
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


def format_results(results: list[dict[str, str]]) -> str:
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


def format_json(data: object) -> str:
    """Format data as pretty JSON.

    Args:
        data: Data to format

    Returns:
        Pretty JSON string

    """
    return json.dumps(data, indent=2, default=str)


def paginate(  # noqa: C901
    lines: list[str],
    *,
    title: str = "",
    page_size: int = 20,
    console: Any = None,
) -> None:
    """Display long content with page-by-page navigation.

    Shows *page_size* lines at a time, prompting user to continue.
    Uses Rich Console if available, falls back to plain print.

    In non-interactive environments (pytest capture, piped stdin), all content
    is printed at once without pausing.

    Args:
        lines: Content lines to display.
        title: Optional header shown above each page.
        page_size: Lines per page (default 20).
        console: Optional Rich Console instance. If None, uses _get_utf8_console().

    """
    if not lines:
        return

    # 检测是否处于非交互式环境（测试、管道等），如果是则跳过分页暂停
    import sys as _sys

    def _is_interactive() -> bool:
        try:
            return _sys.stdin.isatty()
        except Exception as e:
            logger.debug("Failed to check stdin interactivity: %s", e)
            return False

    interactive = _is_interactive()

    # 尝试获取 Rich Console
    _con = console
    if _con is None:
        try:
            from rich.console import Console as _RC  # noqa: N814

            _con = _RC()
        except Exception as e:
            logger.debug("Failed to create Rich Console for pagination: %s", e)
            _con = None

    total = len(lines)

    # 非交互模式或内容不超过一页：直接全部显示
    if not interactive or total <= page_size:
        if _con is not None:
            if title:
                _con.print(f"[bold dim]-- {title} --[/bold dim]")
            for line in lines:
                _con.print(line)
        else:
            if title:
                print(f"-- {title} --")
            for line in lines:
                print(line)
        return

    # 交互模式 + 需要分页
    for start in range(0, total, page_size):
        chunk = lines[start : start + page_size]
        current_page = start // page_size + 1
        total_pages = (total + page_size - 1) // page_size

        if _con is not None:
            if title:
                _con.print(
                    f"[bold dim]-- {title} (Page {current_page}/{total_pages}) --[/bold dim]",
                )
            else:
                _con.print(
                    f"[bold dim]-- Page {current_page}/{total_pages} --[/bold dim]",
                )
            for line in chunk:
                _con.print(line)
            footer = f"[dim]({total} total lines, press Enter for next, q=quit)[/dim]"
            _con.print(footer)
        else:
            if title:
                print(f"-- {title} (Page {current_page}/{total_pages}) --")
            else:
                print(f"-- Page {current_page}/{total_pages} --")
            for line in chunk:
                print(line)
            print(f"--- ({total} total lines) ---")

        # 最后一页后不需要暂停
        if start + page_size < total:
            try:
                _ = input("   Press Enter to continue (q=quit)...")
            except (EOFError, KeyboardInterrupt):
                break
