# -*- coding: utf-8 -*-
"""P3-10: fast_json 模块单元测试"""
import json
import pytest
import tempfile
import os
from src.utils.fast_json import (
    fast_dumps, fast_loads, fast_dump, fast_load, is_orjson_available
)


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
        # Ensure keys are sorted (JSON has no key order guarantee in spec, but both json and orjson output sorted)
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
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8'
        ) as f:
            temp_path = f.name
            fast_dump(data, f, indent=2)

        try:
            with open(temp_path, 'r', encoding='utf-8') as f:
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
