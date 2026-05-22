#!/usr/bin/env python3
"""Target address resolver for collision engine.

Resolves Bitcoin addresses from various input formats into normalized
representations for matching.
"""

import re
import hashlib
from typing import Optional

from ...utils import get_configured_logger

logger = get_configured_logger("TargetResolver")

# Base58 character map
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _base58_to_bytes(data: str) -> bytes:
    """Decode a Base58 string to bytes.

    Args:
        data: Base58 encoded string

    Returns:
        Decoded bytes
    """
    result = 0
    for char in data:
        result = result * 58 + BASE58_ALPHABET.index(char)
    num_bytes = (result.bit_length() + 7) // 8
    return result.to_bytes(num_bytes, "big")


def _base58_encode(payload: bytes) -> str:
    """Encode bytes to Base58Check format.

    Args:
        payload: Bytes to encode (with version prefix)

    Returns:
        Base58Check encoded string
    """
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    data = payload + checksum
    result = 0
    for byte in data:
        result = result * 256 + byte
    encoded = ""
    while result > 0:
        encoded = BASE58_ALPHABET[result % 58] + encoded
        result //= 58
    leading_zeros = len(data) - len(data.lstrip(b"\x00"))
    encoded = BASE58_ALPHABET[0] * leading_zeros + encoded
    return encoded


def _bech32_decode(address: str) -> tuple[Optional[str], list[int], str]:
    """Decode a bech32 address using local implementation.

    Args:
        address: Bech32 encoded address

    Returns:
        (hrp, data, spec) tuple
    """
    # Simplified bech32 decode for address validation
    if not address:
        return None, [], ""
    s = address.lower().strip()
    if not s.startswith("bc1"):
        return None, [], ""
    # Remove HRP separator
    body = s[3:]  # remove 'bc1'
    if len(body) < 6:
        return None, [], ""
    # Convert bech32 chars to 5-bit values
    charset = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    data = []
    for c in body:
        if c not in charset:
            return None, [], ""
        data.append(charset.index(c))
    return "bc", data, "bech32"


class TargetResolver:
    """Resolves and normalizes Bitcoin target addresses.

    Supports P2PKH, P2SH, Bech32, and raw Hash160 formats with
    automatic format detection.
    """

    MAX_INPUT_LENGTH = 1000

    def __init__(self, enable_cache: bool = True) -> None:
        """Initialize target resolver.

        Args:
            enable_cache: Whether to enable address resolution cache
        """
        self.enable_cache = enable_cache
        self._cache: dict[str, tuple[str, bytes] | None] = {}

    def resolve(self, address: str) -> Optional[str]:
        """Resolve an address string to a normalized target format.

        Args:
            address: Raw address string

        Returns:
            Normalized address string or None if invalid
        """
        if len(address) > self.MAX_INPUT_LENGTH:
            logger.warning(f"Input too long: {len(address)}")
            return None

        s = address.strip()

        # Raw Hash160 (40 hex chars)
        if len(s) == 40 and all(c in "0123456789abcdefABCDEF" for c in s):
            return s.lower()

        # Bech32 (bc1...)
        if s.startswith("bc1"):
            hrp, data, spec = _bech32_decode(s)
            if hrp == "bc" and data:
                return s.lower()
            return None

        # Base58 (P2PKH starting with 1, P2SH starting with 3)
        if s.startswith(("1", "3")):
            try:
                decoded = _base58_to_bytes(s)
                if len(decoded) >= 4:
                    return s
            except (ValueError, IndexError):
                pass
            return None

        logger.debug(f"Unknown address format: {s[:20]}")
        return None

    @staticmethod
    def detect_format(
        input_str: str,
    ) -> str:
        """Detect the format of an address input string.

        Args:
            input_str: Raw input string

        Returns:
            Format string: 'p2pkh', 'p2sh', 'bech32',
                'raw_hash160', or 'unknown'
        """
        if (
            len(input_str)
            > TargetResolver.MAX_INPUT_LENGTH
        ):
            logger.warning(
                f"Input too long: {len(input_str)}"
            )
            return "unknown"
        s = input_str.strip()
        if len(s) == 40 and all(
            c in "0123456789abcdefABCDEF" for c in s
        ):
            return "raw_hash160"
        if s.startswith("1"):
            return "p2pkh"
        if s.startswith("3"):
            return "p2sh"
        if s.startswith("bc1"):
            return "bech32"
        return "unknown"

    def hash160_to_address(self, hash160: bytes, prefix: str = "00") -> str:
        """Convert a Hash160 to a Base58Check address.

        Args:
            hash160: 20-byte Hash160 value
            prefix: Address prefix (00=P2PKH, 05=P2SH)

        Returns:
            Base58Check encoded address string
        """
        version_byte = bytes.fromhex(prefix)
        payload = version_byte + hash160
        return _base58_encode(payload)
