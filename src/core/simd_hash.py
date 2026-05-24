"""SIMD-optimized hash computation module.

Provides batch hash operations optimized for collision detection.
"""

import hashlib

from ..utils import get_configured_logger

logger = get_configured_logger("SIMDHash")


def batch_sha256(data_batch: list[bytes]) -> list[bytes]:
    """Batch SHA-256 hash computation using list comprehension.

    Args:
        data_batch: List of input data bytes

    Returns:
        List of SHA-256 hash results

    """
    return [hashlib.sha256(data).digest() for data in data_batch]


def batch_hash160(data_batch: list[bytes]) -> list[bytes]:
    """Batch Hash160 (SHA-256 + RIPEMD-160) computation.

    Args:
        data_batch: List of input data bytes

    Returns:
        List of Hash160 results

    """
    return [
        hashlib.new(
            "ripemd160",
            hashlib.sha256(data).digest(),
        ).digest()
        for data in data_batch
    ]


def batch_double_sha256(
    data_batch: list[bytes],
) -> list[bytes]:
    """Batch double SHA-256 hash computation.

    Args:
        data_batch: List of input data bytes

    Returns:
        List of double SHA-256 results

    """
    return [
        hashlib.sha256(
            hashlib.sha256(data).digest(),
        ).digest()
        for data in data_batch
    ]
