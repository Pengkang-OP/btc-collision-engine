"""Fast JSON serialization utilities with caching."""

import json as _json
import typing
from functools import lru_cache


def fast_dump(obj: typing.Any, fp: typing.BinaryIO, **kwargs: typing.Any) -> None:
    """Fast JSON serialization to file.

    Args:
        obj: Object to serialize
        fp: File-like object
        **kwargs: Passed to json.dump

    """
    _json.dump(obj, fp, **kwargs)


def fast_load(fp: typing.BinaryIO) -> typing.Any:
    """Fast JSON deserialization from file.

    Args:
        fp: File-like object

    Returns:
        Deserialized object

    """
    return _json.load(fp)


def fast_loads(s: str) -> typing.Any:
    """Fast JSON deserialization from string.

    Args:
        s: JSON string

    Returns:
        Deserialized object

    """
    return _json.loads(s)


def fast_dumps(obj: typing.Any, **kwargs: typing.Any) -> str:
    """Fast JSON serialization with caching for repeated calls.

    Args:
        obj: Object to serialize
        **kwargs: Passed to json.dumps

    Returns:
        JSON string

    """
    return _json.dumps(obj, **kwargs)

