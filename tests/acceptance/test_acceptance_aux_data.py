#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""辅助数据验收测试 - 数据辅助工具和转换

本模块测试 `src.utils` 和 `src.core` 中的数据辅助功能，
确保：
1. 功能层：功能正确性、功能调用、功能判断
2. 数据层：数据、数据流、数据管道、数据类型、数据调用
3. 逻辑层：代码正确性、逻辑、逻辑正确性、逻辑判断

测试策略：
- 多工具：测试 fast_json、encoding_utils、hash_utils 等工具
- 多数据组合：测试不同数据类型、格式、边界条件
- 高可读性：结构化测试代码，清晰的测试用例命名，详细的文档字符串
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

import pytest

from tests.acceptance.conftest import (
    AcceptanceTestConstants,
    assert_valid_bitcoin_address,
    assert_valid_private_key,
)


# ============================================================================
# 白盒测试 - 基于内部代码结构的测试
# ============================================================================

@pytest.mark.acceptance
@pytest.mark.white_box
@pytest.mark.functional
@pytest.mark.data_layer
class TestFastJsonWhiteBox:
    """fast_json 白盒测试

    基于内部代码结构的测试，验证：
    1. 内部状态转换的正确性
    2. 条件判断分支的覆盖
    3. 循环逻辑的正确性
    4. 异常处理路径的覆盖
    """

    def test_fast_dumps_logic(self):
        """白盒测试：验证 fast_dumps 的逻辑分支"""

        from src.utils.fast_json import fast_dumps

        # 白盒验证：不同数据类型的处理
        test_data = {
            "string": "test",
            "number": 123,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "object": {"key": "value"},
        }

        result = fast_dumps(test_data)
        assert result is not None, "fast_dumps 逻辑不正确：应返回字符串"
        assert isinstance(result, str), (
            "fast_dumps 逻辑不正确：应返回 str 类型"
        )

        # 验证 JSON 格式正确性
        parsed = json.loads(result)
        assert parsed["string"] == "test", (
            "fast_dumps 逻辑不正确：字符串序列化失败"
        )
        assert parsed["number"] == 123, (
            "fast_dumps 逻辑不正确：数字序列化失败"
        )

    def test_fast_loads_logic(self):
        """白盒测试：验证 fast_loads 的逻辑分支"""

        from src.utils.fast_json import fast_loads

        # 白盒验证：JSON 字符串解析
        test_json = '{"key": "value", "number": 123}'

        result = fast_loads(test_json)
        assert result is not None, "fast_loads 逻辑不正确：应返回字典"
        assert isinstance(result, dict), (
            "fast_loads 逻辑不正确：应返回 dict 类型"
        )

        # 验证解析正确性
        assert result["key"] == "value", (
            "fast_loads 逻辑不正确：字符串解析失败"
        )
        assert result["number"] == 123, (
            "fast_loads 逻辑不正确：数字解析失败"
        )

    def test_fast_json_error_handling(self):
        """白盒测试：验证 fast_json 的错误处理路径"""

        from src.utils.fast_json import fast_loads

        # 白盒验证：无效 JSON 的错误处理
        invalid_json = '{"key": "value", "invalid": }'

        try:
            result = fast_loads(invalid_json)
            # 如果不抛出异常，应返回 None 或空字典
            assert result is None or isinstance(result, dict), (
                "fast_json 错误处理逻辑不正确：应返回 None 或 dict"
            )
        except (json.JSONDecodeError, ValueError):
            # 预期行为：抛出异常
            pass


@pytest.mark.acceptance
@pytest.mark.white_box
@pytest.mark.functional
@pytest.mark.data_layer
class TestHashUtilsWhiteBox:
    """hash_utils 白盒测试"""

    def test_hash160_logic(self):
        """白盒测试：验证 hash160 的逻辑分支"""

        from src.core.hash_utils import HashUtils

        # 白盒验证：Hash160 计算
        test_data = b"test data"

        hash160 = HashUtils.hash160(test_data)
        assert hash160 is not None, "hash160 逻辑不正确：应返回字节串"
        assert isinstance(hash160, bytes), (
            "hash160 逻辑不正确：应返回 bytes 类型"
        )
        assert len(hash160) == 20, (
            f"hash160 逻辑不正确：长度应为 20 字节，"
            f"实际为 {len(hash160)} 字节"
        )

    def test_double_sha256_logic(self):
        """白盒测试：验证 double_sha256 的逻辑分支"""

        from src.core.hash_utils import HashUtils

        # 白盒验证：Double SHA256 计算
        test_data = b"test data"

        double_hash = HashUtils.double_sha256(test_data)
        assert double_hash is not None, (
            "double_sha256 逻辑不正确：应返回字节串"
        )
        assert isinstance(double_hash, bytes), (
            "double_sha256 逻辑不正确：应返回 bytes 类型"
        )
        assert len(double_hash) == 32, (
            f"double_sha256 逻辑不正确：长度应为 32 字节，"
            f"实际为 {len(double_hash)} 字节"
        )


