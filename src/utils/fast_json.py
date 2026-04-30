# -*- coding: utf-8 -*-
"""快速JSON序列化模块 (P3-10)

提供高性能JSON序列化/反序列化，优先使用 orjson（3-5x faster），
不可用时自动降级为标准 json 模块。

orjson 优势:
- 序列化速度 3-5x faster than json
- 原生支持 datetime, UUID, numpy 类型
- 线程安全，无需额外锁

降级策略:
- orjson 不可用时使用标准 json，功能完全兼容
- 自动转换 orjson bytes 输出为 str（保持 API 一致性）

使用示例:
    from src.utils.fast_json import fast_dumps, fast_loads, fast_dump, fast_load

    # 序列化
    data = {"key": "value", "count": 42}
    json_str = fast_dumps(data)  # 返回 str

    # 反序列化
    obj = fast_loads(json_str)

    # 文件操作
    with open("data.json", "w") as f:
        fast_dump(data, f)

参考:
- orjson: https://github.com/ijl/orjson (5.9.0+)
- Python json: https://docs.python.org/3/library/json.html
"""

import json as _json
import logging
from typing import Any, Optional, Union, IO

from . import get_configured_logger

logger = get_configured_logger("FastJSON")

# P3-10: 检测 orjson 可用性
_ORJSON_AVAILABLE = False
_orjson_module = None

try:
    import orjson as _orjson_module
    _ORJSON_AVAILABLE = True
    logger.debug("fast_json: 使用 orjson 加速 JSON 序列化")
except ImportError:
    logger.info("fast_json: orjson 不可用，使用标准 json 模块（性能较低）")


def fast_dumps(
    obj: Any,
    *,
    default: Optional[Any] = None,
    indent: Optional[int] = None,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
    **kwargs
) -> str:
    """高性能 JSON 序列化为字符串

    与 json.dumps 签名兼容。orjson 可用时自动加速。

    Args:
        obj: 要序列化的 Python 对象
        default: 自定义序列化函数（不支持的类型处理）
        indent: 缩进（orjson 仅支持 2，json 支持任意整数）
        ensure_ascii: 是否转义非 ASCII 字符
        sort_keys: 是否对键排序

    Returns:
        JSON 字符串
    """
    if _ORJSON_AVAILABLE:
        try:
            # orjson 选项
            option = 0
            if indent is not None and indent >= 2:
                option |= _orjson_module.OPT_INDENT_2
            if sort_keys:
                option |= _orjson_module.OPT_SORT_KEYS
            # orjson 默认不转义非 ASCII，与 ensure_ascii=False 对应
            if not ensure_ascii:
                option |= _orjson_module.OPT_NON_STR_KEYS

            if default is not None:
                result = _orjson_module.dumps(
                    obj, default=default, option=option
                )
            else:
                result = _orjson_module.dumps(obj, option=option)

            # orjson 返回 bytes，转换为 str
            if isinstance(result, bytes):
                return result.decode('utf-8')
            return result

        except (TypeError, ValueError, OverflowError) as e:
            logger.debug(
                f"orjson 序列化失败 ({type(e).__name__}: {e})，回退到标准 json"
            )
            # 降级到标准 json

    # 标准 json 降级路径
    return _json.dumps(
        obj,
        default=default,
        indent=indent,
        ensure_ascii=ensure_ascii,
        sort_keys=sort_keys,
        **kwargs
    )


def fast_dump(
    obj: Any,
    fp: IO[str],
    *,
    default: Optional[Any] = None,
    indent: Optional[int] = None,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
    **kwargs
) -> None:
    """高性能 JSON 序列化到文件

    与 json.dump 签名兼容。

    Args:
        obj: 要序列化的 Python 对象
        fp: 可写的文件对象
        default: 自定义序列化函数
        indent: 缩进
        ensure_ascii: 是否转义非 ASCII 字符
        sort_keys: 是否对键排序
    """
    json_str = fast_dumps(
        obj,
        default=default,
        indent=indent,
        ensure_ascii=ensure_ascii,
        sort_keys=sort_keys,
        **kwargs
    )
    fp.write(json_str)


def fast_loads(s: Union[str, bytes]) -> Any:
    """高性能 JSON 反序列化（从字符串）

    与 json.loads 签名兼容。

    Args:
        s: JSON 字符串或 bytes

    Returns:
        反序列化的 Python 对象
    """
    if _ORJSON_AVAILABLE:
        try:
            return _orjson_module.loads(s)
        except Exception as e:
            logger.debug(
                f"orjson 反序列化失败 ({type(e).__name__}: {e})，回退到标准 json"
            )

    # 标准 json 降级路径
    if isinstance(s, bytes):
        s = s.decode('utf-8')
    return _json.loads(s)


def fast_load(fp: IO[str]) -> Any:
    """高性能 JSON 反序列化（从文件）

    与 json.load 签名兼容。

    Args:
        fp: 可读的文件对象

    Returns:
        反序列化的 Python 对象
    """
    content = fp.read()
    return fast_loads(content)


def is_orjson_available() -> bool:
    """检查 orjson 是否可用

    Returns:
        True 如果 orjson 已安装
    """
    return _ORJSON_AVAILABLE
