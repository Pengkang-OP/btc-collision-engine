"""启动菜单共享模块状态 — Rich 检测、Console 实例、项目根目录、Python 路径."""

import os
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)

try:
    from rich.console import Console as _RichConsole
    from rich.panel import Panel as _RichPanel
    from rich.text import Text as _RichText

    _has_rich = True
except ImportError:
    _RichConsole = None  # type: ignore[assignment, misc]
    _RichPanel = None  # type: ignore[assignment, misc]
    _RichText = None  # type: ignore[assignment, misc]
    _has_rich = False

if _has_rich:
    try:
        _reconfigure = getattr(sys.stdout, "reconfigure", None)
        if _reconfigure is not None:
            _reconfigure(
                encoding="utf-8",
                errors="replace",
            )
        assert _RichConsole is not None
        _console = _RichConsole()
    except Exception:
        _console = None  # type: ignore[assignment]
else:
    _console = None  # type: ignore[assignment]


def _venv_python() -> str:
    candidates = [
        os.path.join(_PROJECT_ROOT, "venv", "Scripts", "python.exe"),
        os.path.join(_PROJECT_ROOT, "venv", "bin", "python"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return sys.executable


_PYTHON_EXE = _venv_python()