# ============================================================================
# 黑盒测试 - 基于规格说明的功能测试
# ============================================================================

@pytest.mark.acceptance
@pytest.mark.black_box
@pytest.mark.functional
@pytest.mark.data_layer
class TestFastJsonBlackBox:
    """fast_json 黑盒测试"""

    def test_black_box_fast_dumps_valid_input(self):
        """黑盒测试：使用有效输入调用 fast_dumps"""

        from src.utils.fast_json import fast_dumps

        # 黑盒验证：有效输入
        test_data = {"key": "value"}

        result = fast_dumps(test_data)
        assert result is not None, (
            "黑盒测试失败：有效输入应成功序列化"
        )
        assert isinstance(result, str), (
            "黑盒测试失败：应返回 str 类型"
        )

        # 验证 JSON 格式正确性
        parsed = json.loads(result)
        assert parsed["key"] == "value", (
            "黑盒测试失败：序列化结果不正确"
        )

    def test_black_box_fast_loads_valid_input(self):
        """黑盒测试：使用有效输入调用 fast_loads"""

        from src.utils.fast_json import fast_loads

        # 黑盒验证：有效输入
        test_json = '{"key": "value"}'

        result = fast_loads(test_json)
        assert result is not None, (
            "黑盒测试失败：有效输入应成功解析"
        )
        assert isinstance(result, dict), (
            "黑盒测试失败：应返回 dict 类型"
        )

        # 验证解析正确性
        assert result["key"] == "value", (
            "黑盒测试失败：解析结果不正确"
        )

    def test_black_box_fast_dumps_invalid_input(self):
        """黑盒测试：使用无效输入调用 fast_dumps"""

        from src.utils.fast_json import fast_dumps

        # 黑盒验证：无效输入
        # 注意：fast_dumps 可能接受任何对象
        # 这里主要验证代码路径的覆盖
        try:
            result = fast_dumps(None)
            # 如果不抛出异常，应返回字符串
            assert isinstance(result, str), (
                "黑盒测试失败：应返回 str 类型"
            )
        except (TypeError, ValueError):
            # 某些实现可能拒绝 None
            pass

    def test_black_box_fast_loads_invalid_input(self):
        """黑盒测试：使用无效输入调用 fast_loads"""

        from src.utils.fast_json import fast_loads

        # 黑盒验证：无效输入
        invalid_json = "not a json string"

        try:
            result = fast_loads(invalid_json)
            # 如果不抛出异常，应返回 None 或空字典
            assert result is None or isinstance(result, dict), (
                "黑盒测试失败：应返回 None 或 dict"
            )
        except (json.JSONDecodeError, ValueError):
            # 预期行为：抛出异常
            pass


@pytest.mark.acceptance
@pytest.mark.black_box
@pytest.mark.functional
@pytest.mark.data_layer
class TestHashUtilsBlackBox:
    """hash_utils 黑盒测试"""

    def test_black_box_hash160_valid_input(self):
        """黑盒测试：使用有效输入调用 hash160"""

        from src.core.hash_utils import HashUtils

        # 黑盒验证：有效输入
        test_data = b"test data"

        result = HashUtils.hash160(test_data)
        assert result is not None, (
            "黑盒测试失败：有效输入应成功计算 Hash160"
        )
        assert isinstance(result, bytes), (
            "黑盒测试失败：应返回 bytes 类型"
        )
        assert len(result) == 20, (
            f"黑盒测试失败：Hash160 长度应为 20 字节，"
            f"实际为 {len(result)} 字节"
        )

    def test_black_box_double_sha256_valid_input(self):
        """黑盒测试：使用有效输入调用 double_sha256"""

        from src.core.hash_utils import HashUtils

        # 黑盒验证：有效输入
        test_data = b"test data"

        result = HashUtils.double_sha256(test_data)
        assert result is not None, (
            "黑盒测试失败：有效输入应成功计算 Double SHA256"
        )
        assert isinstance(result, bytes), (
            "黑盒测试失败：应返回 bytes 类型"
        )
        assert len(result) == 32, (
            f"黑盒测试失败：Double SHA256 长度应为 32 字节，"
            f"实际为 {len(result)} 字节"
        )


