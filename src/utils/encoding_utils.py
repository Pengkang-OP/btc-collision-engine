"""Encoding utility functions for Bitcoin data formats."""
import hashlib


def bytes_to_hex(data: bytes) -> str:
    """Convert bytes to lowercase hex string.

    Args:
        data: Input bytes

    Returns:
        Hex string
    """
    return data.hex()


def hex_to_bytes(hex_str: str) -> bytes:
    """Convert hex string to bytes.

    Args:
        hex_str: Hex string

    Returns:
        Decoded bytes
    """
    return bytes.fromhex(hex_str)


def int_to_bytes(value: int, length: int = 32) -> bytes:
    """Convert integer to big-endian bytes.

    Args:
        value: Integer value
        length: Output byte length

    Returns:
        Byte representation
    """
    return value.to_bytes(length, "big")


def bytes_to_int(data: bytes) -> int:
    """Convert big-endian bytes to integer.

    Args:
        data: Input bytes

    Returns:
        Integer value
    """
    return int.from_bytes(data, "big")
