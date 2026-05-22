"""P3-10: fast_json 模块单元测试"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.utils.fast_json import fast_dump, fast_dumps, fast_load, fast_loads, is_orjson_available


class TestFastDumps:
    """fast_dumps 序列化测试"""

    def test_basic_dict(self):
        data = {"key": "value", "num": 42}
        result = fast_dumps(data)
        assert isinstance(result, str)
        loaded = json.loads(result)
        assert loaded == data

    def test_ensure_ascii(self):
        data = {"cn": "中文测试"}
        result = fast_dumps(data, ensure_ascii=False)
        loaded = json.loads(result)
        assert loaded == data

    def test_indent(self):
        data = {"a": 1, "b": 2}
        result = fast_dumps(data, indent=2)
        assert "\n" in result
        loaded = json.loads(result)
        assert loaded == data

    def test_sort_keys(self):
        data = {"z": 3, "a": 1}
        result = fast_dumps(data, sort_keys=True)
        loaded = json.loads(result)
        assert loaded == data
        # Ensure keys are sorted (JSON has no key order guarantee in spec, but
        # both json and orjson output sorted)
        assert result.index('"a"') < result.index('"z"')


class TestFastLoads:
    """fast_loads 反序列化测试"""

    def test_basic_dict(self):
        s = '{"key": "value", "num": 42}'
        result = fast_loads(s)
        assert result == {"key": "value", "num": 42}

    def test_bytes_input(self):
        s = b'{"key": "value"}'
        result = fast_loads(s)
        assert result == {"key": "value"}

    def test_unicode(self):
        s = '{"cn": "中文测试"}'
        result = fast_loads(s)
        assert result == {"cn": "中文测试"}


class TestFastDumpLoad:
    """fast_dump / fast_load 文件操作测试"""

    def test_round_trip(self):
        data = {"test": "value", "list": [1, 2, 3], "nested": {"a": 1}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            temp_path = f.name
            fast_dump(data, f, indent=2)

        try:
            with open(temp_path, encoding="utf-8") as f:
                loaded = fast_load(f)
            assert loaded == data
        finally:
            os.unlink(temp_path)


class TestIsOrjsonAvailable:
    """is_orjson_available 检测"""

    def test_returns_bool(self):
        result = is_orjson_available()
        assert isinstance(result, bool)


class TestIntegration:
    """集成测试: 与 json 模块兼容性"""

    def test_compat_with_json_loads(self):
        """fast_dumps 输出可以被 json.loads 解析"""
        data = {"int": 1, "float": 3.14, "bool": True, "null": None, "str": "text"}
        result = fast_dumps(data)
        parsed = json.loads(result)
        assert parsed == data

    def test_compat_with_standard_json_dumps(self):
        """json.dumps 输出可以被 fast_loads 解析"""
        data = {"int": 1, "float": 3.14, "bool": True, "null": None}
        result = json.dumps(data)
        parsed = fast_loads(result)
        assert parsed == data

    def test_default_parameter(self):
        """default 参数传递给 json.dumps（强制 json 降级路径）"""
        from datetime import datetime

        data = {"ts": datetime(2024, 1, 1, 12, 0, 0)}
        with patch("src.utils.fast_json._ORJSON_AVAILABLE", False):
            result = fast_dumps(data, default=str)
        parsed = json.loads(result)
        assert "2024" in parsed["ts"]

    def test_no_indent(self):
        """无 indent 参数时输出紧凑格式"""
        data = {"a": 1, "b": 2}
        result = fast_dumps(data)
        assert "\n" not in result

    def test_ensure_ascii_true(self):
        """ensure_ascii=True 转义非 ASCII 字符（json 降级路径）"""
        data = {"cn": "中文"}
        with patch("src.utils.fast_json._ORJSON_AVAILABLE", False):
            result = fast_dumps(data, ensure_ascii=True)
        assert "\\u" in result


class TestFastLoadsEdge:
    """fast_loads 边界测试"""

    def test_invalid_json_raises(self):
        """无效 JSON 抛出异常（json 降级路径）"""
        with patch("src.utils.fast_json._ORJSON_AVAILABLE", False):
            with pytest.raises(json.JSONDecodeError):
                fast_loads("{invalid}")


class TestFastDumpsOrjsonPath:
    """fast_dumps orjson 路径测试（mock orjson 可用）"""

    def test_orjson_dumps_without_default(self):
        """orjson 可用时通过 orjson.dumps 序列化"""
        mock_orjson = MagicMock()
        mock_orjson.dumps.return_value = b'{"a":1}'

        with (
            patch("src.utils.fast_json._ORJSON_AVAILABLE", True),
            patch("src.utils.fast_json._orjson_module", mock_orjson),
        ):
            result = fast_dumps({"a": 1})
            assert result == '{"a":1}'
            mock_orjson.dumps.assert_called_once()

    def test_orjson_dumps_with_default(self):
        """orjson 路径传递 default 参数"""
        mock_orjson = MagicMock()
        mock_orjson.dumps.return_value = b'{"a":"2024-01-01"}'

        def custom_default(obj):
            return str(obj)

        with (
            patch("src.utils.fast_json._ORJSON_AVAILABLE", True),
            patch("src.utils.fast_json._orjson_module", mock_orjson),
        ):
            result = fast_dumps({"a": object()}, default=custom_default)
            assert result == '{"a":"2024-01-01"}'
            call_args = mock_orjson.dumps.call_args
            assert call_args[1]["default"] is custom_default

    def test_orjson_dumps_with_indent_option(self):
        """orjson 路径 indent>=2 时设置 OPT_INDENT_2"""
        mock_orjson = MagicMock()
        mock_orjson.dumps.return_value = b'{"a": 1}'

        with (
            patch("src.utils.fast_json._ORJSON_AVAILABLE", True),
            patch("src.utils.fast_json._orjson_module", mock_orjson),
        ):
            fast_dumps({"a": 1}, indent=2)
            call_kwargs = mock_orjson.dumps.call_args[1]
            option = call_kwargs["option"]
            assert option & 1  # OPT_INDENT_2

    def test_orjson_dumps_with_sort_keys_option(self):
        """orjson 路径 sort_keys=True 时设置 OPT_SORT_KEYS"""
        mock_orjson = MagicMock()
        mock_orjson.dumps.return_value = b'{"a":1,"b":2}'

        with (
            patch("src.utils.fast_json._ORJSON_AVAILABLE", True),
            patch("src.utils.fast_json._orjson_module", mock_orjson),
        ):
            fast_dumps({"b": 2, "a": 1}, sort_keys=True)
            call_kwargs = mock_orjson.dumps.call_args[1]
            option = call_kwargs["option"]
            assert option & 2  # OPT_SORT_KEYS

    def test_orjson_dumps_non_ascii_option(self):
        """orjson 路径 ensure_ascii=False 时设置 OPT_NON_STR_KEYS"""
        mock_orjson = MagicMock()
        mock_orjson.dumps.return_value = b'{"key":"value"}'

        with (
            patch("src.utils.fast_json._ORJSON_AVAILABLE", True),
            patch("src.utils.fast_json._orjson_module", mock_orjson),
        ):
            fast_dumps({"key": "value"}, ensure_ascii=False)
            call_kwargs = mock_orjson.dumps.call_args[1]
            option = call_kwargs["option"]
            assert option & 4  # OPT_NON_STR_KEYS

    def test_orjson_dumps_fallback_on_type_error(self):
        """orjson.dumps 抛出 TypeError 时降级到 json.dumps"""
        mock_orjson = MagicMock()
        mock_orjson.dumps.side_effect = TypeError("not serializable")

        with (
            patch("src.utils.fast_json._ORJSON_AVAILABLE", True),
            patch("src.utils.fast_json._orjson_module", mock_orjson),
        ):
            result = fast_dumps({"a": 1})
            loaded = json.loads(result)
            assert loaded == {"a": 1}

    def test_orjson_dumps_fallback_on_value_error(self):
        """orjson.dumps 抛出 ValueError 时降级到 json.dumps"""
        mock_orjson = MagicMock()
        mock_orjson.dumps.side_effect = ValueError("bad value")

        with (
            patch("src.utils.fast_json._ORJSON_AVAILABLE", True),
            patch("src.utils.fast_json._orjson_module", mock_orjson),
        ):
            result = fast_dumps({"a": 1})
            loaded = json.loads(result)
            assert loaded == {"a": 1}

    def test_orjson_dumps_fallback_on_overflow_error(self):
        """orjson.dumps 抛出 OverflowError 时降级到 json.dumps"""
        mock_orjson = MagicMock()
        mock_orjson.dumps.side_effect = OverflowError("float too large")

        with (
            patch("src.utils.fast_json._ORJSON_AVAILABLE", True),
            patch("src.utils.fast_json._orjson_module", mock_orjson),
        ):
            result = fast_dumps({"a": float("inf")})
            loaded = json.loads(result)
            assert loaded == {"a": float("inf")}

    def test_orjson_dumps_returns_str_directly(self):
        """orjson.dumps 返回 str 时直接返回不 decode"""
        mock_orjson = MagicMock()
        mock_orjson.dumps.return_value = '{"a":1}'

        with (
            patch("src.utils.fast_json._ORJSON_AVAILABLE", True),
            patch("src.utils.fast_json._orjson_module", mock_orjson),
        ):
            result = fast_dumps({"a": 1})
            assert result == '{"a":1}'


class TestFastLoadsOrjsonPath:
    """fast_loads orjson 路径测试（mock orjson 可用）"""

    def test_orjson_loads(self):
        """orjson 可用时通过 orjson.loads 反序列化"""
        mock_orjson = MagicMock()
        mock_orjson.loads.return_value = {"a": 1}

        with (
            patch("src.utils.fast_json._ORJSON_AVAILABLE", True),
            patch("src.utils.fast_json._orjson_module", mock_orjson),
        ):
            result = fast_loads('{"a":1}')
            assert result == {"a": 1}
            mock_orjson.loads.assert_called_once_with('{"a":1}')

    def test_orjson_loads_fallback_on_exception(self):
        """orjson.loads 异常时降级到 json.loads"""
        mock_orjson = MagicMock()
        mock_orjson.loads.side_effect = ValueError("bad json")

        with (
            patch("src.utils.fast_json._ORJSON_AVAILABLE", True),
            patch("src.utils.fast_json._orjson_module", mock_orjson),
        ):
            result = fast_loads('{"a":1}')
            assert result == {"a": 1}

    def test_orjson_loads_bytes_input(self):
        """orjson 路径处理 bytes 输入"""
        mock_orjson = MagicMock()
        mock_orjson.loads.return_value = {"a": 1}

        with (
            patch("src.utils.fast_json._ORJSON_AVAILABLE", True),
            patch("src.utils.fast_json._orjson_module", mock_orjson),
        ):
            result = fast_loads(b'{"a":1}')
            assert result == {"a": 1}


class TestOrjsonUnavailable:
    """orjson 不可用时的降级行为验证"""

    def test_is_orjson_available_returns_false(self):
        """当前环境 orjson 不可用"""
        with patch("src.utils.fast_json._ORJSON_AVAILABLE", False):
            assert is_orjson_available() is False

    def test_fast_dumps_uses_json_fallback(self):
        """orjson 不可用时 fast_dumps 使用 json.dumps"""
        with patch("src.utils.fast_json._ORJSON_AVAILABLE", False):
            result = fast_dumps({"a": 1})
            loaded = json.loads(result)
            assert loaded == {"a": 1}

    def test_fast_loads_uses_json_fallback(self):
        """orjson 不可用时 fast_loads 使用 json.loads"""
        with patch("src.utils.fast_json._ORJSON_AVAILABLE", False):
            result = fast_loads('{"a":1}')
            assert result == {"a": 1}
