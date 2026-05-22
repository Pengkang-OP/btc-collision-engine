#!/usr/bin/env python3
"""Format-aware target manager for multi-type address matching."""

from ...utils import get_configured_logger

logger = get_configured_logger("FormatAwareManager")


class FormatAwareManager:
    """Manages targets across multiple address formats."""

    def __init__(self):
        self._p2pkh: set[str] = set()
        self._p2sh: set[str] = set()
        self._bech32: set[str] = set()

    def add(
        self, address: str, fmt: str
    ) -> None:
        if fmt == "p2pkh":
            self._p2pkh.add(address.lower())
        elif fmt == "p2sh":
            self._p2sh.add(address.lower())
        elif fmt == "bech32":
            self._bech32.add(address.lower())

    def get_targets(
        self, fmt: str
    ) -> set[str]:
        if fmt == "p2pkh":
            return self._p2pkh
        elif fmt == "p2sh":
            return self._p2sh
        elif fmt == "bech32":
            return self._bech32
        return set()