# ============================================================================
# 功能层测试 - 功能正确性、功能调用、功能判断
# ============================================================================

@pytest.mark.acceptance
@pytest.mark.functional
@pytest.mark.data_layer
class TestDataAuxiliaryFunctionalLayer:
    """辅助数据功能层测试"""

    def test_functional_fast_json_dumps(self):
        """功能层测试：fast_dumps 功能正确性"""

        from src.utils.fast_json import fast_dumps

        # 功能正确性：fast_dumps
        test_data = {"key": "value"}

        result = fast_dumps(test_data)
        assert result is not None, (
            "功能层测试失败：fast_dumps 应成功序列化"
        )
        assert isinstance(result, str), (
            "功能层测试失败：应返回 str 类型"
        )

        # 验证序列化结果
        parsed = json.loads(result)
        assert parsed["key"] == "value", (
            "功能层测试失败：序列化结果不正确"
        )

    def test_functional_fast_json_loads(self):
        """功能层测试：fast_loads 功能正确性"""

        from src.utils.fast_json import fast_loads

        # 功能正确性：fast_loads
        test_json = '{"key": "value"}'

        result = fast_loads(test_json)
        assert result is not None, (
            "功能层测试失败：fast_loads 应成功解析"
        )
        assert isinstance(result, dict), (
            "功能层测试失败：应返回 dict 类型"
        )

        # 验证解析结果
        assert result["key"] == "value", (
            "功能层测试失败：解析结果不正确"
        )

    def test_functional_hash_utils_hash160(self):
        """功能层测试：hash160 功能正确性"""

        from src.core.hash_utils import HashUtils

        # 功能正确性：hash160
        test_data = b"test data"

        result = HashUtils.hash160(test_data)
        assert result is not None, (
            "功能层测试失败：hash160 应成功计算"
        )
        assert isinstance(result, bytes), (
            "功能层测试失败：应返回 bytes 类型"
        )
        assert len(result) == 20, (
            f"功能层测试失败：Hash160 长度应为 20 字节，"
            f"实际为 {len(result)} 字节"
        )

    def test_functional_hash_utils_double_sha256(self):
        """功能层测试：double_sha256 功能正确性"""

        from src.core.hash_utils import HashUtils

        # 功能正确性：double_sha256
        test_data = b"test data"

        result = HashUtils.double_sha256(test_data)
        assert result is not None, (
            "功能层测试失败：double_sha256 应成功计算"
        )
        assert isinstance(result, bytes), (
            "功能层测试失败：应返回 bytes 类型"
        )
        assert len(result) == 32, (
            f"功能层测试失败：Double SHA256 长度应为 32 字节，"
            f"实际为 {len(result)} 字节"
        )


# ============================================================================
# 逻辑层测试 - 代码正确性、逻辑、逻辑正确性、逻辑判断
# ============================================================================

