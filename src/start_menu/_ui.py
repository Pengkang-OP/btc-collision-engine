"""启动菜单 UI 组件 — 渲染、子菜单、横幅."""

import os
import shutil
import subprocess
from pathlib import Path

from ._i18n import _t
from ._shared import (  # type: ignore[attr-defined]
    _PROJECT_ROOT,
    _PYTHON_EXE,
    _console,
    _has_rich,
    _RichPanel,
    _RichText,
)
from ._utils import (
    _clear_screen,
    _collect_dynamic_stats,
    _term_width,
    _wait_key,
)

# ── 子菜单 Rich 渲染 ────────────────────────────────────────────


def _show_cleanup_menu_rich() -> None:
    assert _console is not None
    pw = max(46, _term_width() - 10)
    opts = _RichText()
    opts.append("  1. ", style="bold white")
    opts.append("Clear log files\n", style="white")
    opts.append("  2. ", style="bold white")
    opts.append("Clear checkpoint files\n", style="white")
    opts.append("  3. ", style="bold white")
    opts.append("Clear ALL temporary files", style="yellow")
    opts.append("  [DANGEROUS]", style="dim red italic")
    opts.append("\n  0. ", style="bold white")
    opts.append("Back", style="red")
    panel = _RichPanel(
        opts,
        title="[bold yellow]Maintenance & Cleanup[/bold yellow]",
        border_style="yellow",
        width=pw,
        padding=(1, 2),
    )
    _console.print(panel)
    _console.print()


def _show_cleanup_menu_plain() -> None:
    print()
    print("=" * 64)
    print(f"          {_t('menu.cleanup_title')}")
    print("=" * 64)
    print()
    print(_t("menu.cleanup_option_1"))
    print(_t("menu.cleanup_option_2"))
    print(_t("menu.cleanup_option_3"))
    print(_t("menu.cleanup_back"))
    print()
    print("=" * 64)
    print()


def _show_monitor_menu_rich() -> None:
    assert _console is not None
    pw = max(44, _term_width() - 12)
    opts = _RichText()
    opts.append("  1. ", style="bold white")
    opts.append("Basic Monitoring (CPU mode)\n", style="white")
    opts.append("  2. ", style="bold white")
    opts.append("GPU Monitoring\n", style="white")
    opts.append("  3. ", style="bold white")
    opts.append("Monitoring + Report\n", style="white")
    opts.append("  0. ", style="bold white")
    opts.append("Back", style="red")
    panel = _RichPanel(
        opts,
        title="[bold blue]Monitoring[/bold blue]",
        border_style="blue",
        width=pw,
        padding=(1, 2),
    )
    _console.print(panel)
    _console.print()


def _show_monitor_menu_plain() -> None:
    print()
    print("=" * 64)
    print(f"          {_t('menu.monitor_title')}")
    print("=" * 64)
    print()
    print(_t("menu.monitor_option_1"))
    print(_t("menu.monitor_option_2"))
    print(_t("menu.monitor_option_3"))
    print(_t("menu.monitor_back"))
    print()
    print("=" * 64)
    print()


# ── 清理子菜单 ────────────────────────────────────────────────


