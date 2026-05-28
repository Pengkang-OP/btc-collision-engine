"""P2PKH Bitcoin address generator.

Provides shared base class and standard implementation for address
generation.
- BaseAddressGenerator: Shared base class (private key generation,
  public key derivation, address encoding)
- P2PKHAddressGenerator: Standard implementation (crypto_backend path,
  performance check)
- OptimizedP2PKHAddressGenerator: Optimized implementation
  (precomputed tables + SIMD + memory pool, in
  optimized_address_generator.py)
"""

__all__ = [
    "BaseAddressGenerator",
    "P2PKHAddressGenerator",
    "PerformanceWarning",
    "secure_clear_bytearray",
]

import ctypes
import secrets
from abc import ABC, abstractmethod

# Import logging configuration
from ..utils import get_configured_logger
from .base58 import Base58
from .hash_utils import HashUtils
from .secp256k1 import EllipticCurve, Secp256k1

# v4.2.2 M3: Log initialization unified by CLI entry (main.py) and
# utils/__init__.py

# Get module logger
logger = get_configured_logger("AddressGenerator")


class PerformanceWarning(UserWarning):
    """Performance warning: current configuration may not be optimal."""


def secure_clear_bytearray(buffer: bytearray) -> None:
    """Securely clear bytearray memory.

    Uses ctypes to directly zero out bytearray memory, preventing
    sensitive data from lingering in memory.

    Args:
        buffer: bytearray object to clear (must be mutable bytearray)

    Note:
        - bytes objects are immutable and cannot be cleared; convert
          to bytearray first
        - Python's GC may copy objects; this method only clears the
          current reference
        - For highest security requirements, use dedicated crypto
          libraries (e.g. cryptography.io)
        - This method is suitable for bytearray objects used for
          temporary private key storage

    Usage:
        >>> # Correct: use bytearray
        >>> private_key = bytearray(secrets.token_bytes(32))
        >>> # Use private key...
        >>> secure_clear_bytearray(private_key)  # Clear

        >>> # Wrong: bytes is immutable
        >>> private_key = secrets.token_bytes(32)  # bytes type
        >>> # secure_clear_bytearray(private_key)  # Will fail!

    Raises:
        TypeError: If input is not a bytearray type

    """
    if not isinstance(buffer, bytearray):
        raise TypeError(
            f"Input must be bytearray, got {type(buffer).__name__}. "
            "bytes is immutable and cannot be cleared. "
            "Convert to bytearray first.",
        )

    try:
        # Use ctypes.memset to directly zero out bytearray memory
        ctypes.memset(
            ctypes.addressof(ctypes.c_char.from_buffer(buffer)),
            0,
            len(buffer),
        )
    except (TypeError, ValueError, OSError) as e:
        # Silently fail if buffer is already freed or inaccessible
        # Log debug info (without leaking sensitive data)
        logger.debug(
            f"Failed to clear buffer: {type(e).__name__}",
        )


class BaseAddressGenerator(ABC):
    """Shared base class for address generators.

    Defines the common address generation workflow; subclasses only
    need to implement private_key_to_public_key().
    All address generators (standard and optimized) inherit from this
    class to eliminate code duplication.

    Attributes:
        ec: Elliptic curve calculator instance

    Subclasses must implement:
        private_key_to_public_key(private_key, compressed) -> bytes

    """

    def __init__(self) -> None:
        """Initialize base class — create elliptic curve calculator."""
        self.ec = EllipticCurve()

    @abstractmethod
    def private_key_to_public_key(
        self,
        private_key: bytes,
        compressed: bool = True,
    ) -> bytes:
        """Derive public key from private key (subclass must implement).

        Args:
            private_key: 32-byte private key
            compressed: Whether to use compressed format

        Returns:
            Public key bytes

        """
        ...

    def public_key_to_hash160(
        self,
        public_key: bytes,
    ) -> bytes:
        """Compute Hash160 from public key (without full address).

        Only performs Hash160 computation, skipping Base58Check
        encoding.
        Used for fast match detection in collision engine hot path.

        Args:
            public_key: Public key bytes (compressed or uncompressed)

        Returns:
            20-byte Hash160 value

        """
        return HashUtils.hash160(public_key)

    def public_key_to_address(
        self,
        public_key: bytes,
    ) -> str:
        """Generate Bitcoin address from public key.

        Performs Hash160 and Base58Check encoding. Subclasses can
        override to use optimized paths (e.g. SIMD).

        Args:
            public_key: Public key bytes (compressed or uncompressed)

        Returns:
            Bitcoin address starting with '1'

        """
        hash160 = self.public_key_to_hash160(public_key)
        address = Base58.check_encode(0x00, hash160)
        return address

    def generate_address(
        self,
        private_key: bytes,
        compressed: bool = True,
    ) -> tuple[str, bytes, bytes]:
        """Generate complete address from private key.

        Args:
            private_key: 32-byte private key (required)
            compressed: Whether to use compressed public key format

        Returns:
            (address, public_key, private_key) tuple

        """
        public_key = self.private_key_to_public_key(
            private_key,
            compressed,
        )
        address = self.public_key_to_address(public_key)
        return address, public_key, private_key

    def generate_private_key(
        self,
        max_retries: int = 100,
    ) -> bytes:
        """Generate random private key.

        Uses cryptographically secure random number generator to
        generate a 32-byte private key.
        Ensures the key is in valid range (1 <= key < N).

        Args:
            max_retries: Maximum retry attempts, default 100

        Returns:
            32-byte private key

        Raises:
            KeyGenerationError: When unable to generate valid key
                within max_retries

        """
        from ..utils.exceptions import KeyGenerationError

        for attempt in range(max_retries):
            try:
                private_key = secrets.token_bytes(32)
                key_int = int.from_bytes(private_key, "big")

                if 1 <= key_int < Secp256k1.N:
                    logger.debug(
                        f"Private key generated successfully (attempt {attempt + 1}/{max_retries})",
                    )
                    return private_key
            except Exception as e:
                # secrets.token_bytes may raise ValueError/
                # TypeError/OverflowError due to low system entropy
                # Other exceptions (e.g. OSError) also logged
                logger.error(
                    "Error generating private key (attempt %d/%d): %s",
                    attempt + 1,
                    max_retries,
                    type(e).__name__,
                )

        logger.error(
            "Private key generation failed: exceeded max retries %s",
            max_retries,
        )
        raise KeyGenerationError(
            f"Cannot generate valid private key within {max_retries} attempts",
            error_code=1001,
            context={"max_retries": max_retries},
        )


