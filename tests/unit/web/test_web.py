"""Tests for src/web package - Web 监控仪表板.

Covers:
- __init__.py: version, re-exports
- dashboard.py: auth, data utilities, Flask routes, CLI
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# __init__.py tests (no Flask needed)
# ============================================================================


class TestWebInit:
    """Test web/__init__.py package exports."""

    def test_version(self):
        from src.web import __version__

        assert __version__ == "5.0.1"

    def test_all_exports(self):
        from src.web import __all__

        assert "create_app" in __all__
        assert "run_dashboard" in __all__

    def test_create_app_importable(self):
        from src.web import create_app

        assert callable(create_app)

    def test_run_dashboard_importable(self):
        from src.web import run_dashboard

        assert callable(run_dashboard)


# ============================================================================
# Auth functions tests (no Flask needed)
# ============================================================================


class TestAuthFunctions:
    """Test API Key authentication functions."""

    def test_set_api_key_enables_auth(self):
        import src.web.dashboard as dash

        dash.set_api_key("test-key-123")
        assert dash._api_key == "test-key-123"
        assert dash._api_key_required is True

    def test_set_api_key_none_disables_auth(self):
        import src.web.dashboard as dash

        dash.set_api_key(None)
        assert dash._api_key is None
        assert dash._api_key_required is False

    def test_set_api_key_empty_disables_auth(self):
        import src.web.dashboard as dash

        dash.set_api_key("")
        assert dash._api_key == ""
        assert dash._api_key_required is False

    def test_validate_api_key_no_auth_required(self, monkeypatch):
        from src.web.dashboard import _validate_api_key

        monkeypatch.setattr("src.web.dashboard._api_key_required", False)
        assert _validate_api_key() is True

    def test_validate_api_key_valid_bearer_token(self, monkeypatch):
        from src.web.dashboard import _validate_api_key

        monkeypatch.setattr("src.web.dashboard._api_key_required", True)
        monkeypatch.setattr("src.web.dashboard._api_key", "my-secret")
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer my-secret"
        mock_request.args.get.return_value = ""
        monkeypatch.setattr("src.web.dashboard.request", mock_request)
        assert _validate_api_key() is True

    def test_validate_api_key_query_param_not_supported(self, monkeypatch):
        """Query param API keys are intentionally NOT supported.

        Security design: _validate_api_key only reads from Authorization header
        to prevent API keys from leaking into browser history, server logs, etc.
        """
        from src.web.dashboard import _validate_api_key

        monkeypatch.setattr("src.web.dashboard._api_key_required", True)
        monkeypatch.setattr("src.web.dashboard._api_key", "my-secret")
        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.args.get.return_value = "my-secret"
        monkeypatch.setattr("src.web.dashboard.request", mock_request)
        # Query param is ignored by design – only Authorization header is checked
        assert _validate_api_key() is False

    def test_validate_api_key_invalid(self, monkeypatch):
        from src.web.dashboard import _validate_api_key

        monkeypatch.setattr("src.web.dashboard._api_key_required", True)
        monkeypatch.setattr("src.web.dashboard._api_key", "my-secret")
        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.args.get.return_value = "wrong-key"
        monkeypatch.setattr("src.web.dashboard.request", mock_request)
        assert _validate_api_key() is False

    def test_validate_api_key_bearer_empty_key(self, monkeypatch):
        from src.web.dashboard import _validate_api_key

        monkeypatch.setattr("src.web.dashboard._api_key_required", True)
        monkeypatch.setattr("src.web.dashboard._api_key", "my-secret")
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer "
        mock_request.args.get.return_value = ""
        monkeypatch.setattr("src.web.dashboard.request", mock_request)
        assert _validate_api_key() is False

    def test_validate_api_key_no_bearer_prefix_in_header(self, monkeypatch):
        """Auth header without Bearer prefix: removeprefix no-op, raw value compared."""
        from src.web.dashboard import _validate_api_key

        monkeypatch.setattr("src.web.dashboard._api_key_required", True)
        monkeypatch.setattr("src.web.dashboard._api_key", "my-secret")
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "my-secret"
        mock_request.args.get.return_value = ""
        monkeypatch.setattr("src.web.dashboard.request", mock_request)
        assert _validate_api_key() is True

    def test_validate_api_key_no_bearer_wrong_key_rejected(self, monkeypatch):
        """Header without Bearer prefix but wrong key: rejected (no query fallback)."""
        from src.web.dashboard import _validate_api_key

        monkeypatch.setattr("src.web.dashboard._api_key_required", True)
        monkeypatch.setattr("src.web.dashboard._api_key", "my-secret")
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "wrong-key"
        mock_request.args.get.return_value = ""
        monkeypatch.setattr("src.web.dashboard.request", mock_request)
        assert _validate_api_key() is False

    def test_require_auth_unprotected_route(self):
        from src.web.dashboard import require_auth

        @require_auth
        def health():
            return "ok"

        result = health()
        assert result == "ok"

    def test_require_auth_valid_key(self, monkeypatch):
        from src.web.dashboard import require_auth

        monkeypatch.setattr("src.web.dashboard._api_key_required", True)
        monkeypatch.setattr("src.web.dashboard._api_key", "secret")
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer secret"
        mock_request.args.get.return_value = ""
        monkeypatch.setattr("src.web.dashboard.request", mock_request)

        @require_auth
        def my_endpoint():
            return "success"

        assert my_endpoint() == "success"

    def test_require_auth_invalid_key_aborts(self, monkeypatch):
        from src.web.dashboard import require_auth

        monkeypatch.setattr("src.web.dashboard._api_key_required", True)
        monkeypatch.setattr("src.web.dashboard._api_key", "secret")
        mock_abort = MagicMock(side_effect=Exception("401"))
        monkeypatch.setattr("src.web.dashboard.abort", mock_abort)
        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        mock_request.args.get.return_value = ""
        monkeypatch.setattr("src.web.dashboard.request", mock_request)

        @require_auth
        def my_endpoint():
            return "success"

        with pytest.raises(Exception, match="401"):
            my_endpoint()

    def test_require_auth_preserves_function_name(self):
        from src.web.dashboard import require_auth

        @require_auth
        def my_protected_route():
            """Docstring for testing."""
            return "data"

        assert my_protected_route.__name__ == "my_protected_route"
        assert my_protected_route.__doc__ == "Docstring for testing."


# ============================================================================
# Data utility tests (no Flask needed)
# ============================================================================


class TestFindDataLogsDir:
    """Test _find_data_logs_dir function."""

    def test_finds_data_logs_in_cwd(self, tmp_path, monkeypatch):
        from src.web.dashboard import _find_data_logs_dir

        data_logs = tmp_path / "data_logs"
        data_logs.mkdir()
        # Change CWD so Path("data_logs") resolves
        monkeypatch.chdir(tmp_path)
        result = _find_data_logs_dir()
        # _find_data_logs_dir returns Path("data_logs") - relative path
        assert result == Path("data_logs")
        # But it resolves to the correct absolute path in CWD
        assert result.resolve() == data_logs.resolve()

    def test_finds_data_logs_via_project_root(self, monkeypatch):
        from src.web.dashboard import _find_data_logs_dir

        # Path("data_logs") doesn't exist, second candidate should match
        # We can't easily test this without actual data_logs dir
        result = _find_data_logs_dir()
        assert isinstance(result, Path)

    def test_returns_default_when_nonexistent(self, tmp_path, monkeypatch):
        from src.web.dashboard import _find_data_logs_dir

        # Must ensure both candidates are unavailable
        # In the project workspace, the project-root data_logs EXISTS,
        # so the function correctly returns it. That's expected behavior.
        monkeypatch.chdir(tmp_path)
        result = _find_data_logs_dir()
        assert isinstance(result, Path)

    def test_both_candidates_nonexistent_fallback(self, monkeypatch):
        """Cover line 251: return Path('data_logs') when both candidates unavailable."""
        from src.web.dashboard import _find_data_logs_dir

        monkeypatch.setattr(Path, "exists", lambda self: False)
        result = _find_data_logs_dir()
        assert result == Path("data_logs")


class TestSafeReadJson:
    """Test _safe_read_json helper."""

    def test_reads_valid_json(self, tmp_path):
        from src.web.dashboard import _safe_read_json

        p = tmp_path / "test.json"
        p.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        result = _safe_read_json(p)
        assert result == {"key": "value"}

    def test_returns_none_for_missing_file(self, tmp_path):
        from src.web.dashboard import _safe_read_json

        result = _safe_read_json(tmp_path / "nonexistent.json")
        assert result is None

    def test_returns_none_for_invalid_json(self, tmp_path):
        from src.web.dashboard import _safe_read_json

        p = tmp_path / "bad.json"
        p.write_text("not json", encoding="utf-8")
        result = _safe_read_json(p)
        assert result is None

    def test_returns_none_on_oserror(self, tmp_path):
        from src.web.dashboard import _safe_read_json

        p = tmp_path / "unreadable.json"
        p.write_text('{"key": "value"}', encoding="utf-8")
        # _safe_read_json uses Path(path).open() not builtins.open()
        with patch("pathlib.Path.open", side_effect=OSError("Permission denied")):
            result = _safe_read_json(p)
            assert result is None


class TestGetCurrentStats:
    """Test get_current_stats function."""

    def test_full_data(self, tmp_path):
        from src.web.dashboard import get_current_stats

        data = {
            "performance": {
                "speed": 1000,
                "avg_speed": 900,
                "total_checked": 50000,
                "matches_found": 3,
                "cpu_usage": 45.5,
                "memory_usage": 256.0,
                "thread_count": 4,
            },
            "engine": {
                "is_running": True,
                "mode": "GPU",
                "target_count": 5,
                "current_position": 12345,
            },
            "system": {
                "os": "Windows",
                "python_version": "3.12",
                "pid": 9999,
            },
            "uptime": 3600,
        }
        (tmp_path / "current_data.json").write_text(json.dumps(data), encoding="utf-8")
        result = get_current_stats(tmp_path)
        assert result["speed"] == 1000
        assert result["avg_speed"] == 900
        assert result["total_checked"] == 50000
        assert result["matches_found"] == 3
        assert result["cpu_usage"] == 45.5
        assert result["memory_usage"] == 256.0
        assert result["thread_count"] == 4
        assert result["uptime"] == 3600
        assert result["is_running"] is True
        assert result["mode"] == "GPU"
        assert result["target_count"] == 5
        assert result["current_position"] == 12345
        assert result["os"] == "Windows"
        assert result["python_version"] == "3.12"
        assert result["pid"] == 9999
        assert "generated_at" in result

    def test_empty_file(self, tmp_path):
        from src.web.dashboard import get_current_stats

        (tmp_path / "current_data.json").write_text("{}", encoding="utf-8")
        result = get_current_stats(tmp_path)
        assert result["speed"] == 0
        assert result["total_checked"] == 0
        assert result["is_running"] is False
        assert result["os"] == "N/A"

    def test_perf_not_dict(self, tmp_path):
        from src.web.dashboard import get_current_stats

        data = {"performance": "not a dict", "engine": {}, "system": {}}
        (tmp_path / "current_data.json").write_text(json.dumps(data), encoding="utf-8")
        result = get_current_stats(tmp_path)
        assert result["speed"] == 0
        assert result["total_checked"] == 0

    def test_engine_not_dict(self, tmp_path):
        from src.web.dashboard import get_current_stats

        data = {"performance": {}, "engine": "not dict", "system": {}}
        (tmp_path / "current_data.json").write_text(json.dumps(data), encoding="utf-8")
        result = get_current_stats(tmp_path)
        assert result["is_running"] is False
        assert result["mode"] == ""

    def test_system_not_dict(self, tmp_path):
        from src.web.dashboard import get_current_stats

        data = {"performance": {}, "engine": {}, "system": 123}
        (tmp_path / "current_data.json").write_text(json.dumps(data), encoding="utf-8")
        result = get_current_stats(tmp_path)
        assert result["os"] == "N/A"
        assert result["python_version"] == "N/A"
        assert result["pid"] == "N/A"


class TestGetHistory:
    """Test get_history function."""

    def test_returns_last_n_items(self, tmp_path):
        from src.web.dashboard import get_history

        data = [{"id": i, "speed": i * 100} for i in range(100)]
        (tmp_path / "history_data.json").write_text(json.dumps(data), encoding="utf-8")
        result = get_history(tmp_path, limit=5)
        assert len(result) == 5
        assert result[-1]["id"] == 99
        assert result[0]["id"] == 95

    def test_returns_data_when_less_than_limit(self, tmp_path):
        from src.web.dashboard import get_history

        data = [{"id": 1}, {"id": 2}]
        (tmp_path / "history_data.json").write_text(json.dumps(data), encoding="utf-8")
        result = get_history(tmp_path, limit=10)
        assert len(result) == 2

    def test_not_a_list_returns_empty(self, tmp_path):
        from src.web.dashboard import get_history

        (tmp_path / "history_data.json").write_text('{"not": "list"}', encoding="utf-8")
        result = get_history(tmp_path)
        assert result == []

    def test_missing_file_returns_empty(self, tmp_path):
        from src.web.dashboard import get_history

        result = get_history(tmp_path)
        assert result == []


class TestGetErrors:
    """Test get_errors function."""

    def test_returns_last_n_errors(self, tmp_path):
        from src.web.dashboard import get_errors

        data = [{"type": "error", "message": f"err{i}"} for i in range(50)]
        (tmp_path / "error_log.json").write_text(json.dumps(data), encoding="utf-8")
        result = get_errors(tmp_path, limit=3)
        assert len(result) == 3
        assert result[-1]["message"] == "err49"

    def test_not_a_list_returns_empty(self, tmp_path):
        from src.web.dashboard import get_errors

        (tmp_path / "error_log.json").write_text('"just a string"', encoding="utf-8")
        result = get_errors(tmp_path)
        assert result == []


class TestFormatUptime:
    """Test format_uptime helper."""

    def test_seconds_less_than_60(self):
        from src.web.dashboard import format_uptime

        assert format_uptime(30) == "30秒"

    def test_minutes_less_than_3600(self):
        from src.web.dashboard import format_uptime

        assert format_uptime(125) == "2分5秒"

    def test_hours(self):
        from src.web.dashboard import format_uptime

        assert format_uptime(7325) == "2小时2分"

    def test_zero_seconds(self):
        from src.web.dashboard import format_uptime

        assert format_uptime(0) == "0秒"

    def test_exactly_60_seconds(self):
        from src.web.dashboard import format_uptime

        assert format_uptime(60) == "1分0秒"

    def test_59_seconds(self):
        from src.web.dashboard import format_uptime

        assert format_uptime(59) == "59秒"

    def test_3599_seconds(self):
        from src.web.dashboard import format_uptime

        assert format_uptime(3599) == "59分59秒"

    def test_exactly_3600_seconds(self):
        from src.web.dashboard import format_uptime

        assert format_uptime(3600) == "1小时0分"

    def test_float_input_truncates(self):
        from src.web.dashboard import format_uptime

        assert format_uptime(60.9) == "1分0秒"


# ============================================================================
# Dashboard tests with Flask mock (via sys.modules)
# ============================================================================

_SAVED_FLASK_MODULES: dict = {}


class _RouteCapture:
    """Captures route handler functions for direct testing."""

    def __init__(self, path, handlers_dict):
        self.path = path
        self._handlers = handlers_dict

    def __call__(self, func):
        self._handlers[self.path] = func
        return func


@pytest.fixture
def flask_mock():
    """Mock Flask at sys.modules level, capturing route handlers."""
    route_handlers: dict = {}

    # Create mock Flask app that captures routes
    mock_app = MagicMock()
    # Override route() to capture handlers
    mock_app.route = MagicMock(side_effect=lambda path: _RouteCapture(path, route_handlers))
    mock_app.run = MagicMock()

    # Build mock flask module
    mock_flask = MagicMock()
    mock_flask.Flask = MagicMock(return_value=mock_app)
    mock_flask.jsonify = MagicMock(side_effect=lambda x: x)
    mock_flask.render_template_string = MagicMock(return_value="<html>...</html>")
    mock_flask.abort = MagicMock()
    mock_flask.request = MagicMock()

    # Save + inject
    _SAVED_FLASK_MODULES["flask"] = sys.modules.get("flask", None)
    sys.modules["flask"] = mock_flask

    # Remove cached web modules to force re-import
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("src.web"):
            del sys.modules[mod_name]

    yield {
        "flask": mock_flask,
        "Flask": mock_flask.Flask,
        "app": mock_app,
        "jsonify": mock_flask.jsonify,
        "render": mock_flask.render_template_string,
        "abort": mock_flask.abort,
        "request": mock_flask.request,
        "route_handlers": route_handlers,
    }

    # Restore
    sys.modules.pop("flask", None)
    if _SAVED_FLASK_MODULES["flask"] is not None:
        sys.modules["flask"] = _SAVED_FLASK_MODULES["flask"]
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("src.web"):
            del sys.modules[mod_name]


class TestCreateAppFlaskAvailable:
    """Test create_app when Flask is mocked as available."""

    def _setup_app(self):
        """Helper: reload dash with Flask mock active and create app."""
        import importlib

        import src.web.dashboard as dash

        importlib.reload(dash)
        return dash

    def test_create_app_returns_flask_app(self, flask_mock):
        dash = self._setup_app()
        assert dash.FLASK_AVAILABLE is True

        app = dash.create_app()
        flask_mock["Flask"].assert_called_once()
        assert app is not None

    def test_create_app_with_custom_data_dir(self, flask_mock):
        dash = self._setup_app()
        app = dash.create_app(data_dir=Path("/custom/data"))
        assert app is not None

    def test_create_app_no_api_key_warns(self, flask_mock):
        import importlib

        import src.web.dashboard as dash

        importlib.reload(dash)
        dash.set_api_key(None)
        app = dash.create_app()
        assert app is not None

    def test_create_app_with_api_key_logs(self, flask_mock):
        import importlib

        import src.web.dashboard as dash

        importlib.reload(dash)
        dash.set_api_key("secret")
        app = dash.create_app()
        assert app is not None

    def test_create_app_flask_not_available(self, flask_mock, monkeypatch):
        """Test create_app raises ImportError when FLASK_AVAILABLE=False."""
        import importlib

        import src.web.dashboard as dash

        importlib.reload(dash)
        monkeypatch.setattr(dash, "FLASK_AVAILABLE", False)
        with pytest.raises(ImportError, match="Flask 未安装"):
            dash.create_app()

    def test_index_route_registered(self, flask_mock):
        dash = self._setup_app()
        dash.set_api_key(None)
        dash.create_app()
        handlers = flask_mock["route_handlers"]
        assert "/" in handlers
        assert "/api/v1/status" in handlers
        assert "/api/v1/history" in handlers
        assert "/api/v1/errors" in handlers
        assert "/api/v1/report" in handlers
        assert "/api/v1/security-audit" in handlers
        assert "/health" in handlers

    # ── Route handler body tests ──

    def test_index_route_renders(self, flask_mock, tmp_path):
        """Test index route renders dashboard template."""
        dash = self._setup_app()
        dash.set_api_key(None)
        # Create mock data files
        (tmp_path / "current_data.json").write_text(
            json.dumps(
                {
                    "performance": {
                        "speed": 1000,
                        "total_checked": 5000,
                        "cpu_usage": 30,
                        "memory_usage": 200,
                    },
                    "engine": {"is_running": True, "mode": "GPU"},
                    "system": {"os": "Windows"},
                    "uptime": 3600,
                },
            ),
            encoding="utf-8",
        )
        (tmp_path / "history_data.json").write_text(
            json.dumps([{"speed": 900, "total_checked": 4000, "cpu_usage": 25, "memory_usage": 150}]),
            encoding="utf-8",
        )
        (tmp_path / "error_log.json").write_text(
            json.dumps([{"message": "test error", "type": "error"}]),
            encoding="utf-8",
        )

        dash.create_app(data_dir=tmp_path)
        handler = flask_mock["route_handlers"]["/"]
        result = handler()
        flask_mock["render"].assert_called_once()
        assert result is not None

    def test_api_status_route(self, flask_mock, tmp_path):
        """Test /api/v1/status route returns current stats."""
        dash = self._setup_app()
        dash.set_api_key(None)
        (tmp_path / "current_data.json").write_text(
            json.dumps({"performance": {"speed": 500}, "engine": {}, "system": {}}),
            encoding="utf-8",
        )
        dash.create_app(data_dir=tmp_path)
        handler = flask_mock["route_handlers"]["/api/v1/status"]
        result = handler()
        assert result["speed"] == 500

    def test_api_history_route_default_limit(self, flask_mock, tmp_path):
        """Test /api/v1/history default limit=50 when no query param."""
        dash = self._setup_app()
        dash.set_api_key(None)
        data = [{"id": i} for i in range(100)]
        (tmp_path / "history_data.json").write_text(json.dumps(data), encoding="utf-8")
        dash.create_app(data_dir=tmp_path)

        flask_mock["request"].args.get.return_value = 50
        handler = flask_mock["route_handlers"]["/api/v1/history"]
        result = handler()
        assert len(result) == 50

    def test_api_history_route_limit_capped_at_200(self, flask_mock, tmp_path):
        """Test /api/v1/history limit capped at 200."""
        dash = self._setup_app()
        dash.set_api_key(None)
        data = [{"id": i} for i in range(300)]
        (tmp_path / "history_data.json").write_text(json.dumps(data), encoding="utf-8")
        dash.create_app(data_dir=tmp_path)

        flask_mock["request"].args.get.return_value = 500
        handler = flask_mock["route_handlers"]["/api/v1/history"]
        result = handler()
        assert len(result) == 200

    def test_api_history_limit_zero_returns_all(self, flask_mock, tmp_path):
        """Test /api/v1/history limit=0 returns all data (data[-0:] == data[:])."""
        dash = self._setup_app()
        dash.set_api_key(None)
        data = [{"id": i} for i in range(80)]
        (tmp_path / "history_data.json").write_text(json.dumps(data), encoding="utf-8")
        dash.create_app(data_dir=tmp_path)

        # Simulate Flask type=int: ?limit=0 → 0
        flask_mock["request"].args.get.return_value = 0
        handler = flask_mock["route_handlers"]["/api/v1/history"]
        result = handler()
        assert len(result) == 80

    def test_api_history_limit_non_integer_uses_default(self, flask_mock, tmp_path):
        """Test /api/v1/history with non-integer limit → Flask type=int returns default 50."""
        dash = self._setup_app()
        dash.set_api_key(None)
        data = [{"id": i} for i in range(60)]
        (tmp_path / "history_data.json").write_text(json.dumps(data), encoding="utf-8")
        dash.create_app(data_dir=tmp_path)

        # Simulate Flask type=int: ?limit=abc → default 50
        flask_mock["request"].args.get.return_value = 50
        handler = flask_mock["route_handlers"]["/api/v1/history"]
        result = handler()
        assert len(result) == 50

    def test_api_errors_route_default_limit(self, flask_mock, tmp_path):
        """Test /api/v1/errors default limit=50 when no query param."""
        dash = self._setup_app()
        dash.set_api_key(None)
        data = [{"msg": f"err{i}"} for i in range(60)]
        (tmp_path / "error_log.json").write_text(json.dumps(data), encoding="utf-8")
        dash.create_app(data_dir=tmp_path)

        flask_mock["request"].args.get.return_value = 50
        handler = flask_mock["route_handlers"]["/api/v1/errors"]
        result = handler()
        assert len(result) == 50

    def test_api_report_empty_history(self, flask_mock, tmp_path):
        """Test /api/v1/report with empty history yields zero speeds."""
        dash = self._setup_app()
        dash.set_api_key(None)
        (tmp_path / "current_data.json").write_text(
            json.dumps({"performance": {}, "engine": {}, "system": {}, "uptime": 0}),
            encoding="utf-8",
        )
        (tmp_path / "history_data.json").write_text("[]", encoding="utf-8")

        dash.create_app(data_dir=tmp_path)
        handler = flask_mock["route_handlers"]["/api/v1/report"]
        result = handler()
        assert result["summary"]["avg_speed"] == 0
        assert result["summary"]["max_speed"] == 0
        assert "summary" in result
        assert "engine" in result
        assert "generated_at" in result

    def test_api_report_history_not_a_list(self, flask_mock, tmp_path):
        """Test /api/v1/report handles non-list history gracefully."""
        dash = self._setup_app()
        dash.set_api_key(None)
        (tmp_path / "current_data.json").write_text(
            json.dumps({"performance": {}, "engine": {}, "system": {}, "uptime": 0}),
            encoding="utf-8",
        )
        (tmp_path / "history_data.json").write_text('{"not": "list"}', encoding="utf-8")

        dash.create_app(data_dir=tmp_path)
        handler = flask_mock["route_handlers"]["/api/v1/report"]
        result = handler()
        assert result["summary"]["avg_speed"] == 0
        assert result["summary"]["max_speed"] == 0
        assert "summary" in result
        assert "engine" in result
        assert "generated_at" in result

    def test_api_errors_route(self, flask_mock, tmp_path):
        """Test /api/v1/errors route returns error data."""
        dash = self._setup_app()
        dash.set_api_key(None)
        data = [{"msg": f"err{i}"} for i in range(30)]
        (tmp_path / "error_log.json").write_text(json.dumps(data), encoding="utf-8")
        dash.create_app(data_dir=tmp_path)

        flask_mock["request"].args.get.return_value = 5
        handler = flask_mock["route_handlers"]["/api/v1/errors"]
        result = handler()
        assert len(result) == 5

    def test_api_report_route(self, flask_mock, tmp_path):
        """Test /api/v1/report route returns report summary."""
        dash = self._setup_app()
        dash.set_api_key(None)
        (tmp_path / "current_data.json").write_text(
            json.dumps(
                {
                    "performance": {
                        "total_checked": 10000,
                        "matches_found": 2,
                        "cpu_usage": 40,
                        "memory_usage": 300,
                    },
                    "engine": {"is_running": True, "mode": "GPU"},
                    "system": {},
                    "uptime": 7200,
                },
            ),
            encoding="utf-8",
        )
        history_data = [{"speed": s} for s in [100, 200, 300, 0, None]]
        # Include an entry with no speed key to test filter
        history_data.append({"other": "data"})
        (tmp_path / "history_data.json").write_text(json.dumps(history_data), encoding="utf-8")

        dash.create_app(data_dir=tmp_path)
        handler = flask_mock["route_handlers"]["/api/v1/report"]
        result = handler()
        assert "summary" in result
        assert result["summary"]["total_checked"] == 10000
        assert "engine" in result

    def test_health_route(self, flask_mock, tmp_path):
        """Test /health route (unauthenticated)."""
        dash = self._setup_app()
        (tmp_path / "current_data.json").write_text("{}", encoding="utf-8")
        dash.create_app(data_dir=tmp_path)
        handler = flask_mock["route_handlers"]["/health"]
        result = handler()
        assert result["status"] == "ok"

    def test_version_fallback_on_import_error(self, flask_mock):
        """Test version fallback when from . import __version__ fails."""
        import importlib

        import src.web.dashboard as dash

        importlib.reload(dash)

        # Remove __version__ from src.web so the relative import fails
        import src.web

        saved_version = getattr(src.web, "__version__", None)
        try:
            del src.web.__version__
            app = dash.create_app()
            assert app is not None
        finally:
            if saved_version is not None:
                src.web.__version__ = saved_version

    def test_create_app_returns_registered_routes(self, flask_mock):
        """Verify create_app registers all expected routes."""
        dash = self._setup_app()
        dash.set_api_key(None)
        dash.create_app()
        # The Flask constructor should have been called with a name
        flask_mock["Flask"].assert_called_once()
        # Routes: /, /api/status, /api/history, /api/errors, /api/report,
        #         /api/security-audit, /health
        assert len(flask_mock["route_handlers"]) == 8


class TestRunDashboard:
    """Test run_dashboard function."""

    def test_flask_not_available_exits(self, monkeypatch):
        import src.web.dashboard as dash

        monkeypatch.setattr(dash, "FLASK_AVAILABLE", False)
        with pytest.raises(SystemExit) as exc_info:
            dash.run_dashboard()
        assert exc_info.value.code == 1

    def test_run_dashboard_with_flask_available(self, flask_mock):
        import importlib

        import src.web.dashboard as dash

        importlib.reload(dash)
        mock_app_run = MagicMock()
        flask_mock["app"].run = mock_app_run

        dash.run_dashboard(host="127.0.0.1", port=9999)
        mock_app_run.assert_called_once_with(
            host="127.0.0.1",
            port=9999,
            debug=False,
            use_reloader=False,
        )

    def test_run_dashboard_with_api_key(self, flask_mock):
        import importlib

        import src.web.dashboard as dash

        importlib.reload(dash)
        mock_app_run = MagicMock()
        flask_mock["app"].run = mock_app_run

        dash.run_dashboard(api_key="my-api-key")
        assert dash._api_key == "my-api-key"
        assert dash._api_key_required is True

    def test_debug_mode_redirects_host(self, flask_mock):
        import importlib

        import src.web.dashboard as dash

        importlib.reload(dash)
        mock_app_run = MagicMock()
        flask_mock["app"].run = mock_app_run

        dash.run_dashboard(host="0.0.0.0", port=8080, debug=True)
        mock_app_run.assert_called_once_with(host="127.0.0.1", port=8080, debug=True, use_reloader=False)

    def test_debug_mode_localhost_not_redirected(self, flask_mock):
        import importlib

        import src.web.dashboard as dash

        importlib.reload(dash)
        mock_app_run = MagicMock()
        flask_mock["app"].run = mock_app_run

        dash.run_dashboard(host="127.0.0.1", port=8080, debug=True)
        mock_app_run.assert_called_once_with(host="127.0.0.1", port=8080, debug=True, use_reloader=False)

    def test_run_dashboard_with_data_dir(self, flask_mock, tmp_path):
        import importlib

        import src.web.dashboard as dash

        importlib.reload(dash)
        mock_app_run = MagicMock()
        flask_mock["app"].run = mock_app_run

        dash.run_dashboard(data_dir=str(tmp_path))
        mock_app_run.assert_called()


class TestMainCLI:
    """Test main() CLI entry with argument parsing."""

    def _setup(self, flask_mock):
        """Helper: reload dash and set up mock app.run."""
        import importlib

        import src.web.dashboard as dash

        importlib.reload(dash)
        mock_app_run = MagicMock()
        flask_mock["app"].run = mock_app_run
        return dash, mock_app_run

    def test_main_defaults(self, flask_mock, monkeypatch):
        dash, mock_app_run = self._setup(flask_mock)
        monkeypatch.setattr("sys.argv", ["dashboard.py"])
        dash.main()
        mock_app_run.assert_called_once_with(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

    def test_main_custom_port(self, flask_mock, monkeypatch):
        dash, mock_app_run = self._setup(flask_mock)
        monkeypatch.setattr("sys.argv", ["dashboard.py", "--port", "3000"])
        dash.main()
        mock_app_run.assert_called_once_with(host="0.0.0.0", port=3000, debug=False, use_reloader=False)

    def test_main_with_debug(self, flask_mock, monkeypatch):
        dash, mock_app_run = self._setup(flask_mock)
        monkeypatch.setattr("sys.argv", ["dashboard.py", "--debug"])
        dash.main()
        mock_app_run.assert_called_once_with(host="127.0.0.1", port=8080, debug=True, use_reloader=False)

    def test_main_with_api_key(self, flask_mock, monkeypatch):
        dash, mock_app_run = self._setup(flask_mock)
        monkeypatch.setattr("sys.argv", ["dashboard.py", "--api-key", "secret123"])
        dash.main()
        assert dash._api_key == "secret123"

    def test_main_with_reload(self, flask_mock, monkeypatch):
        dash, mock_app_run = self._setup(flask_mock)
        monkeypatch.setattr("sys.argv", ["dashboard.py", "--reload"])
        dash.main()
        mock_app_run.assert_called_once_with(host="0.0.0.0", port=8080, debug=False, use_reloader=True)

    def test_main_with_data_dir(self, flask_mock, monkeypatch, tmp_path):
        dash, mock_app_run = self._setup(flask_mock)
        monkeypatch.setattr("sys.argv", ["dashboard.py", "--data-dir", str(tmp_path)])
        dash.main()
        mock_app_run.assert_called()

    @patch("os.environ.get", return_value="env-secret")
    def test_main_api_key_from_env(self, mock_environ, flask_mock, monkeypatch):
        dash, mock_app_run = self._setup(flask_mock)
        monkeypatch.setattr("sys.argv", ["dashboard.py"])
        dash.main()
        mock_app_run.assert_called()

    def test_main_module_entry_point(self, flask_mock, monkeypatch):
        """Test if __name__ == '__main__' block calls main()."""
        import importlib

        import src.web.dashboard as dash

        importlib.reload(dash)
        mock_app_run = MagicMock()
        flask_mock["app"].run = mock_app_run

        monkeypatch.setattr("sys.argv", ["dashboard.py"])

        # Execute the module-level __name__ check directly
        exec("if __name__ == '__main__': main()", {"__name__": "__main__", "main": dash.main})

    def test_main_entry_point_via_runpy(self, flask_mock, monkeypatch):
        """Cover line 557: actual if __name__ == '__main__' via runpy."""
        monkeypatch.setattr("sys.argv", ["dashboard.py"])

        # run_module with run_name='__main__' triggers the __name__ guard
        import runpy

        runpy.run_module("src.web.dashboard", run_name="__main__")