def cleanup_menu() -> bool:
    while True:
        _clear_screen()
        if _has_rich and _console is not None:
            _show_cleanup_menu_rich()
        else:
            _show_cleanup_menu_plain()
        try:
            choice = input(_t("menu.cleanup_enter_option")).strip()
        except (EOFError, KeyboardInterrupt):
            return False
        if not choice:
            continue
        if choice == "1":
            print(_t("menu.cleanup_clearing_logs"))
            deleted = 0
            for pattern in ("*.log", "*.log.*"):
                for f in Path(_PROJECT_ROOT).rglob(pattern):
                    try:
                        f.unlink()
                        deleted += 1
                    except OSError:
                        pass
            print(_t("menu.cleanup_deleted", count=deleted))
            _wait_key()
        elif choice == "2":
            print(_t("menu.cleanup_clearing_checkpoints"))
            deleted = 0
            for pattern in ("*.ckpt", "*.checkpoint", "*.pkl"):
                for f in Path(_PROJECT_ROOT).rglob(pattern):
                    if f.name in (
                        "config.json",
                        "config.example.json",
                        "config.schema.json",
                        "package.json",
                        "pyproject.toml",
                    ):
                        continue
                    try:
                        f.unlink()
                        deleted += 1
                    except OSError:
                        pass
            print(_t("menu.cleanup_deleted", count=deleted))
            _wait_key()
        elif choice == "3":
            print()
            print(_t("menu.cleanup_warning"))
            print()
            try:
                confirm = input(_t("menu.cleanup_confirm")).strip().upper()
            except (EOFError, KeyboardInterrupt):
                print(_t("menu.cleanup_cancelled"))
                _wait_key()
                continue
            if confirm != "Y":
                print(_t("menu.cleanup_cancelled"))
                _wait_key()
                continue
            total_deleted = 0
            for pattern in ("*.log", "*.log.*"):
                for f in Path(_PROJECT_ROOT).rglob(pattern):
                    try:
                        f.unlink()
                        total_deleted += 1
                    except OSError:
                        pass
            for pattern in ("*.ckpt", "*.checkpoint", "*.pkl"):
                for f in Path(_PROJECT_ROOT).rglob(pattern):
                    try:
                        f.unlink()
                        total_deleted += 1
                    except OSError:
                        pass
            pycache_dirs = [p for p in Path(_PROJECT_ROOT).rglob("__pycache__") if p.is_dir()]
            for p in pycache_dirs:
                try:
                    for f in p.rglob("*"):
                        if f.is_file():
                            total_deleted += 1
                    shutil.rmtree(str(p), ignore_errors=True)
                except OSError:
                    pass
            for f in Path(_PROJECT_ROOT).rglob("*.lock"):
                try:
                    f.unlink()
                    total_deleted += 1
                except OSError:
                    pass
            print(_t("menu.cleanup_deleted", count=total_deleted))
            print(_t("menu.cleanup_all_done"))
            _wait_key()
        elif choice == "0":
            return False
        else:
            print(_t("menu.invalid_option", choice=choice))
            _wait_key()
    return False


# ── 监控子菜单 ─────────────────────────────────────────────────


def monitoring_menu() -> bool:
    while True:
        _clear_screen()
        if _has_rich and _console is not None:
            _show_monitor_menu_rich()
        else:
            _show_monitor_menu_plain()
        try:
            choice = input(_t("menu.monitor_enter_option")).strip()
        except (EOFError, KeyboardInterrupt):
            return False
        if not choice:
            continue
        monitor_script = os.path.join(_PROJECT_ROOT, "start_monitoring.py")
        if not os.path.isfile(monitor_script):
            print(_t("menu.monitor_not_found"))
            _wait_key()
            return False
        if choice == "1":
            print(_t("menu.monitor_starting_cpu"))
            subprocess.run(
                [_PYTHON_EXE, "start_monitoring.py", "--mode", "cpu"],
                cwd=_PROJECT_ROOT,
                check=False,
            )
            _wait_key()
        elif choice == "2":
            print(_t("menu.monitor_starting_gpu"))
            subprocess.run(
                [_PYTHON_EXE, "start_monitoring.py", "--mode", "gpu"],
                cwd=_PROJECT_ROOT,
                check=False,
            )
            _wait_key()
        elif choice == "3":
            print(_t("menu.monitor_starting_report"))
            subprocess.run(
                [_PYTHON_EXE, "start_monitoring.py", "--mode", "cpu", "--report"],
                cwd=_PROJECT_ROOT,
                check=False,
            )
            _wait_key()
        elif choice == "0":
            return False
        else:
            print(_t("menu.invalid_option", choice=choice))
            _wait_key()
    return False


# ── 横幅显示 ──────────────────────────────────────────────────


def _show_banner() -> None:
    _clear_screen()
    venv_ok = os.path.isfile(
        os.path.join(_PROJECT_ROOT, "venv", "Scripts", "activate.bat"),
    ) or os.path.isfile(os.path.join(_PROJECT_ROOT, "venv", "bin", "activate"))
    targets_ok = os.path.isfile(os.path.join(_PROJECT_ROOT, "targets.txt"))
    if _has_rich and _console is not None:
        _show_banner_rich(venv_ok, targets_ok)
    else:
        _show_banner_plain(venv_ok, targets_ok)


