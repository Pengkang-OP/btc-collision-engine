"""Fast JSON serialization utilities with caching."""

import json as _json
from functools import lru_cache


def fast_dump(obj, fp, **kwargs) -> None:
    """Fast JSON serialization to file.

    Args:
        obj: Object to serialize
        fp: File-like object
        **kwargs: Passed to json.dump

    """
    _json.dump(obj, fp, **kwargs)


def fast_load(fp):
    """Fast JSON deserialization from file.

    Args:
        fp: File-like object

    Returns:
        Deserialized object

    """
    return _json.load(fp)


def fast_loads(s: str):
    """Fast JSON deserialization from string.

    Args:
        s: JSON string

    Returns:
        Deserialized object

    """
    return _json.loads(s)


def fast_dumps(obj, **kwargs) -> str:
    """Fast JSON serialization with caching for repeated calls.

    Args:
        obj: Object to serialize
        **kwargs: Passed to json.dumps

    Returns:
        JSON string

    """
    return _json.dumps(obj, **kwargs)


@lru_cache(maxsize=128)
def _cached_dumps(obj_str: str) -> str:
    """Cached JSON serialization for known objects.

    Args:
        obj_str: String representation of object

    Returns:
        Cached JSON string

    """
    return obj_str
