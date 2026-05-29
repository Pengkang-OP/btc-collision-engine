"""Web dashboard package.

Provides a Flask-based web monitoring dashboard for the BTC collision engine.
"""

from __future__ import annotations

from pathlib import Path

# pyright: reportImportCycles=false
from src import __version__ as __version__  # noqa: F401

__all__ = ["create_app", "run_dashboard"]


def create_app(data_dir: Path | None = None, debug: bool = False) -> object:
    """Create a Flask app (lazy import for web dashboard).

    Returns:
        Flask application instance if Flask is available.

    Raises:
        ImportError: If Flask is not installed.
    """
    try:
        from .dashboard import create_app as _app
    except ImportError as e:
        raise ImportError("Flask is not installed. Install with: pip install flask") from e
    return _app(data_dir, debug)


def run_dashboard(
    host: str = "0.0.0.0",  # nosec B104
    port: int = 8080,
    data_dir: str | None = None,
    debug: bool = False,
    use_reloader: bool = False,
    api_key: str | None = None,
) -> None:
    """Run the web dashboard (lazy import for web dashboard).

    Args:
        host: Host to bind to.
        port: Port to bind to.
        data_dir: Data directory path.
        debug: Enable debug mode.
        use_reloader: Enable auto-reloader.
        api_key: API key for authentication.

    Raises:
        ImportError: If Flask is not installed.
    """
    try:
        from .dashboard import run_dashboard as _run_dashboard
    except ImportError as e:
        raise ImportError("Flask is not installed. Install with: pip install flask") from e
    _run_dashboard(host, port, data_dir, debug, use_reloader, api_key)


__all__ = ["create_app", "run_dashboard"]