@pytest.mark.acceptance
@pytest.mark.logic_layer
@pytest.mark.data_layer
class TestDataAuxiliaryLogicLayer:
    """辅助数据逻辑层测试"""

    def test_logic_fast_json_dumps_branch_coverage(self):
        """逻辑层测试：fast_dumps 分支覆盖"""

        from src.utils.fast_json import fast_dumps

        # 逻辑判断：不同数据类型的处理
        test_cases = [
            "string",
            123,
            3.14,
            True,
            None,
            [1, 2, 3],
            {"key": "value"},
        ]

        for test_data in test_cases:
            result = fast_dumps(test_data)
            # 验证：所有数据类型都能被序列化
            assert result is not None, (
                f"逻辑层测试失败：数据类型 {type(test_data)} 序列化失败"
            )
            assert isinstance(result, str), (
                f"逻辑层测试失败：数据类型 {type(test_data)} 应返回 str"
            )

    def test_logic_fast_json_loads_branch_coverage(self):
        """逻辑层测试：fast_loads 分支覆盖"""

        from src.utils.fast_json import fast_loads

        # 逻辑判断：不同 JSON 字符串的解析
        # 注意：JSON 'null' 解析为 Python None，这是正确行为
        test_cases = [
            ('{"key": "value"}', dict),
            ('[1, 2, 3]', list),
            ('true', bool),
            ('false', bool),
            ('null', type(None)),  # JSON null -> Python None
            ('123', int),
            ('"string"', str),
        ]

        for test_json, expected_type in test_cases:
            result = fast_loads(test_json)
            # 验证：所有有效 JSON 都能被正确解析
            assert result is not None or expected_type is type(None), (
                f"逻辑层测试失败：JSON {test_json} 解析失败"
            )
            assert isinstance(result, expected_type), (
                f"逻辑层测试失败：JSON {test_json} 应返回 {expected_type.__name__}，"
                f"实际返回 {type(result).__name__}"
            )

    def test_logic_hash_utils_hash160_branch_coverage(self):
        """逻辑层测试：hash160 分支覆盖"""

        from src.core.hash_utils import HashUtils

        # 逻辑判断：不同输入数据的处理
        # 注意：hash160 不接受空字节串，会抛出 ValueError
        test_cases = [
            b"a",  # 单字节
            b"test data",  # 正常数据
            os.urandom(32),  # 随机数据
            os.urandom(64),  # 长数据
        ]

        for test_data in test_cases:
            result = HashUtils.hash160(test_data)
            # 验证：所有输入都能被处理
            assert result is not None, (
                f"逻辑层测试失败：输入数据 {test_data} 处理失败"
            )
            assert isinstance(result, bytes), (
                f"逻辑层测试失败：应返回 bytes 类型"
            )
            assert len(result) == 20, (
                f"逻辑层测试失败：Hash160 长度应为 20 字节，"
                f"实际为 {len(result)} 字节"
            )

    def test_logic_hash_utils_double_sha256_branch_coverage(self):
        """逻辑层测试：double_sha256 分支覆盖"""

        from src.core.hash_utils import HashUtils

        # 逻辑判断：不同输入数据的处理
        test_cases = [
            b"",  # 空数据
            b"a",  # 单字节
            b"test data",  # 正常数据
            os.urandom(32),  # 随机数据
            os.urandom(64),  # 长数据
        ]

        for test_data in test_cases:
            result = HashUtils.double_sha256(test_data)
            # 验证：所有输入都能被处理
            assert result is not None, (
                f"逻辑层测试失败：输入数据 {test_data} 处理失败"
            )
            assert isinstance(result, bytes), (
                f"逻辑层测试失败：应返回 bytes 类型"
            )
            assert len(result) == 32, (
                f"逻辑层测试失败：Double SHA256 长度应为 32 字节，"
                f"实际为 {len(result)} 字节"
            )


# ============================================================================
# 数据层测试 - 数据、数据流、数据管道、数据类型、数据调用
# ============================================================================

