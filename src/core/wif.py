"""WIF (Wallet Import Format) encode/decode utility"""

from .base58 import Base58
from .hash_utils import HashUtils


class WIF:
    """WIF (Wallet Import Format) encode/decode.

    Implements Bitcoin private key WIF format encoding and decoding.
    Supports mainnet and testnet, compressed and uncompressed formats.

    Format:
    - Mainnet compressed: 'K'/'L' prefix, 52 chars
    - Mainnet uncompressed: '5' prefix, 51 chars
    - Testnet compressed: 'c' prefix, 52 chars
    - Testnet uncompressed: '9' prefix, 51 chars

    Structure:
    [version(1)] [private_key(32)] [compressed_flag(1)] [checksum(4)]

    Reference: https://en.bitcoin.it/wiki/Wallet_import_format
    """

    MAINNET_VERSION = 0x80
    TESTNET_VERSION = 0xEF
    COMPRESSED_FLAG = 0x01

    @staticmethod
    def encode(
        private_key: bytes,
        compressed: bool = True,
        testnet: bool = False,
    ) -> str:
        """Encode private key to WIF format.

        Args:
            private_key: 32-byte private key
            compressed: Whether to use compressed format,
                default True
            testnet: Whether to use testnet version byte,
                default False

        Returns:
            WIF encoded string

        Raises:
            ValueError: When private key length is invalid

        """
        if not isinstance(private_key, bytes):
            raise ValueError(
                f"Private key must be bytes, "
                f"got {type(private_key).__name__}",
            )

        if len(private_key) != 32:
            raise ValueError(
                f"Private key must be 32 bytes, "
                f"got {len(private_key)}",
            )

        # Build payload
        version_byte = (
            WIF.TESTNET_VERSION
            if testnet
            else WIF.MAINNET_VERSION
        )
        payload = bytes([version_byte]) + private_key

        if compressed:
            payload += bytes([WIF.COMPRESSED_FLAG])

        # Compute checksum
        checksum = HashUtils.double_sha256(payload)[:4]

        return Base58.encode(payload + checksum)

    @staticmethod
    def decode(wif: str) -> tuple[bytes, bool]:
        """Decode WIF string to private key.

        Args:
            wif: WIF encoded string

        Returns:
            (private_key, is_compressed) tuple

        Raises:
            ValueError: When WIF format is invalid or checksum
                verification fails

        """
        if not isinstance(wif, str):
            raise ValueError(
                f"WIF must be a string, "
                f"got {type(wif).__name__}",
            )

        data = Base58.decode(wif)

        # Minimum length: 1 (version) + 32 (key) + 4 (checksum)
        # = 37, or 38 with compressed flag
        if len(data) < 37:
            raise ValueError(
                f"WIF data too short: "
                f"{len(data)} bytes",
            )

        # Validate version byte
        version = data[0]
        if version not in (WIF.MAINNET_VERSION, WIF.TESTNET_VERSION):
            raise ValueError(
                f"Invalid WIF version byte: 0x{version:02X}, "
                f"expected 0x{WIF.MAINNET_VERSION:02X} or "
                f"0x{WIF.TESTNET_VERSION:02X}",
            )

        # Extract and verify checksum
        payload = data[:-4]
        checksum = data[-4:]
        expected = HashUtils.double_sha256(payload)[:4]

        if checksum != expected:
            raise ValueError(
                "WIF checksum verification failed",
            )

        # Extract key data
        key_data = payload[1:]

        # Determine compression based on payload length
        if len(key_data) == 33 and key_data[-1] == 0x01:
            return key_data[:-1], True  # Compressed
        if len(key_data) == 32:
            return key_data, False  # Uncompressed
        raise ValueError(
            f"Invalid WIF payload length: "
            f"{len(key_data)}",
        )
