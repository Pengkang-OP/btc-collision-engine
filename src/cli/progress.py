r"""Progress display utilities for CLI.

Uses rich.live.Live for smooth real-time stats display
without the flicker of \r overwrite approach.
"""

import time

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..utils import get_configured_logger

# ── formatting helpers ─────────────────────────────────────────


def _fmt_speed(speed: float) -> str:
    """Format speed with human-readable unit."""
    if speed <= 0:
        return "      --  "
    if speed >= 1_000_000:
        return f"{speed / 1_000_000:.2f} M/s"
    if speed >= 1_000:
        return f"{speed / 1_000:.1f} K/s"
    return f"{speed:.0f}/s      "


def _fmt_keys(n: int) -> str:
    """Format large key count compactly."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}G"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n // 1000}K"
    return str(n)


def _fmt_elapsed(seconds: float) -> str:
    """Format elapsed time compactly."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m{s}s"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h{m}m"


def format_progress(
    keys_checked: int,
    speed: float,
    matches: int,
    elapsed: float,
) -> str:
    """Format a one-line progress string (legacy, for non-rich fallback).

    Returns:
        Compact single-line progress string

    """
    k = _fmt_keys(keys_checked)
    sp = _fmt_speed(speed)
    t = _fmt_elapsed(elapsed)
    return f" {k:>9s}  {sp:>10s}  hit:{matches:<4d}  {t}"


logger = get_configured_logger(__name__)

# ── Rich Live display ──────────────────────────────────────────


def create_stats_table(
    keys_checked: int,
    speed: float,
    matches: int,
    elapsed: float,
    engine_type: str = "GPU",
    gpu_info: str = "",
) -> Table:
    """Build a Rich Table for live stats display.

    Args:
        keys_checked: total keys tried
        speed: keys/sec
        matches: matches found
        elapsed: seconds since start
        engine_type: 'CPU' / 'GPU' / 'MultiGPU'
        gpu_info: optional extra GPU field (e.g. "65C 38%")

    Returns:
        Rich Table ready for Live display

    """
    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=None,  # clean, no borders
        padding=(0, 2),  # compact
    )

    table.add_column("Keys", justify="right", style="white")
    table.add_column("Speed", justify="right", style="green")
    table.add_column("Hit", justify="center", style="yellow")
    table.add_column("Time", justify="right", style="dim")

    if gpu_info:
        table.add_column("GPU", justify="right", style="magenta")

    if gpu_info:
        table.add_row(
            _fmt_keys(keys_checked),
            _fmt_speed(speed),
            f"[bold yellow]{matches}[/]",
            f"[dim]{_fmt_elapsed(elapsed)}[/]",
            gpu_info,
        )
    else:
        table.add_row(
            _fmt_keys(keys_checked),
            _fmt_speed(speed),
            f"[bold yellow]{matches}[/]",
            f"[dim]{_fmt_elapsed(elapsed)}[/]",
        )

    return table


class LiveStatsDisplay:
    """Manages a Rich Live display for collision engine stats.

    Usage:
        display = LiveStatsDisplay(engine_type="GPU")
        display.start()
        while running:
            display.update(keys=..., speed=..., matches=..., elapsed=...)
        display.stop()
    """

    def __init__(
        self,
        engine_type: str = "GPU",
        description: str = "",
        refresh_rate: float = 4,
    ):
        """Initialize the progress display."""
        self.engine_type = engine_type
        self.description = description or f"{engine_type} 引擎运行中"
        self.refresh_rate = refresh_rate
        self._live: Live | None = None
        self._started = False

    def start(self) -> None:
        """Open the live display context."""
        panel = Panel(
            Text(self.description, style="bold cyan"),
            title="BTC Collision Engine",
            border_style="cyan",
            subtitle="[q] quit  [Ctrl+C] stop",
        )
        self._live = Live(
            panel,
            refresh_per_second=self.refresh_rate,
            transient=False,
            vertical_overflow="crop",
        )
        self._live.__enter__()
        self._started = True

    def update(
        self,
        keys_checked: int = 0,
        speed: float = 0,
        matches: int = 0,
        elapsed: float = 0,
        gpu_info: str = "",
    ) -> None:
        """Update the live display with latest stats."""
        if not self._live or not self._started:
            return

        try:
            table = create_stats_table(
                keys_checked,
                speed,
                matches,
                elapsed,
                self.engine_type,
                gpu_info,
            )

            # Add a hit-highlight when matches found
            if matches > 0:
                hit_alert = Text(f"  Matches Found: {matches}  ", style="bold yellow on red")
                content = Group(table, hit_alert)
            else:
                content = table

            panel = Panel(
                content,
                title="BTC Collision Engine",
                border_style="cyan" if matches == 0 else "bold yellow",
                subtitle=f"[dim]{self.description}[/]  [dim][q] quit[/]",
            )
            self._live.update(panel)
        except Exception:
            logger.debug("Live display update failed (non-fatal)")

    def stop(self) -> None:
        """Close the live display context."""
        if self._live and self._started:
            try:
                self._live.__exit__(None, None, None)
            except Exception:
                logger.debug("Live display exit failed (non-fatal)")
        self._started = False


# ── legacy ProgressBar class ───────────────────────────────────


class ProgressBar:
    """Simple progress bar for CLI display (legacy)."""

    def __init__(self, total: int, width: int = 40) -> None:
        """Initialize the simple progress bar."""
        self.total = total
        self.width = width
        self._start = time.time()

    def update(self, current: int) -> None:
        """Update progress bar display."""
        if self.total <= 0:
            return
        ratio = min(current / self.total, 1.0)
        filled = int(self.width * ratio)
        bar = "#" * filled + "-" * (self.width - filled)
        elapsed = time.time() - self._start
        print(f"\r[{bar}] {ratio:.1%}  {elapsed:.0f}s", end="", flush=True)
