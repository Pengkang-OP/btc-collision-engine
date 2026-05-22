#!/usr/bin/env python3
"""Target address format validator.

Validates Bitcoin addresses for correctness before use in
collision detection.
"""

from ...utils import get_configured_logger
from ...utils.bech32_codec import bech32_decode

logger = get_configured_logger("TargetValidator")


class TargetValidator:
    """Validates Bitcoin address formats for target resolution."""

    @staticmethod
    def validate(address: str) -> bool:
        """Validate a Bitcoin address.

        Args:
            address: Bitcoin address string

        Returns:
            True if address format is valid
        """
        if not address or not isinstance(address, str):
            return False
        address = address.strip()
        if address.startswith("1") and 25 <= len(address) <= 34:
            return True
        if address.startswith("3") and 25 <= len(address) <= 34:
            return True
        if address.lower().startswith("bc1"):
            hrp, data, spec = bech32_decode(address)
            return hrp is not None
        return False

    @staticmethod
    def validate_batch(addresses: list[str]) -> list[tuple[str, bool]]:
        """Validate a batch of addresses.

        Args:
            addresses: List of address strings

        Returns:
            List of (address, is_valid) tuples
        """
        return [
            (addr, TargetValidator.validate(addr))
            for addr in addresses
        ]
