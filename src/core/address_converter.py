"""Bitcoin address format converter.

Provides conversion between different Bitcoin address formats:
- P2PKH, P2SH, Bech32
- Supports address type detection and format validation
"""

import hashlib

from ..utils import get_configured_logger
from ..utils.bech32_codec import bech32_decode, bech32_encode
from .base58 import Base58
from .hash_utils import HashUtils

logger = get_configured_logger("AddressConverter")

# Mainnet version bytes
P2PKH_VERSION = 0x00
P2SH_VERSION = 0x05


class AddressConverter:
    """Bitcoin address format converter.

    Provides conversion and validation between different Bitcoin
    address formats.

    Feature overview:
    - Detect address type (P2PKH / P2SH / Bech32)
    - Convert between formats
    - Validate address format
    - Calculate address hash
    """

    @staticmethod
    def detect_type(address: str) -> str:
        """Detect Bitcoin address type.

        Args:
            address: Bitcoin address string

        Returns:
            Address type string: 'P2PKH', 'P2SH', 'BECH32', or
                'UNKNOWN'
        """
        address = address.strip()
        if not address:
            return "UNKNOWN"
        if address.startswith("1") and 25 <= len(address) <= 34:
            return "P2PKH"
        elif address.startswith("3") and 25 <= len(address) <= 34:
            return "P2SH"
        elif address.lower().startswith("bc1"):
            return "BECH32"
        return "UNKNOWN"

    @staticmethod
    def is_valid_address(address: str) -> bool:
        """Check if address format is valid.

        Args:
            address: Bitcoin address string

        Returns:
            True if address format is valid
        """
        addr_type = AddressConverter.detect_type(address)
        if addr_type == "UNKNOWN":
            return False

        try:
            if addr_type == "BECH32":
                hrp, data, spec = bech32_decode(address)
                return hrp is not None
            else:
                version, hash160 = Base58.check_decode(
                    address
                )
                return len(hash160) == 20
        except (ValueError, TypeError):
            return False

    @staticmethod
    def get_address_hash(address: str) -> bytes | None:
        """Get the hash from an address.

        Extracts the hash embedded in the address.
        For Base58 addresses: returns decoded hash part.
        For Bech32 addresses: returns witness program data.

        Args:
            address: Bitcoin address string

        Returns:
            Address hash bytes, or None if address is invalid
        """
        if not AddressConverter.is_valid_address(address):
            return None
        try:
            addr_type = AddressConverter.detect_type(address)
            if addr_type == "BECH32":
                hrp, data, spec = bech32_decode(address)
                if hrp is None:
                    return None
                return bytes(data[1:])
            else:
                version, hash160 = Base58.check_decode(
                    address
                )
                return hash160
        except (ValueError, TypeError):
            return None

    @staticmethod
    def p2pkh_to_p2sh(address: str) -> str | None:
        """Convert P2PKH address to P2SH address.

        Converts a P2PKH address to corresponding P2SH address.

        Args:
            address: P2PKH address starting with '1'

        Returns:
            P2SH address starting with '3', or None if conversion
            fails
        """
        if AddressConverter.detect_type(address) != "P2PKH":
            return None
        try:
            hash160 = AddressConverter.get_address_hash(
                address
            )
            if hash160 is None:
                return None

            # Build P2PKH redeem script
            redeem_script = (
                bytes([0x76, 0xA9, 0x14])
                + hash160
                + bytes([0x88, 0xAC])
            )

            # Hash160 of redeem script
            script_hash = HashUtils.hash160(redeem_script)

            # Add P2SH version byte
            versioned = (
                bytes([P2SH_VERSION]) + script_hash
            )

            # Base58Check encoding
            checksum = HashUtils.double_sha256(versioned)[
                :4
            ]
            return Base58.encode(versioned + checksum)
        except (ValueError, TypeError) as e:
            logger.debug(
                f"P2PKH to P2SH conversion failed: {e}"
            )
            return None

    @staticmethod
    def p2pkh_to_bech32(address: str) -> str | None:
        """Convert P2PKH address to Bech32 address.

        Converts a P2PKH address to corresponding Bech32 (P2WPKH)
        address.

        Args:
            address: P2PKH address starting with '1'

        Returns:
            Bech32 address starting with 'bc1q', or None if
            conversion fails
        """
        if AddressConverter.detect_type(address) != "P2PKH":
            return None
        try:
            hash160 = AddressConverter.get_address_hash(
                address
            )
            if hash160 is None:
                return None

            return bech32_encode("bc", 0, hash160, "bech32")
        except Exception as e:
            logger.debug(
                f"P2PKH to Bech32 conversion failed: {e}"
            )
            return None


class AddressHashCalculator:
    """Address hash calculator.

    Provides hash calculation for Bitcoin addresses, supporting
    various hash algorithms and formats.
    """

    @staticmethod
    def hash160_to_address(
        hash160: bytes, version_byte: int = 0x00
    ) -> str:
        """Convert Hash160 to Bitcoin address.

        Args:
            hash160: 20-byte Hash160 value
            version_byte: Address version byte (mainnet P2PKH=0x00)

        Returns:
            Bitcoin address string
        """
        return Base58.check_encode(version_byte, hash160)

    @staticmethod
    def double_sha256(data: bytes) -> bytes:
        """Compute double SHA256 hash.

        Args:
            data: Input data

        Returns:
            32-byte hash result
        """
        return hashlib.sha256(
            hashlib.sha256(data).digest()
        ).digest()

    @staticmethod
    def hash160(data: bytes) -> bytes:
        """Compute Hash160 (SHA256 + RIPEMD160).

        Args:
            data: Input data

        Returns:
            20-byte Hash160 result
        """
        return HashUtils.hash160(data)