def _show_banner_rich(venv_ok: bool, targets_ok: bool) -> None:
    assert _console is not None
    pw = _term_width()
    dyn = _collect_dynamic_stats()
    venv_tag = "[green]Found[/green]" if venv_ok else "[yellow]Not Found[/yellow]"
    tgt_tag = "[green]Found[/green]" if targets_ok else "[yellow]Not Found[/yellow]"
    lines: list[str] = []
    lines.append("")
    lines.append(f"  [dim]Virtual Env:[/dim]       {venv_tag}")
    lines.append(f"  [dim]Targets File:[/dim]      {tgt_tag}")
    if "target_count" in dyn:
        lines.append(f"  [dim]Addresses:[/dim]         [cyan]{dyn['target_count']}[/cyan]")
    if "target_size" in dyn:
        lines.append(f"  [dim]File Size:[/dim]         [dim]{dyn['target_size']}[/dim]")
    if "gpu" in dyn:
        lines.append(f"  [dim]GPU:[/dim]               [green]{dyn['gpu']}[/green]")
    if "log_files" in dyn:
        lines.append(f"  [dim]Log Files:[/dim]         [dim]{dyn['log_files']}[/dim]")
    if "python" in dyn:
        lines.append(f"  [dim]Python:[/dim]            [dim]{dyn['python']}[/dim]")
    lines.append("")
    sep_len = max(0, min(pw - 10, 44))
    lines.append(f"  [bold dim]{'─' * sep_len} Options {'─' * sep_len}[/bold dim]")
    lines.append("")
    options = [
        ("1", "Interactive Wizard", "cyan", True),
        ("2", "GPU Mode (Single GPU)", "white", False),
        ("3", "Start Monitoring", "white", False),
        ("4", "Maintenance & Cleanup", "white", False),
        ("5", "Show Help", "white", False),
        ("6", "Multi-GPU Mode", "white", False),
        ("0", "Exit", "red", False),
    ]
    for num, label, color, recommended in options:
        if recommended:
            lines.append(
                f"  [bold]{num}.[/bold] [{color} bold]{label}[/{color} bold] "
                "[dim italic][Recommended][/dim italic]",
            )
        else:
            lines.append(f"  [bold]{num}.[/bold] [{color}]{label}[/{color}]")
    content = "\n".join(lines)
    panel = _RichPanel(
        content,
        title="[bold cyan]BTC Collision Engine[/bold cyan]",
        subtitle="[dim]Startup Menu[/dim]",
        border_style="cyan",
        width=pw,
        padding=(1, 2),
    )
    _console.print(panel)
    _console.print()


def _show_banner_plain(venv_ok: bool, targets_ok: bool) -> None:
    print()
    print("=" * 64)
    print(f"          {_t('menu.title')}")
    print("=" * 64)
    print()
    print(_t("menu.system_status"))
    if venv_ok:
        print(_t("menu.venv_found"))
    else:
        print(_t("menu.venv_not_found"))
    if targets_ok:
        print(_t("menu.targets_found"))
    else:
        print(_t("menu.targets_not_found"))
    print()
    print(_t("menu.prompt"))
    print()
    print(_t("menu.option_1"))
    print(_t("menu.option_2"))
    print(_t("menu.option_3"))
    print(_t("menu.option_4"))
    print(_t("menu.option_5"))
    print(_t("menu.option_6"))
    print(_t("menu.option_exit"))
    print()
    print("=" * 64)
    print()


# ── CLI 运行器 ────────────────────────────────────────────────


def _run_cli(args: list[str], label: str = "") -> int:
    if _has_rich and _console is not None:
        _console.print(
            _RichPanel(
                f"[dim]Launching... {label}[/dim]" if label else "[dim]Launching...[/dim]",
                title="[bold cyan]BTC Collision Engine[/bold cyan]",
                border_style="dim",
                width=_term_width(),
            ),
        )
        _console.print()
    try:
        result = subprocess.run(
            [_PYTHON_EXE, "key_collision_cli.py", *args],
            cwd=_PROJECT_ROOT,
            check=False,
        )
        return result.returncode
    except KeyboardInterrupt:
        print(f"\n  [Interrupted] {label}" if label else "\n  [Interrupted]")
        return -1
    except Exception as exc:
        print(f"\n  [ERROR] {exc}")
        return -1