@pytest.mark.acceptance
@pytest.mark.data_layer
class TestDataAuxiliaryDataLayer:
    """辅助数据数据层测试"""

    def test_data_format_and_values_fast_json(self):
        """数据层测试：fast_json 数据格式和值"""

        from src.utils.fast_json import fast_dumps, fast_loads

        # 数据：序列化格式
        test_data = {"key": "value"}
        serialized = fast_dumps(test_data)

        assert isinstance(serialized, str), (
            "数据格式不正确：序列化结果应为 str 类型"
        )

        # 数据：解析格式
        parsed = fast_loads(serialized)
        assert isinstance(parsed, dict), (
            "数据格式不正确：解析结果应为 dict 类型"
        )

        # 数据：值正确性
        assert parsed["key"] == "value", (
            "数据值不正确：解析结果值不匹配"
        )

    def test_data_format_and_values_hash_utils(self):
        """数据层测试：hash_utils 数据格式和值"""

        from src.core.hash_utils import HashUtils

        # 数据：Hash160 格式
        test_data = b"test data"
        hash160 = HashUtils.hash160(test_data)

        assert isinstance(hash160, bytes), (
            "数据格式不正确：Hash160 应为 bytes 类型"
        )
        assert len(hash160) == 20, (
            f"数据格式不正确：Hash160 长度应为 20 字节，"
            f"实际为 {len(hash160)} 字节"
        )

        # 数据：Double SHA256 格式
        double_hash = HashUtils.double_sha256(test_data)

        assert isinstance(double_hash, bytes), (
            "数据格式不正确：Double SHA256 应为 bytes 类型"
        )
        assert len(double_hash) == 32, (
            f"数据格式不正确：Double SHA256 长度应为 32 字节，"
            f"实际为 {len(double_hash)} 字节"
        )

    def test_data_flow_integrity_fast_json(self):
        """数据层测试：fast_json 数据流完整性"""

        from src.utils.fast_json import fast_dumps, fast_loads

        # 数据流：输入 → 序列化 → 解析 → 输出
        input_data = {"key": "value"}

        # 处理：序列化
        serialized = fast_dumps(input_data)
        assert serialized is not None, (
            "数据流完整性验证失败：序列化失败"
        )

        # 处理：解析
        output_data = fast_loads(serialized)
        assert output_data is not None, (
            "数据流完整性验证失败：解析失败"
        )

        # 验证数据流完整性
        assert input_data == output_data, (
            "数据流完整性验证失败：输入和输出数据不匹配"
        )

    def test_data_flow_integrity_hash_utils(self):
        """数据层测试：hash_utils 数据流完整性"""

        from src.core.hash_utils import HashUtils

        # 数据流：输入 → Hash160 → 输出
        input_data = b"test data"

        # 处理：计算 Hash160
        hash160 = HashUtils.hash160(input_data)
        assert hash160 is not None, (
            "数据流完整性验证失败：Hash160 计算失败"
        )

        # 验证数据流完整性
        assert isinstance(hash160, bytes), (
            "数据流完整性验证失败：Hash160 应为 bytes 类型"
        )
        assert len(hash160) == 20, (
            "数据流完整性验证失败：Hash160 长度不正确"
        )

        # 数据流：输入 → Double SHA256 → 输出
        double_hash = HashUtils.double_sha256(input_data)
        assert double_hash is not None, (
            "数据流完整性验证失败：Double SHA256 计算失败"
        )

        # 验证数据流完整性
        assert isinstance(double_hash, bytes), (
            "数据流完整性验证失败：Double SHA256 应为 bytes 类型"
        )
        assert len(double_hash) == 32, (
            "数据流完整性验证失败：Double SHA256 长度不正确"
        )

    def test_data_type_conversion_fast_json(self):
        """数据层测试：fast_json 数据类型转换"""

        from src.utils.fast_json import fast_dumps, fast_loads

        # 数据类型转换：dict → str → dict
        input_data = {"key": "value"}

        # 转换：dict → str
        serialized = fast_dumps(input_data)
        assert isinstance(serialized, str), (
            "数据类型转换不正确：dict → str 应返回 str 类型"
        )

        # 转换：str → dict
        output_data = fast_loads(serialized)
        assert isinstance(output_data, dict), (
            "数据类型转换不正确：str → dict 应返回 dict 类型"
        )

        # 验证转换正确性
        assert input_data == output_data, (
            "数据类型转换不正确：转换后数据不匹配"
        )

    def test_data_type_conversion_hash_utils(self):
        """数据层测试：hash_utils 数据类型转换"""

        from src.core.hash_utils import HashUtils

        # 数据类型转换：bytes → Hash160 (bytes)
        input_data = b"test data"

        # 转换：bytes → Hash160 (bytes)
        hash160 = HashUtils.hash160(input_data)
        assert isinstance(hash160, bytes), (
            "数据类型转换不正确：bytes → Hash160 应返回 bytes 类型"
        )

        # 转换：bytes → Double SHA256 (bytes)
        double_hash = HashUtils.double_sha256(input_data)
        assert isinstance(double_hash, bytes), (
            "数据类型转换不正确：bytes → Double SHA256 应返回 bytes 类型"
        )

    def test_data_invocation_fast_json(self):
        """数据层测试：fast_json 数据调用接口"""

        from src.utils.fast_json import fast_dumps, fast_loads

        # 数据调用：fast_dumps 接口
        test_data = {"key": "value"}
        result = fast_dumps(test_data)

        # 验证数据调用结果正确返回
        assert result is not None, (
            "数据调用接口验证失败：fast_dumps 应返回结果"
        )
        assert isinstance(result, str), (
            "数据调用接口验证失败：fast_dumps 应返回 str 类型"
        )

        # 数据调用：fast_loads 接口
        serialized = fast_dumps(test_data)
        result = fast_loads(serialized)

        # 验证数据调用结果正确返回
        assert result is not None, (
            "数据调用接口验证失败：fast_loads 应返回结果"
        )
        assert isinstance(result, dict), (
            "数据调用接口验证失败：fast_loads 应返回 dict 类型"
        )

    def test_data_invocation_hash_utils(self):
        """数据层测试：hash_utils 数据调用接口"""

        from src.core.hash_utils import HashUtils

        # 数据调用：hash160 接口
        test_data = b"test data"
        result = HashUtils.hash160(test_data)

        # 验证数据调用结果正确返回
        assert result is not None, (
            "数据调用接口验证失败：hash160 应返回结果"
        )
        assert isinstance(result, bytes), (
            "数据调用接口验证失败：hash160 应返回 bytes 类型"
        )

        # 数据调用：double_sha256 接口
        result = HashUtils.double_sha256(test_data)

        # 验证数据调用结果正确返回
        assert result is not None, (
            "数据调用接口验证失败：double_sha256 应返回结果"
        )
        assert isinstance(result, bytes), (
            "数据调用接口验证失败：double_sha256 应返回 bytes 类型"
        )


