"""Web dashboard package.

Provides a Flask-based web monitoring dashboard for the BTC collision engine.
"""
__version__ = "5.0.0"

try:
    from src.web.dashboard import create_app, run_dashboard

    __all__ = ["create_app", "run_dashboard"]
except ImportError:
    # Flask not available – web dashboard is optional
    __all__ = ["create_app", "run_dashboard"]

    def create_app(*args, **kwargs):  # pragma: no cover
        raise ImportError(
            "Flask is not installed. Install with: pip install flask"
        )

    def run_dashboard(*args, **kwargs):  # pragma: no cover
        raise ImportError(
            "Flask is not installed. Install with: pip install flask"
        )
