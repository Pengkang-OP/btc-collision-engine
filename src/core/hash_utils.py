"""Hash utility module.

Provides Bitcoin-related hash computation functions:
- SHA-256
- RIPEMD-160
- Hash160 (SHA-256 + RIPEMD-160)
- Double SHA-256
- Key fingerprinting
"""

import hashlib


class HashUtils:
    """Hash utility class.

    Provides static methods for Bitcoin-related hash computations.
    All methods are stateless and thread-safe.
    """

    @staticmethod
    def sha256(data: bytes) -> bytes:
        """Compute SHA-256 hash.

        Args:
            data: Input data

        Returns:
            32-byte hash result
        """
        return hashlib.sha256(data).digest()

    @staticmethod
    def double_sha256(data: bytes) -> bytes:
        """Compute double SHA-256 hash.

        Used for Bitcoin address checksums and block hashing.

        Args:
            data: Input data

        Returns:
            32-byte hash result
        """
        return hashlib.sha256(
            hashlib.sha256(data).digest()
        ).digest()

    @staticmethod
    def ripemd160(data: bytes) -> bytes:
        """Compute RIPEMD-160 hash.

        Args:
            data: Input data

        Returns:
            20-byte hash result
        """
        return hashlib.new("ripemd160", data).digest()

    @staticmethod
    def hash160(data: bytes) -> bytes:
        """Compute Hash160 (SHA-256 + RIPEMD-160).

        Used for Bitcoin address generation:
        1. SHA-256(data)
        2. RIPEMD-160(result)

        Args:
            data: Input data

        Returns:
            20-byte Hash160 result

        Raises:
            TypeError: If data is not bytes type
            ValueError: If data is empty
        """
        if not isinstance(data, bytes):
            raise TypeError(
                f"Input data must be bytes type, got {type(data).__name__}"
            )
        if len(data) == 0:
            raise ValueError("Input data cannot be empty")
        return HashUtils.ripemd160(
            HashUtils.sha256(data)
        )

    @staticmethod
    def key_fingerprint(key: bytes) -> str:
        """Compute key fingerprint (first 8 hex chars of Hash160).

        Provides a short identifier for a key without exposing the
        full key.

        Args:
            key: Key bytes

        Returns:
            8-character hex fingerprint
        """
        return HashUtils.hash160(key).hex()[:8]