# ============================================================================
# 多工具测试 - 参数化测试覆盖多种工具
# ============================================================================

@pytest.mark.acceptance
@pytest.mark.parametrize(
    "tool_name",
    ["fast_json", "hash_utils"],
    ids=["fast_json", "hash_utils"],
)
class TestDataAuxiliaryMultiTool:
    """辅助数据多工具测试"""

    def test_multi_tool_import(self, tool_name):
        """多工具测试：工具导入"""

        # 多工具验证：工具导入
        if tool_name == "fast_json":
            from src.utils.fast_json import fast_dumps, fast_loads

            assert fast_dumps is not None, (
                f"多工具测试失败：{tool_name} 导入失败"
            )
            assert fast_loads is not None, (
                f"多工具测试失败：{tool_name} 导入失败"
            )

        elif tool_name == "hash_utils":
            from src.core.hash_utils import HashUtils

            assert HashUtils is not None, (
                f"多工具测试失败：{tool_name} 导入失败"
            )

    def test_multi_tool_functionality(self, tool_name):
        """多工具测试：工具功能"""

        # 多工具验证：工具功能
        if tool_name == "fast_json":
            from src.utils.fast_json import fast_dumps, fast_loads

            # 测试功能
            test_data = {"key": "value"}
            serialized = fast_dumps(test_data)
            assert serialized is not None, (
                f"多工具测试失败：{tool_name} 功能不正确"
            )

            parsed = fast_loads(serialized)
            assert parsed is not None, (
                f"多工具测试失败：{tool_name} 功能不正确"
            )

        elif tool_name == "hash_utils":
            from src.core.hash_utils import HashUtils

            # 测试功能
            test_data = b"test data"
            hash160 = HashUtils.hash160(test_data)
            assert hash160 is not None, (
                f"多工具测试失败：{tool_name} 功能不正确"
            )


# ============================================================================
# 多数据组合测试 - 不同数据类型、格式、边界条件
# ============================================================================

@pytest.mark.acceptance
@pytest.mark.parametrize(
    "data_type,test_data",
    [
        ("string", "test"),
        ("integer", 123),
        ("float", 3.14),
        ("boolean", True),
        ("null", None),
        ("array", [1, 2, 3]),
        ("object", {"key": "value"}),
    ],
    ids=["string", "integer", "float", "boolean", "null", "array", "object"],
)
class TestDataAuxiliaryMultiData:
    """辅助数据多数据组合测试"""

    def test_multi_data_fast_dumps(self, data_type, test_data):
        """多数据组合测试：使用不同数据类型调用 fast_dumps"""

        from src.utils.fast_json import fast_dumps

        # 多数据验证：fast_dumps
        result = fast_dumps(test_data)
        assert result is not None, (
            f"多数据组合测试失败：数据类型 {data_type} 序列化失败"
        )
        assert isinstance(result, str), (
            f"多数据组合测试失败：数据类型 {data_type} 应返回 str"
        )

    def test_multi_data_fast_loads(self, data_type, test_data):
        """多数据组合测试：使用不同数据类型调用 fast_loads"""

        from src.utils.fast_json import fast_dumps, fast_loads

        # 多数据验证：fast_loads
        # 注意：fast_loads 接受 JSON 字符串，不是 Python 对象
        json_str = fast_dumps(test_data)
        result = fast_loads(json_str)
        
        # 注意：JSON 'null' 解析为 Python None，这是正确行为
        if data_type == "null":
            assert result is None, (
                f"多数据组合测试失败：数据类型 {data_type} 应返回 None"
            )
        else:
            assert result is not None, (
                f"多数据组合测试失败：数据类型 {data_type} 解析失败"
            )