class P2PKHAddressGenerator(BaseAddressGenerator):
    """P2PKH Bitcoin address generator (standard implementation).

    Inherits from BaseAddressGenerator, uses crypto_backend for
    public key derivation.
    Supports automatic private key generation (generate_address()
    without arguments).

    Attributes:
        ec: Elliptic curve calculator instance (inherited from base)

    Usage:
        >>> generator = P2PKHAddressGenerator()
        >>> address, compressed_pk, uncompressed_pk = \
            generator.generate_address()

    """

    def __init__(self) -> None:
        """Initialize address generator.

        Creates elliptic curve calculator instance and checks crypto
        backend performance.
        """
        super().__init__()

        # Check crypto backend and issue performance warning
        self._check_crypto_backend_performance()

    def _check_crypto_backend_performance(self):
        """Check crypto backend and issue performance warning.

        If using pure Python backend, warns and suggests installing
        coincurve.
        """
        try:
            from .crypto_backend import crypto_manager

            backend = crypto_manager.current_backend

            if backend.name == "PURE_PYTHON":
                import warnings

                warnings.warn(
                    "Currently using pure Python crypto backend, "
                    "lower performance. "
                    "Install coincurve for 3-5x speedup:\n"
                    "  pip install coincurve>=18.0.0",
                    PerformanceWarning,
                    stacklevel=2,
                )
                logger.info(
                    "Tip: Install coincurve for 3-5x performance boost (pip install coincurve>=18.0.0)",
                )
        except ImportError as e:
            # Silently fail, does not affect functionality
            logger.debug(
                "coincurve not available (will use pure Python): %s",
                e,
            )

    def generate_private_key(
        self,
        max_retries: int = 100,
    ) -> bytes:
        """Generate random private key (delegates to base)."""
        return super().generate_private_key(max_retries)

    def private_key_to_public_key(
        self,
        private_key: bytes,
        compressed: bool = True,
    ) -> bytes:
        """Generate public key from private key.

        Args:
            private_key: 32-byte private key
            compressed: Whether to use compressed format, default True

        Returns:
            Public key bytes

        """
        # Prefer crypto backend manager (supports multiple backends)
        try:
            from .crypto_backend import crypto_manager

            return crypto_manager.generate_public_key(
                private_key,
                compressed,
            )
        except (ImportError, AttributeError) as e:
            # Fall back to pure Python implementation
            logger.debug(
                f"Crypto backend unavailable, using pure Python: {type(e).__name__}",
            )
            return self.ec.generate_public_key(
                private_key,
                compressed,
            )

    def public_key_to_address(
        self,
        public_key: bytes,
    ) -> str:
        """Generate Bitcoin address from public key (delegates to base)."""
        return super().public_key_to_address(public_key)

    def generate_address(
        self,
        private_key: bytes | None = None,
        compressed: bool = True,
    ) -> tuple[str, bytes, bytes]:
        """Generate complete Bitcoin address from private key.

        P2PKHAddressGenerator always returns both compressed and
        uncompressed public keys, so the compressed parameter is
        accepted only for base class interface compatibility.

        Args:
            private_key: Optional 32-byte private key,
                None for random generation
            compressed: Base class compatibility parameter,
                does not affect P2PKHAddressGenerator behavior

        Returns:
            (address, compressed_public_key,
             uncompressed_public_key) tuple

        Raises:
            ValueError: When private key length is invalid or out of
                valid range

        """
        # Generate or validate private key
        if private_key is None:
            private_key = self.generate_private_key()
        elif len(private_key) != 32:
            raise ValueError(
                f"Private key length must be 32 bytes, got {len(private_key)} bytes",
            )
        else:
            # Validate private key in valid range [1, N)
            key_int = int.from_bytes(private_key, "big")
            if key_int == 0:
                raise ValueError(
                    "Private key cannot be zero, must be in range [1, N)",
                )
            if key_int >= Secp256k1.N:
                raise ValueError(
                    f"Private key exceeds curve order N = {Secp256k1.N}. Key must be in range [1, N)",
                )

        # Generate compressed public key
        compressed_pk = self.private_key_to_public_key(
            private_key,
            compressed=True,
        )

        # Generate uncompressed public key
        uncompressed_pk = self.private_key_to_public_key(
            private_key,
            compressed=False,
        )

        # Generate address
        address = self.public_key_to_address(compressed_pk)

        return address, compressed_pk, uncompressed_pk


# Backward compatibility alias (referenced by simd_optimizer.py, etc.)
AddressGenerator = P2PKHAddressGenerator
