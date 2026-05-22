#!/usr/bin/env python3
"""Target address cache for efficient address lookup."""

from ...utils import get_configured_logger

logger = get_configured_logger("TargetCache")


class TargetCache:
    """Caches resolved target addresses for fast collision lookup."""

    def __init__(self):
        self._hash160_cache: dict[bytes, str] = {}
        self._address_cache: dict[str, bytes] = {}

    def cache_address(
        self, address: str, hash160: bytes
    ) -> None:
        self._hash160_cache[hash160] = address
        self._address_cache[address.lower()] = hash160

    def get_address(
        self, hash160: bytes
    ) -> str | None:
        return self._hash160_cache.get(hash160)

    def get_hash160(self, address: str) -> bytes | None:
        return self._address_cache.get(address.lower())

    def clear(self) -> None:
        self._hash160_cache.clear()
        self._address_cache.clear()