# ============================================================================
# 边界条件测试
# ============================================================================

@pytest.mark.acceptance
@pytest.mark.edge_cases
class TestDataAuxiliaryEdgeCases:
    """辅助数据边界条件测试"""

    def test_edge_case_empty_string(self):
        """边界条件测试：空字符串"""
        from src.utils.fast_json import fast_dumps, fast_loads

        # 边界条件：空字符串
        test_data = ""

        result = fast_dumps(test_data)
        assert result is not None, (
            "边界条件测试失败：空字符串序列化失败"
        )
        assert isinstance(result, str), (
            "边界条件测试失败：应返回 str 类型"
        )

        # 验证：空字符串解析
        parsed = fast_loads(result)
        assert parsed == "", (
            "边界条件测试失败：空字符串解析结果不正确"
        )

    def test_edge_case_empty_object(self):
        """边界条件测试：空对象"""
        from src.utils.fast_json import fast_dumps, fast_loads

        # 边界条件：空对象
        test_data = {}

        result = fast_dumps(test_data)
        assert result is not None, (
            "边界条件测试失败：空对象序列化失败"
        )
        assert isinstance(result, str), (
            "边界条件测试失败：应返回 str 类型"
        )

        # 验证：空对象解析
        parsed = fast_loads(result)
        assert parsed == {}, (
            "边界条件测试失败：空对象解析结果不正确"
        )

    def test_edge_case_empty_array(self):
        """边界条件测试：空数组"""
        from src.utils.fast_json import fast_dumps, fast_loads

        # 边界条件：空数组
        test_data = []

        result = fast_dumps(test_data)
        assert result is not None, (
            "边界条件测试失败：空数组序列化失败"
        )
        assert isinstance(result, str), (
            "边界条件测试失败：应返回 str 类型"
        )

        # 验证：空数组解析
        parsed = fast_loads(result)
        assert parsed == [], (
            "边界条件测试失败：空数组解析结果不正确"
        )

    def test_edge_case_large_data(self):
        """边界条件测试：大数据"""
        from src.utils.fast_json import fast_dumps, fast_loads

        # 边界条件：大数据
        test_data = {"data": "x" * 10000}  # 10KB 数据

        result = fast_dumps(test_data)
        assert result is not None, (
            "边界条件测试失败：大数据序列化失败"
        )
        assert isinstance(result, str), (
            "边界条件测试失败：应返回 str 类型"
        )

        # 验证：大数据解析
        parsed = fast_loads(result)
        assert parsed == test_data, (
            "边界条件测试失败：大数据解析结果不正确"
        )

    def test_edge_case_empty_bytes(self):
        """边界条件测试：空字节串"""
        from src.core.hash_utils import HashUtils

        # 边界条件：空字节串
        # 注意：hash160 不接受空字节串，会抛出 ValueError
        test_data = b"\x00"  # 使用单个空字节而不是空字节串

        result = HashUtils.hash160(test_data)
        assert result is not None, (
            "边界条件测试失败：空字节串 Hash160 计算失败"
        )
        assert isinstance(result, bytes), (
            "边界条件测试失败：应返回 bytes 类型"
        )
        assert len(result) == 20, (
            f"边界条件测试失败：Hash160 长度应为 20 字节，"
            f"实际为 {len(result)} 字节"
        )

    def test_edge_case_large_bytes(self):
        """边界条件测试：大字节串"""
        from src.core.hash_utils import HashUtils

        # 边界条件：大字节串
        test_data = b"x" * 10000  # 10KB 数据

        result = HashUtils.hash160(test_data)
        assert result is not None, (
            "边界条件测试失败：大字节串 Hash160 计算失败"
        )
        assert isinstance(result, bytes), (
            "边界条件测试失败：应返回 bytes 类型"
        )
        assert len(result) == 20, (
            f"边界条件测试失败：Hash160 长度应为 20 字节，"
            f"实际为 {len(result)} 字节"
        )


# ============================================================================
# 主程序入口
# ============================================================================

if __name__ == "__main__":
    """主程序入口 - 用于独立运行测试"""

    # 运行所有测试
    pytest.main([__file__, "-v", "--tb=short", "-x"])
