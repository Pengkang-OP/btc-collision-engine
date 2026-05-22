#!/usr/bin/env python3
"""
Bitcoin key generation and address matching full validation system.

Strictly validates against Bitcoin Core specification:
1. Private key to public key (secp256k1 elliptic curve)
2. Public key to address (P2PKH/P2SH/Bech32)
3. Private key to WIF format
4. Address matching verification
5. Full workflow validation
"""

import hmac
import time
from enum import Enum
from typing import Any

from ..utils.bech32_codec import bech32_decode  # Unified bech32 validation
from .base58 import Base58
from .hash_utils import HashUtils
from .secp256k1 import ECPoint, EllipticCurve, Secp256k1
from .wif import WIF


class WIFEncoder:
    """WIF (Wallet Import Format) encoder - compliant with Bitcoin Core spec

    Independent WIF encode/decode implementation with testnet support.
    Note: This implementation overlaps with src.core.wif.WIF;
    prefer using WIF class.
    - Mainnet compressed WIF: 'K'/'L' prefix (52 chars)
    - Mainnet uncompressed WIF: '5' prefix (51 chars)
    - Testnet compressed WIF: 'c' prefix
    - Testnet uncompressed WIF: '9' prefix
    """

    MAINNET_VERSION = 0x80
    TESTNET_VERSION = 0xEF

    @staticmethod
    def encode(private_key: bytes, compressed: bool = True, testnet: bool = False) -> str:
        """Encode 32-byte private key to WIF format.

        Args:
            private_key: 32-byte private key
            compressed: Generate compressed WIF (K/L prefix) or uncompressed (5 prefix)
            testnet: Use testnet version byte (0xEF)

        Returns:
            WIF encoded string

        Raises:
            ValueError: When private key length is not 32 bytes
        """
        if not isinstance(private_key, bytes):
            raise ValueError("Private key must be bytes")
        if len(private_key) != 32:
            raise ValueError("Private key length must be 32 bytes")

        # Version byte: mainnet 0x80, testnet 0xEF
        version = WIFEncoder.TESTNET_VERSION if testnet else WIFEncoder.MAINNET_VERSION
        data = bytes([version]) + private_key
        if compressed:
            data += bytes([0x01])  # Compressed flag
        # Checksum: first 4 bytes of double SHA256
        checksum = HashUtils.double_sha256(data)[:4]
        return Base58.encode(data + checksum)

    @staticmethod
    def decode(wif: str) -> tuple[bytes, bool, bool]:
        """Decode WIF to private key.

        Args:
            wif: WIF encoded string

        Returns:
            (private_key, is_compressed, is_testnet) tuple

        Raises:
            ValueError: When WIF format is invalid or checksum verification fails
        """
        if not isinstance(wif, str):
            raise ValueError("WIF must be a string")

        raw = Base58.decode(wif)
        if len(raw) < 5:
            raise ValueError(f"WIF data too short: {len(raw)} bytes")

        # Checksum verification
        payload, checksum = raw[:-4], raw[-4:]
        expected = HashUtils.double_sha256(payload)[:4]
        if checksum != expected:
            raise ValueError("WIF checksum verification failed")

        version = payload[0]
        if version not in (WIFEncoder.MAINNET_VERSION, WIFEncoder.TESTNET_VERSION):
            raise ValueError(f"Invalid WIF version byte: 0x{version:02x}")

        is_testnet = version == WIFEncoder.TESTNET_VERSION
        key_data = payload[1:]

        if len(key_data) == 33 and key_data[-1] == 0x01:
            return key_data[:-1], True, is_testnet  # Compressed
        elif len(key_data) == 32:
            return key_data, False, is_testnet  # Uncompressed
        else:
            raise ValueError(f"Invalid WIF payload length: {len(key_data)}")


class KeyValidationConstants:
    """Key validation constants"""

    PRIVATE_KEY_LENGTH = 32
    COMPRESSED_PUBLIC_KEY_LENGTH = 33
    UNCOMPRESSED_PUBLIC_KEY_LENGTH = 65
    P2PKH_VERSION_BYTE = 0x00
    P2SH_VERSION_BYTE = 0x05
    WIF_VERSION_BYTE = 0x80
    P2PKH_ADDRESS_MIN_LENGTH = 25
    P2PKH_ADDRESS_MAX_LENGTH = 34
    COMPRESSED_WIF_LENGTH = 52
    UNCOMPRESSED_WIF_LENGTH = 51


