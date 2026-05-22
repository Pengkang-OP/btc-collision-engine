"""Encoding utility functions for Bitcoin data formats."""


class EncodingUtils:
    """Encoding utility class for Bitcoin data formats."""

    @staticmethod
    def bytes_to_hex(data: bytes) -> str:
        return data.hex()

    @staticmethod
    def hex_to_bytes(hex_str: str) -> bytes:
        return bytes.fromhex(hex_str)

    @staticmethod
    def int_to_bytes(value: int, length: int = 32) -> bytes:
        return value.to_bytes(length, "big")

    @staticmethod
    def bytes_to_int(data: bytes) -> int:
        return int.from_bytes(data, "big")


def bytes_to_hex(data: bytes) -> str:
    return data.hex()


def hex_to_bytes(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str)


def int_to_bytes(value: int, length: int = 32) -> bytes:
    return value.to_bytes(length, "big")


def bytes_to_int(data: bytes) -> int:
    return int.from_bytes(data, "big")
