"""Multi-format Bitcoin address generator.

Supports generating multiple formats of Bitcoin addresses from a
single private key:
- P2PKH (Pay-to-Public-Key-Hash) - '1' prefix
- P2SH (Pay-to-Script-Hash) - '3' prefix
- Bech32 (SegWit v0) - 'bc1q' prefix
- Taproot (SegWit v1) - 'bc1p' prefix

Usage:
    >>> generator = MultiFormatAddressGenerator()
    >>> private_key = secrets.token_bytes(32)
    >>> addresses = generator.generate_all_formats(private_key)
    >>> print(addresses['p2pkh'], addresses['p2sh'], addresses['bech32'])
"""

__all__ = [
    "AddressFormat",
    "MultiFormatAddressGenerator",
]

import secrets
from enum import Enum

from ..utils import get_configured_logger
from ..utils.bech32_codec import bech32_encode
from .bitcoin_key_validator import BitcoinKeyValidator

logger = get_configured_logger("MultiFormatAddressGenerator")


class AddressFormat(Enum):
    """Bitcoin address format enumeration."""

    P2PKH = "p2pkh"
    P2SH = "p2sh"
    BECH32 = "bech32"
    TAPROOT = "taproot"


class MultiFormatAddressGenerator:
    """Multi-format Bitcoin address generator.

    Generates all supported address formats from a single private key,
    with smart format detection and on-demand generation.

    Attributes:
        auto_detect: Whether to auto-detect supported formats
        prefer_compressed: Whether to prefer compressed public key

    Usage:
        >>> gen = MultiFormatAddressGenerator()
        >>> key = secrets.token_bytes(32)
        >>> all_addrs = gen.generate_all_formats(key)
        >>> p2pkh_only = gen.generate_address(key, AddressFormat.P2PKH)

    """

    def __init__(
        self,
        auto_detect: bool = True,
        prefer_compressed: bool = True,
    ) -> None:
        """Initialize multi-format address generator.

        Args:
            auto_detect: Whether to auto-detect supported formats,
                default True
            prefer_compressed: Whether to prefer compressed public key,
                default True

        """
        self.auto_detect = auto_detect
        self.prefer_compressed = prefer_compressed
        self._public_key_cache: bytes | None = None
        logger.info(
            "MultiFormatAddressGenerator initialized: auto_detect=%s, prefer_compressed=%s",
            auto_detect,
            prefer_compressed,
        )

    def generate_public_key(
        self,
        private_key: bytes,
        compressed: bool = True,
    ) -> bytes:
        """Generate public key from private key.

        Args:
            private_key: 32-byte private key
            compressed: Whether to use compressed format

        Returns:
            Public key bytes (33 bytes compressed / 65 bytes uncompressed)

        """
        from .address_generator import P2PKHAddressGenerator

        generator = P2PKHAddressGenerator()
        return generator.private_key_to_public_key(
            private_key,
            compressed,
        )

    def generate_p2pkh_address(
        self,
        private_key: bytes,
    ) -> str:
        """Generate P2PKH address (Pay-to-Public-Key-Hash).

        Format: '1' prefix, Base58Check encoded.

        Args:
            private_key: 32-byte private key

        Returns:
            P2PKH address string

        """
        public_key = self.generate_public_key(
            private_key,
            self.prefer_compressed,
        )
        from .address_generator import P2PKHAddressGenerator

        generator = P2PKHAddressGenerator()
        return generator.public_key_to_address(public_key)

    def generate_p2sh_address(
        self,
        private_key: bytes,
    ) -> str:
        """Generate P2SH address (Pay-to-Script-Hash).

        Format: '3' prefix, Base58Check encoded.

        Args:
            private_key: 32-byte private key

        Returns:
            P2SH address string

        """
        public_key = self.generate_public_key(
            private_key,
            compressed=True,
        )
        return BitcoinKeyValidator.generate_p2sh_address(
            public_key,
        )

    def generate_bech32_address(
        self,
        private_key: bytes,
        hrp: str = "bc",
    ) -> str:
        """Generate Bech32 address (SegWit v0 - P2WPKH).

        Format: 'bc1q' prefix, Bech32 encoded.

        Args:
            private_key: 32-byte private key
            hrp: Human-readable part (mainnet='bc', testnet='tb')

        Returns:
            Bech32 address string

        """
        public_key = self.generate_public_key(
            private_key,
            compressed=True,
        )
        return BitcoinKeyValidator.generate_bech32_address(
            public_key,
            hrp,
        )

    def generate_taproot_address(
        self,
        private_key: bytes,
        hrp: str = "bc",
    ) -> str:
        """Generate Taproot address (SegWit v1 - P2TR).

        Format: 'bc1p' prefix, Bech32m encoded.

        Note: Taproot uses xonly public key (32 bytes, x coordinate
        only).

        Args:
            private_key: 32-byte private key
            hrp: Human-readable part (mainnet='bc', testnet='tb')

        Returns:
            Taproot address string

        """
        try:
            import coincurve

            priv_key = coincurve.PrivateKey(private_key)
            pub_key = priv_key.public_key
            xonly_pubkey = pub_key.format(compressed=True)[1:33]
            return bech32_encode(hrp, 1, xonly_pubkey, "bech32m")
        except ImportError:
            logger.warning(
                "coincurve not available, cannot generate Taproot address",
            )
            raise ValueError(
                "coincurve not available, cannot generate "
                "Taproot address. "
                "Install: pip install coincurve",
            ) from None
        except Exception as e:
            logger.error(
                "Taproot address generation failed: %s",
                e,
            )
            raise ValueError(
                f"Taproot address generation failed: {e}",
            ) from e

    def generate_address(
        self,
        private_key: bytes,
        format_type: AddressFormat = AddressFormat.P2PKH,
    ) -> str:
        """Generate Bitcoin address of specified format.

        Args:
            private_key: 32-byte private key
            format_type: Address format type

        Returns:
            Bitcoin address in the specified format

        Raises:
            ValueError: When private key length is invalid or format
                is not supported

        """
        if len(private_key) != 32:
            raise ValueError(
                f"Private key must be 32 bytes, got {len(private_key)} bytes",
            )

        if format_type == AddressFormat.P2PKH:
            return self.generate_p2pkh_address(private_key)
        if format_type == AddressFormat.P2SH:
            return self.generate_p2sh_address(private_key)
        if format_type == AddressFormat.BECH32:
            return self.generate_bech32_address(private_key)
        if format_type == AddressFormat.TAPROOT:
            return self.generate_taproot_address(private_key)
        raise ValueError(
            f"Unsupported address format: {format_type}",
        )

    def generate_all_formats(
        self,
        private_key: bytes,
        hrp: str = "bc",
    ) -> dict[str, str]:
        """Generate all supported address formats.

        Args:
            private_key: 32-byte private key
            hrp: Human-readable part (mainnet='bc', testnet='tb')

        Returns:
            Dictionary with all format addresses
            {
                'p2pkh': '1xxx...',
                'p2sh': '3xxx...',
                'bech32': 'bc1qxxx...',
                'taproot': 'bc1pxxx...'
            }

        """
        if len(private_key) != 32:
            raise ValueError(
                f"Private key must be 32 bytes, got {len(private_key)} bytes",
            )

        result = {}

        try:
            result["p2pkh"] = self.generate_p2pkh_address(
                private_key,
            )
        except Exception as e:
            logger.error(
                "P2PKH address generation failed: %s",
                e,
            )
            result["p2pkh"] = ""

        try:
            result["p2sh"] = self.generate_p2sh_address(
                private_key,
            )
        except Exception as e:
            logger.error(
                "P2SH address generation failed: %s",
                e,
            )
            result["p2sh"] = ""

        try:
            result["bech32"] = self.generate_bech32_address(
                private_key,
                hrp,
            )
        except Exception as e:
            logger.error(
                "Bech32 address generation failed: %s",
                e,
            )
            result["bech32"] = ""

        try:
            result["taproot"] = self.generate_taproot_address(
                private_key,
                hrp,
            )
        except Exception as e:
            logger.error(
                "Taproot address generation failed: %s",
                e,
            )
            result["taproot"] = ""

        return result

    def detect_address_format(
        self,
        address: str,
    ) -> AddressFormat:
        """Detect Bitcoin address format.

        Args:
            address: Bitcoin address string

        Returns:
            Address format enum

        Raises:
            ValueError: When address format cannot be identified

        """
        if not address:
            raise ValueError("Address cannot be empty")

        address = address.strip().lower()

        if address.startswith("1"):
            return AddressFormat.P2PKH
        if address.startswith("3"):
            return AddressFormat.P2SH
        if address.startswith("bc1p"):
            return AddressFormat.TAPROOT
        if address.startswith("bc1"):
            return AddressFormat.BECH32
        raise ValueError(
            f"Unrecognized address format: {address[:20]}...",
        )

    def get_targets_by_format(
        self,
        targets: set[str],
    ) -> dict[AddressFormat, set[str]]:
        """Categorize target addresses by format.

        Args:
            targets: Set of target addresses

        Returns:
            Dictionary of addresses grouped by format

        """
        result: dict[AddressFormat, set[str]] = {
            AddressFormat.P2PKH: set(),
            AddressFormat.P2SH: set(),
            AddressFormat.BECH32: set(),
            AddressFormat.TAPROOT: set(),
        }

        for address in targets:
            try:
                fmt = self.detect_address_format(address)
                result[fmt].add(address.lower())
            except ValueError as e:
                logger.warning(
                    f"Cannot detect address format: {address[:20]}... - {e}",
                )

        return result

    def match_address(
        self,
        private_key: bytes,
        targets: dict[AddressFormat, set[str]],
    ) -> tuple[bool, str | None, str | None]:
        """Check if generated address matches any format target.

        [Optimization] Only generates addresses for target formats
        to improve performance.
        [Note] Returns first match; use match_all_formats for all
        matches.

        Args:
            private_key: 32-byte private key
            targets: Dictionary of targets grouped by format

        Returns:
            (is_match, matched_address, matched_format) tuple

        """
        for fmt, target_set in targets.items():
            if len(target_set) == 0:
                continue

            try:
                if fmt == AddressFormat.P2PKH:
                    address = self.generate_p2pkh_address(
                        private_key,
                    )
                elif fmt == AddressFormat.P2SH:
                    address = self.generate_p2sh_address(
                        private_key,
                    )
                elif fmt == AddressFormat.BECH32:
                    address = self.generate_bech32_address(
                        private_key,
                    )
                elif fmt == AddressFormat.TAPROOT:
                    address = self.generate_taproot_address(
                        private_key,
                    )
                else:
                    continue

                if address and address.lower() in target_set:
                    return True, address, fmt.value

            except Exception as e:
                logger.warning(
                    f"Failed to generate {fmt.value} address: {e}",
                )
                continue

        return False, None, None

    def match_all_formats(
        self,
        private_key: bytes,
        targets: dict[AddressFormat, set[str]],
    ) -> tuple[bool, list[tuple[str, str]]]:
        """Check if generated address matches all target format addresses.

        [Full check] Iterates all target formats, returns all
        matching addresses.

        Args:
            private_key: 32-byte private key
            targets: Dictionary of targets grouped by format

        Returns:
            (is_match, list[tuple[address, format]]) tuple
            e.g. (True, [("1xxx...", "p2pkh"),
                         ("bc1q...", "bech32")])

        """
        matches = []
        for fmt, target_set in targets.items():
            if len(target_set) == 0:
                continue

            try:
                if fmt == AddressFormat.P2PKH:
                    address = self.generate_p2pkh_address(
                        private_key,
                    )
                elif fmt == AddressFormat.P2SH:
                    address = self.generate_p2sh_address(
                        private_key,
                    )
                elif fmt == AddressFormat.BECH32:
                    address = self.generate_bech32_address(
                        private_key,
                    )
                elif fmt == AddressFormat.TAPROOT:
                    address = self.generate_taproot_address(
                        private_key,
                    )
                else:
                    continue

                if address and address.lower() in target_set:
                    matches.append(
                        (address, fmt.value),
                    )

            except Exception as e:
                logger.warning(
                    f"Failed to generate {fmt.value} address: {e}",
                )
                continue

        return len(matches) > 0, matches

    def validate_format_support(
        self,
    ) -> dict[str, bool]:
        """Validate format generation support status.

        Returns:
            Format support status dictionary

        """
        test_key = secrets.token_bytes(32)

        return {
            "p2pkh": bool(
                self.generate_p2pkh_address(test_key),
            ),
            "p2sh": bool(
                self.generate_p2sh_address(test_key),
            ),
            "bech32": bool(
                self.generate_bech32_address(test_key),
            ),
            "taproot": bool(
                self.generate_taproot_address(test_key),
            ),
        }