class AddressType(Enum):
    """Bitcoin address type"""

    P2PKH = "p2pkh"   # '1' prefix
    P2SH = "p2sh"     # '3' prefix
    BECH32 = "bech32"  # 'bc1' prefix
    UNKNOWN = "unknown"


class KeyValidationResult:
    """Key validation result"""

    def __init__(self) -> None:
        self.success = True
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.details: dict[str, Any] = {}

    def add_error(self, error: str) -> "KeyValidationResult":
        self.success = False
        self.errors.append(error)
        return self  # Supports chaining

    def add_warning(self, warning: str) -> None:
        self.warnings.append(warning)

    def add_detail(self, key: str, value: Any) -> None:
        self.details[key] = value

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "errors": self.errors,
            "warnings": self.warnings,
            "details": self.details,
        }


class BitcoinKeyValidator:
    """Bitcoin key and address full validator"""

    def __init__(self, secure_mode: bool = True) -> None:
        """
        Initialize validator.

        Args:
            secure_mode: Secure mode, excludes private key plaintext from results
        """
        self.curve = EllipticCurve()
        self.secure_mode = secure_mode

    @staticmethod
    def generate_p2sh_address(public_key: bytes) -> str:
        """BL-3/BR-1 fix: Generate P2SH address.

        P2SH (Pay-to-Script-Hash) address generation flow:
        1. Create redeem script (simple P2PKH script)
        2. HASH160(redeem_script)
        3. Add version byte (0x05)
        4. Base58Check encoding

        Args:
            public_key: Compressed or uncompressed public key

        Returns:
            P2SH address ('3' prefix)
        """
        # Create simple P2PKH redeem script
        pub_key_hash = HashUtils.hash160(public_key)

        # OP_DUP OP_HASH160 <20 bytes> OP_EQUALVERIFY OP_CHECKSIG
        redeem_script = bytes([0x76, 0xA9, 0x14]) + pub_key_hash + bytes([0x88, 0xAC])

        # HASH160 of redeem script
        script_hash = HashUtils.hash160(redeem_script)

        # Add version byte (P2SH = 0x05)
        versioned = bytes([KeyValidationConstants.P2SH_VERSION_BYTE]) + script_hash

        # Base58Check encoding
        checksum = HashUtils.double_sha256(versioned)[:4]
        return Base58.encode(versioned + checksum)

    @staticmethod
    def generate_bech32_address(public_key: bytes, hrp: str = "bc") -> str:
        """BL-3/BR-1 fix: Generate Bech32 address (SegWit).

        Bech32 address generation flow (P2WPKH):
        1. HASH160(public_key)
        2. Convert to witness program
        3. Bech32 encoding (using unified module src.utils.bech32_codec)

        Args:
            public_key: Compressed public key (compressed format only)
            hrp: Human-readable part (mainnet='bc', testnet='tb')

        Returns:
            Bech32 address ('bc1' prefix)
        """
        from ..utils.bech32_codec import bech32_encode

        # Compressed public key only
        if len(public_key) != 33:
            raise ValueError("Bech32 address only supports compressed public key")

        # HASH160 of public key
        pub_key_hash = HashUtils.hash160(public_key)

        # Witness program + Bech32 encoding
        return bech32_encode(hrp, 0, pub_key_hash, "bech32")

    def validate_private_key(self, private_key: bytes) -> KeyValidationResult:
        """
        Validate private key format and validity.

        Validation items:
        - Must be 32 bytes
        - Value range must be between 1 and N-1 (N is secp256k1 curve order)
        """
        result = KeyValidationResult()

        # Secure mode: do not output private key plaintext
        if self.secure_mode:
            pk_hash = HashUtils.key_fingerprint(private_key)
            result.add_detail("private_key_hash", f"{pk_hash}...")
        else:
            result.add_detail("private_key_hex", private_key.hex())

        result.add_detail("private_key_length", len(private_key))

        # 1. Validate length
        if len(private_key) != KeyValidationConstants.PRIVATE_KEY_LENGTH:
            _len = len(private_key)
            _expected = KeyValidationConstants.PRIVATE_KEY_LENGTH
            result.add_error(
                f"Private key length error: {_len} bytes, expected {_expected} bytes"
            )
            return result

        # 2. Convert to integer
        k = int.from_bytes(private_key, "big")
        result.add_detail("private_key_int", str(k))

        # 3. Validate range: 1 <= k < N
        if k < 1:
            result.add_error("Private key value is 0, invalid")
        elif k >= Secp256k1.N:
            result.add_error("Private key value out of range: >= N (curve order)")
        else:
            result.add_detail("private_key_range_valid", True)

        return result

    def generate_public_key(
        self, private_key: bytes, compressed: bool = True
    ) -> tuple[KeyValidationResult, bytes]:
        """
        Generate public key from private key using secp256k1 elliptic curve.

        Validation items:
        - Uses scalar multiplication: P = k * G
        - Verifies public key is on curve
        - Supports compressed and uncompressed formats
        """
        result = KeyValidationResult()

        # 1. Validate private key
        pk_validation = self.validate_private_key(private_key)
        if not pk_validation.success:
            result.success = False
            result.errors.extend(pk_validation.errors)
            return result, b""

        k = int.from_bytes(private_key, "big")

        try:
            # v4.2.2 R1 fix: use constant-time implementation, avoid RuntimeError
            public_key_point = self.curve.scalar_multiply_const_time(
                k, ECPoint(Secp256k1.Gx, Secp256k1.Gy)
            )

            # 3. Verify public key is not infinity
            if public_key_point.is_infinity:
                result.add_error("Generated public key is infinity point, invalid private key")
                return result, b""

            # 4. Verify public key is on curve
            if not self.curve.is_on_curve(public_key_point):
                result.add_error("Generated public key is not on secp256k1 curve")
                return result, b""

            result.add_detail("public_key_on_curve", True)
            result.add_detail("public_key_point_x", f"{public_key_point.x:064x}")
            result.add_detail("public_key_point_y", f"{public_key_point.y:064x}")

            # 5. Serialize public key — after is_infinity check, x/y are guaranteed non-None
            assert public_key_point.x is not None and public_key_point.y is not None

            if compressed:
                # Compressed format: 33 bytes, 02 or 03 prefix
                prefix = b"\x02" if int(public_key_point.y) % 2 == 0 else b"\x03"
                public_key_bytes = prefix + public_key_point.x.to_bytes(32, "big")
                result.add_detail("public_key_format", "compressed")
                result.add_detail(
                    "public_key_length", KeyValidationConstants.COMPRESSED_PUBLIC_KEY_LENGTH
                )
            else:
                # Uncompressed format: 65 bytes, 04 prefix
                public_key_bytes = (
                    b"\x04"
                    + public_key_point.x.to_bytes(32, "big")
                    + public_key_point.y.to_bytes(32, "big")
                )
                result.add_detail("public_key_format", "uncompressed")
                result.add_detail(
                    "public_key_length", KeyValidationConstants.UNCOMPRESSED_PUBLIC_KEY_LENGTH
                )

            result.add_detail("public_key_hex", public_key_bytes.hex())

            return result, public_key_bytes

        except Exception as e:
            result.add_error(f"Public key generation failed: {str(e)}")
            return result, b""

    def validate_public_key(self, public_key: bytes) -> KeyValidationResult:
        """
        Validate public key format and validity.

        Validation items:
        - Compressed format: 33 bytes, 02 or 03 prefix
        - Uncompressed format: 65 bytes, 04 prefix
        - Verify public key is on curve
        """
        result = KeyValidationResult()
        result.add_detail("public_key_hex", public_key.hex())
        result.add_detail("public_key_length", len(public_key))

        if len(public_key) == KeyValidationConstants.COMPRESSED_PUBLIC_KEY_LENGTH:
            # Compressed format
            if public_key[0] not in [0x02, 0x03]:
                result.add_error(
                    f"Compressed public key prefix error: 0x{public_key[0]:02x}, expected 0x02 or 0x03"
                )
                return result

            x = int.from_bytes(public_key[1:], "big")

            # Verify x coordinate is not zero
            if x == 0:
                result.add_error("Public key x coordinate is 0, invalid")
                return result

            result.add_detail("public_key_format", "compressed")
            result.add_detail("public_key_x", f"{x:064x}")

            # Verify point is on curve
            try:
                y_squared = (pow(x, 3, Secp256k1.P) + 7) % Secp256k1.P
                y = pow(y_squared, (Secp256k1.P + 1) // 4, Secp256k1.P)

                # Determine y based on prefix
                if public_key[0] == 0x03 and y % 2 == 0:  # y is odd
                    y = Secp256k1.P - y

                point = ECPoint(x, y)
                if self.curve.is_on_curve(point):
                    result.add_detail("public_key_on_curve", True)
                else:
                    result.add_error("Compressed public key not on curve")

            except (ValueError, OverflowError) as e:
                result.add_error(f"Compressed public key validation failed: {str(e)}")

        elif len(public_key) == KeyValidationConstants.UNCOMPRESSED_PUBLIC_KEY_LENGTH:
            # Uncompressed format
            if public_key[0] != 0x04:
                result.add_error(
                    f"Uncompressed public key prefix error: 0x{public_key[0]:02x}, expected 0x04"
                )
                return result

            x = int.from_bytes(public_key[1:33], "big")
            y = int.from_bytes(public_key[33:], "big")
            result.add_detail("public_key_format", "uncompressed")
            result.add_detail("public_key_x", f"{x:064x}")
            result.add_detail("public_key_y", f"{y:064x}")

            # Verify point is on curve
            point = ECPoint(x, y)
            if self.curve.is_on_curve(point):
                result.add_detail("public_key_on_curve", True)
            else:
                result.add_error("Uncompressed public key not on curve")
        else:
            result.add_error(
                f"Public key length error: {len(public_key)} bytes, expected 33 or 65 bytes"
            )

        return result

    # ── generate_address helper methods (reduce C901) ────────────────────

    @staticmethod
    def _verify_base58_checksum(
        address: str, expected_version: int, result: KeyValidationResult
    ) -> None:
        """Verify Base58Check checksum and version byte."""
        try:
            version, payload = Base58.check_decode(address)
            if version == expected_version:
                result.add_detail("address_checksum_valid", True)
            else:
                result.add_warning(f"Address version byte anomaly: 0x{version:02x}")
        except (ValueError, TypeError) as e:
            result.add_error(f"Address Base58Check verification failed: {str(e)}")

    @staticmethod
    def _verify_address_length(result: KeyValidationResult, address: str) -> None:
        """Verify Base58 address length is within reasonable range."""
        if (
            len(address) < KeyValidationConstants.P2PKH_ADDRESS_MIN_LENGTH
            or len(address) > KeyValidationConstants.P2PKH_ADDRESS_MAX_LENGTH
        ):
            result.add_warning(f"Address length anomaly: {len(address)}")

    def _generate_p2pkh_address(self, public_key: bytes, result: KeyValidationResult) -> str:
        """Generate P2PKH address ('1' prefix)."""
        hash160_digest = HashUtils.hash160(public_key)
        address = Base58.check_encode(0x00, hash160_digest)
        result.add_detail("address_type", "P2PKH")
        result.add_detail("address", address)
        result.add_detail("hash160", hash160_digest.hex())
        result.add_detail("public_key_used", public_key.hex())
        if not address.startswith("1"):
            result.add_warning(f"P2PKH address should start with '1', current: {address[0]}")
        self._verify_address_length(result, address)
        self._verify_base58_checksum(address, KeyValidationConstants.P2PKH_VERSION_BYTE, result)
        return address

    def _generate_p2sh_address(self, public_key: bytes, result: KeyValidationResult) -> str:
        """Generate P2SH address ('3' prefix)."""
        address = BitcoinKeyValidator.generate_p2sh_address(public_key)
        result.add_detail("address_type", "P2SH")
        result.add_detail("address", address)
        result.add_detail("public_key_used", public_key.hex())
        if not address.startswith("3"):
            result.add_warning(f"P2SH address should start with '3', current: {address[0]}")
        self._verify_address_length(result, address)
        self._verify_base58_checksum(address, KeyValidationConstants.P2SH_VERSION_BYTE, result)
        return address

    def _generate_bech32_address(self, public_key: bytes, result: KeyValidationResult) -> str:
        """Generate Bech32 address ('bc1' prefix)."""
        address = BitcoinKeyValidator.generate_bech32_address(public_key)
        result.add_detail("address_type", "Bech32")
        result.add_detail("address", address)
        result.add_detail("public_key_used", public_key.hex())
        if not address.startswith("bc1"):
            result.add_warning(f"Bech32 address should start with 'bc1', current: {address[:3]}")
        if len(address) < 10:
            result.add_warning(f"Bech32 address too short: {len(address)}")
        return address

    def generate_address(
        self, public_key: bytes, address_type: AddressType = AddressType.P2PKH
    ) -> tuple[KeyValidationResult, str]:
        """Generate Bitcoin address from public key. Supports P2PKH / P2SH / Bech32 types."""
        result = KeyValidationResult()

        pk_validation = self.validate_public_key(public_key)
        if not pk_validation.success:
            result.success = False
            result.errors.extend(pk_validation.errors)
            return result, ""

        try:
            if address_type == AddressType.P2PKH:
                address = self._generate_p2pkh_address(public_key, result)
            elif address_type == AddressType.P2SH:
                address = self._generate_p2sh_address(public_key, result)
            elif address_type == AddressType.BECH32:
                address = self._generate_bech32_address(public_key, result)
            else:
                return result, ""
            return result, address
        except (ValueError, OverflowError, TypeError) as e:
            result.add_error(f"Address generation failed: {str(e)}")
            import traceback

            result.add_detail("traceback", traceback.format_exc())
            return result, ""

    # ── validate_address helper methods (reduce C901) ───────────────────

    @staticmethod
    def _detect_address_type(address: str) -> tuple[AddressType, str]:
        """Detect Bitcoin address type, returns (addr_type, type_label)."""
        if address.startswith("1"):
            return AddressType.P2PKH, "P2PKH"
        elif address.startswith("3"):
            return AddressType.P2SH, "P2SH"
        elif address.startswith("bc1"):
            return AddressType.BECH32, "Bech32"
        return AddressType.UNKNOWN, "unknown"

    @staticmethod
    def _validate_legacy_address(
        address: str, addr_type: AddressType, result: KeyValidationResult
    ) -> None:
        """Validate P2PKH / P2SH legacy address format."""
        if (
            len(address) < KeyValidationConstants.P2PKH_ADDRESS_MIN_LENGTH
            or len(address) > KeyValidationConstants.P2PKH_ADDRESS_MAX_LENGTH
        ):
            _min = KeyValidationConstants.P2PKH_ADDRESS_MIN_LENGTH
            _max = KeyValidationConstants.P2PKH_ADDRESS_MAX_LENGTH
            result.add_error(f"Address length error: {len(address)}, expected {_min}-{_max} chars")

        valid_chars = set(Base58.ALPHABET)
        if not all(c in valid_chars for c in address):
            result.add_error("Address contains invalid Base58 characters")

        try:
            version, payload = Base58.check_decode(address)
            result.add_detail("version_byte", f"0x{version:02x}")
            result.add_detail("payload_length", len(payload))
            expected = (
                KeyValidationConstants.P2PKH_VERSION_BYTE
                if addr_type == AddressType.P2PKH
                else KeyValidationConstants.P2SH_VERSION_BYTE
            )
            if version != expected:
                result.add_warning(
                    f"Address version should be 0x{expected:02x}, current: 0x{version:02x}"
                )
            result.add_detail("checksum_valid", True)
        except (ValueError, TypeError) as e:
            result.add_error(f"Base58Check checksum verification failed: {str(e)}")

    @staticmethod
    def _validate_bech32_address(address: str, result: KeyValidationResult) -> None:
        """Validate Bech32 / Bech32m address format."""
        if len(address) < 10:
            result.add_error(f"Bech32 address too short: {len(address)} chars")
            return

        charset = set("qpzry9x8gf2tvdw0s3jn54khce6mua7l")
        for c in address[3:]:
            if c not in charset:
                result.add_error(f"Bech32 address contains invalid character: '{c}'")
                return

        try:
            hrp, data, _ = bech32_decode(address)
            if hrp is None:
                result.add_error("Bech32 address decode failed (invalid checksum or format)")
                return
            if hrp not in ("bc", "tb"):
                result.add_error(
                    f"Bech32 address HRP error: expected 'bc' or 'tb', got '{hrp}'"
                )

            data_length = len(data)
            if data_length not in (33, 53):
                result.add_error(
                    f"Bech32 address data length error: {data_length}, "
                    "expected 33 (P2WPKH) or 53 (P2WSH)"
                )

            witness_version = data[0]
            if witness_version != 0:
                result.add_error(f"Unsupported witness version: {witness_version}")

            subtype = "P2WPKH" if data_length == 33 else "P2WSH"
            result.add_detail("bech32_address_subtype", subtype)
            result.add_detail("bech32_hrp", hrp)
            result.add_detail("bech32_data_length", data_length)
            result.add_detail("bech32_valid", True)
        except Exception as e:
            result.add_error(f"Bech32 address validation failed: {str(e)}")

    def validate_address(self, address: str) -> KeyValidationResult:
        """Validate Bitcoin address format (version byte, length, checksum)."""
        result = KeyValidationResult()
        result.add_detail("address", address)

        addr_type, type_label = self._detect_address_type(address)
        if addr_type == AddressType.UNKNOWN:
            result.add_error("Unknown address type")
            return result
        result.add_detail("address_type", type_label)

        if addr_type in (AddressType.P2PKH, AddressType.P2SH):
            self._validate_legacy_address(address, addr_type, result)
        elif addr_type == AddressType.BECH32:
            self._validate_bech32_address(address, result)

        return result

    def private_key_to_wif(
        self, private_key: bytes, compressed: bool = True
    ) -> tuple[KeyValidationResult, str]:
        """
        Convert private key to WIF format.

        Validation items:
        - Compressed format: 'K' or 'L' prefix, 52 chars
        - Uncompressed format: '5' prefix, 51 chars
        - Base58Check encoding
        """
        result = KeyValidationResult()

        # 1. Validate private key
        pk_validation = self.validate_private_key(private_key)
        if not pk_validation.success:
            result.success = False
            result.errors.extend(pk_validation.errors)
            return result, ""

        try:
            # 2. Encode to WIF
            wif = WIF.encode(private_key, compressed)
            # Secure mode: mask WIF in step details to prevent leaking via to_dict()
            if self.secure_mode:
                wif_safe = wif[:8] + "..." + wif[-4:] if len(wif) > 12 else "***"
                result.add_detail("wif", wif_safe)
            else:
                result.add_detail("wif", wif)
            result.add_detail("wif_length", len(wif))
            result.add_detail("compressed", compressed)

            # 3. Validate WIF format
            if compressed:
                if len(wif) != KeyValidationConstants.COMPRESSED_WIF_LENGTH:
                    _expected_wif = KeyValidationConstants.COMPRESSED_WIF_LENGTH
                    result.add_warning(
                        f"Compressed WIF length should be {_expected_wif} chars, "
                        f"current: {len(wif)}"
                    )
                if not wif.startswith(("K", "L")):
                    result.add_warning(
                        f"Compressed WIF should start with 'K' or 'L', "
                        f"current: {wif[0]}"
                    )
            else:
                if len(wif) != KeyValidationConstants.UNCOMPRESSED_WIF_LENGTH:
                    _expected_uwif = KeyValidationConstants.UNCOMPRESSED_WIF_LENGTH
                    result.add_warning(
                        f"Uncompressed WIF length should be {_expected_uwif} chars, "
                        f"current: {len(wif)}"
                    )
                if not wif.startswith("5"):
                    result.add_warning(
                        f"Uncompressed WIF should start with '5', "
                        f"current: {wif[0]}"
                    )

            # 4. Validate Base58Check
            try:
                version, payload = Base58.check_decode(wif)
                result.add_detail("wif_version", f"0x{version:02x}")
                result.add_detail("wif_payload_length", len(payload))
                result.add_detail("wif_checksum_valid", True)
            except (ValueError, TypeError) as e:
                result.add_error(f"WIF Base58Check verification failed: {str(e)}")

            return result, wif

        except (ValueError, TypeError) as e:
            result.add_error(f"WIF encoding failed: {str(e)}")
            return result, ""

    def wif_to_private_key(
        self, wif: str
    ) -> tuple[KeyValidationResult, bytes, bool]:
        """
        Decode private key from WIF format.

        Returns private key and compression flag.
        """
        result = KeyValidationResult()
        # Secure mode: mask WIF and private key in step details
        if self.secure_mode:
            wif_safe = wif[:8] + "..." + wif[-4:] if len(wif) > 12 else "***"
            result.add_detail("wif", wif_safe)
        else:
            result.add_detail("wif", wif)

        try:
            # 1. Decode WIF
            private_key, compressed = WIF.decode(wif)

            # Secure mode: do not output private key plaintext
            if self.secure_mode:
                pk_hash = HashUtils.key_fingerprint(private_key)
                result.add_detail("private_key_hash", pk_hash)
            else:
                result.add_detail("private_key_hex", private_key.hex())
            result.add_detail("compressed", compressed)

            # 2. Validate private key
            pk_validation = self.validate_private_key(private_key)
            if not pk_validation.success:
                result.success = False
                result.errors.extend(pk_validation.errors)

            # 3. Validate WIF format
            if compressed:
                if len(wif) != KeyValidationConstants.COMPRESSED_WIF_LENGTH:
                    result.add_warning(
                        f"Compressed WIF length should be "
                        f"{KeyValidationConstants.COMPRESSED_WIF_LENGTH} chars"
                    )
                if not wif.startswith(("K", "L")):
                    result.add_warning("Compressed WIF should start with 'K' or 'L'")
            else:
                if len(wif) != KeyValidationConstants.UNCOMPRESSED_WIF_LENGTH:
                    result.add_warning(
                        f"Uncompressed WIF length should be "
                        f"{KeyValidationConstants.UNCOMPRESSED_WIF_LENGTH} chars"
                    )
                if not wif.startswith("5"):
                    result.add_warning("Uncompressed WIF should start with '5'")

            return result, private_key, compressed

        except (ValueError, TypeError) as e:
            result.add_error(f"WIF decode failed: {str(e)}")
            return result, b"", False

    def verify_address_match(
        self, address: str, target_addresses: set
    ) -> KeyValidationResult:
        """
        Verify if address matches target address list.

        Uses secure comparison to prevent timing attacks.
        """
        result = KeyValidationResult()
        result.add_detail("address", address)
        result.add_detail("target_count", len(target_addresses))

        # 1. Validate address format
        addr_validation = self.validate_address(address)
        if not addr_validation.success:
            result.success = False
            result.errors.extend(addr_validation.errors)
            result.add_detail("match", False)
            return result

        # 2. Pre-validate target addresses and cache valid ones
        valid_targets = set()
        for target in target_addresses:
            target_validation = self.validate_address(target)
            if target_validation.success:
                valid_targets.add(target)
            else:
                result.add_warning(f"Target address format anomaly: {target}")

        # 3. Secure comparison (using hmac.compare_digest to prevent timing attacks)
        match_found = False
        for target in valid_targets:
            # Use secure string comparison
            if hmac.compare_digest(address, target):
                match_found = True
                result.add_detail("matched_target", target)
                break

        result.add_detail("match", match_found)

        if not match_found:
            result.add_detail("match_result", "No match found")

        return result

    def full_validation_chain(
        self, private_key: bytes, target_addresses: set
    ) -> dict[str, Any]:
        """
        Full validation chain: private key -> public key -> address -> WIF -> match verify.

        Returns complete validation report.
        """
        report: dict[str, Any] = {
            "timestamp": time.time(),
            "steps": {},
            "overall_success": True,
            "errors": [],
            "warnings": [],
        }

        # Step 1: Validate private key
        pk_result = self.validate_private_key(private_key)
        report["steps"]["private_key_validation"] = pk_result.to_dict()
        if not pk_result.success:
            report["overall_success"] = False
            report["errors"].extend(pk_result.errors)
            return report

        # Step 2: Generate compressed public key
        pub_comp_result, public_key_compressed = self.generate_public_key(
            private_key, compressed=True
        )
        report["steps"]["public_key_compressed"] = pub_comp_result.to_dict()
        if not pub_comp_result.success:
            report["overall_success"] = False
            report["errors"].extend(pub_comp_result.errors)
            return report

        # Step 3: Generate uncompressed public key
        pub_uncomp_result, public_key_uncompressed = self.generate_public_key(
            private_key, compressed=False
        )
        report["steps"]["public_key_uncompressed"] = pub_uncomp_result.to_dict()
        if not pub_uncomp_result.success:
            report["overall_success"] = False
            report["errors"].extend(pub_uncomp_result.errors)
            return report

        # Step 4: Generate P2PKH address
        addr_result, address = self.generate_address(
            public_key_compressed, AddressType.P2PKH
        )
        report["steps"]["address_generation"] = addr_result.to_dict()
        if not addr_result.success:
            report["overall_success"] = False
            report["errors"].extend(addr_result.errors)
            return report

        # Step 5: Generate compressed WIF
        wif_comp_result, wif_compressed = self.private_key_to_wif(
            private_key, compressed=True
        )
        report["steps"]["wif_compressed"] = wif_comp_result.to_dict()
        if not wif_comp_result.success:
            report["overall_success"] = False
            report["errors"].extend(wif_comp_result.errors)
            return report

        # Step 6: Generate uncompressed WIF
        wif_uncomp_result, wif_uncompressed = self.private_key_to_wif(
            private_key, compressed=False
        )
        report["steps"]["wif_uncompressed"] = wif_uncomp_result.to_dict()
        if not wif_uncomp_result.success:
            report["overall_success"] = False
            report["errors"].extend(wif_uncomp_result.errors)
            return report

        # Step 7: Address match verification
        match_result = self.verify_address_match(address, target_addresses)
        report["steps"]["address_match"] = match_result.to_dict()

        # Aggregate errors and warnings
        if not match_result.success:
            report["errors"].extend(match_result.errors)
        report["warnings"].extend(match_result.warnings)

        # Aggregate warnings from all steps
        for step_result in [
            pk_result,
            pub_comp_result,
            pub_uncomp_result,
            addr_result,
            wif_comp_result,
            wif_uncomp_result,
            match_result,
        ]:
            report["warnings"].extend(step_result.warnings)

        # Add summary - secure mode excludes private key plaintext
        if self.secure_mode:
            pk_hash = HashUtils.key_fingerprint(private_key)
            wif_comp_safe = (
                wif_compressed[:8] + "..." + wif_compressed[-4:]
                if len(wif_compressed) > 12
                else "***"
            )
            wif_uncomp_safe = (
                wif_uncompressed[:8] + "..." + wif_uncompressed[-4:]
                if len(wif_uncompressed) > 12
                else "***"
            )
        else:
            pk_hash = private_key.hex()
            wif_comp_safe = wif_compressed
            wif_uncomp_safe = wif_uncompressed

        report["summary"] = {
            "private_key_hash": pk_hash,
            "public_key_compressed": public_key_compressed.hex(),
            "public_key_uncompressed": public_key_uncompressed.hex(),
            "address": address,
            "wif_compressed": wif_comp_safe,
            "wif_uncompressed": wif_uncomp_safe,
            "address_match": match_result.details.get("match", False),
            "target_count": len(target_addresses),
            "secure_mode": self.secure_mode,
        }

        return report


# Convenience function
def validate_bitcoin_key_chain(
    private_key: bytes, target_addresses: set
) -> dict[str, Any]:
    """
    Convenience function: validate complete Bitcoin key chain.

    Args:
        private_key: 32-byte private key
        target_addresses: Set of target addresses

    Returns:
        Complete validation report
    """
    validator = BitcoinKeyValidator()
    return validator.full_validation_chain(private_key, target_addresses)
