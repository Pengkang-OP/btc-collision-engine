"""Optimized P2PKH address generator with precomputed tables and SIMD."""

from .address_generator import (
    P2PKHAddressGenerator,
)
from .hash_utils import HashUtils
from .precomputed_table import get_precomputed_table
from .simd_optimizer import BatchOptimizer


class OptimizedP2PKHAddressGenerator(P2PKHAddressGenerator):
    """Optimized P2PKH Bitcoin address generator.

    Uses precomputed point tables and batch processing for improved
    performance:
    - Precomputed point tables accelerate scalar multiplication
    - Batch processing reduces per-key overhead
    - Memory pool reduces allocation cost
    """

    def __init__(
        self,
        use_precomputed_table: bool = True,
        use_simd_hash: bool = True,
        use_memory_pool: bool = True,
        window_size: int = 8,
        batch_size: int = 1000,
    ) -> None:
        """Initialize optimized address generator.

        Args:
            use_precomputed_table: Whether to use precomputed table
            use_simd_hash: Whether to use SIMD-accelerated hash
            use_memory_pool: Whether to use memory pool
            window_size: Precomputed table window size (4-8)
            batch_size: Batch processing size

        """
        super().__init__()
        self.use_precomputed_table = use_precomputed_table
        self.use_simd_hash = use_simd_hash
        self.use_memory_pool = use_memory_pool
        self.window_size = window_size
        self.batch_size = batch_size

        # Initialize precomputed table if enabled
        self._table = None
        if use_precomputed_table:
            self._table = get_precomputed_table(window_size)

        # Initialize batch optimizer if any optimization is enabled
        self._batch_optimizer = (
            BatchOptimizer(batch_size) if (use_simd_hash or use_memory_pool) else None
        )

    def private_key_to_public_key(
        self,
        private_key: bytes,
        compressed: bool = True,
    ) -> bytes:
        """Generate public key using precomputed table or crypto backend.

        Prefers native crypto backend (coincurve/OpenSSL) over precomputed
        table when available — native backends are 100-1000x faster than
        Python-based point arithmetic.

        Args:
            private_key: 32-byte private key
            compressed: Whether to use compressed format

        Returns:
            Public key bytes

        """
        # Always prefer native crypto backend (coincurve/OpenSSL) over
        # precomputed table — native libraries are orders of magnitude faster
        try:
            from .crypto_backend import BackendType, crypto_manager

            backend = crypto_manager.current_backend
            backend_type = crypto_manager._default_backend_type
            if backend is not None and backend_type != BackendType.PURE_PYTHON:
                return crypto_manager.generate_public_key(
                    private_key, compressed,
                )
        except (ImportError, AttributeError):
            pass  # Fall through to precomputed table or super

        # Fall back to precomputed table (optimization for pure Python backend)
        if self.use_precomputed_table and self._table is not None:
            k = int.from_bytes(private_key, "big")
            public_point = self._table.scalar_multiply_with_table(k)

            if public_point.is_infinity:
                raise ValueError(
                    "Generated public key is infinity point, "
                    "invalid private key",
                )

            if compressed:
                prefix = (
                    b"\x02"
                    if int(public_point.y) % 2 == 0
                    else b"\x03"
                )
                return (
                    prefix + public_point.x.to_bytes(32, "big")
                )
            return (
                b"\x04"
                + public_point.x.to_bytes(32, "big")
                + public_point.y.to_bytes(32, "big")
            )

        # Final fallback: parent implementation (crypto_backend or pure Python EC)
        return super().private_key_to_public_key(private_key, compressed)

    def public_key_to_address(
        self, public_key: bytes,
    ) -> str:
        """Generate Bitcoin address from public key.

        Uses SIMD-accelerated hash if enabled, otherwise falls back
        to parent implementation.

        Args:
            public_key: Public key bytes (compressed or uncompressed)

        Returns:
            Bitcoin address starting with '1'

        """
        if not self.use_simd_hash:
            return super().public_key_to_address(public_key)

        # Use optimized hash path (SIMD or batch optimizer)
        hash160 = self.public_key_to_hash160(public_key)
        from .base58 import Base58
        address = Base58.check_encode(0x00, hash160)
        return address

    def public_key_to_hash160(
        self, public_key: bytes,
    ) -> bytes:
        """Compute Hash160 from public key.

        Uses SIMD-accelerated batch optimizer if available.

        Args:
            public_key: Public key bytes

        Returns:
            20-byte Hash160 value

        """
        if (
            self.use_simd_hash
            and self._batch_optimizer is not None
            and hasattr(self._batch_optimizer, "batch_hash160")
        ):
            return self._batch_optimizer.batch_hash160([public_key])[0]

        # Fall back to standard HashUtils
        return HashUtils.hash160(public_key)

    def batch_generate(
        self, private_keys: list[bytes],
    ) -> list[str]:
        """Batch generate addresses from private keys.

        Args:
            private_keys: List of 32-byte private keys

        Returns:
            List of Bitcoin addresses

        """
        if not private_keys:
            return []

        return [
            self.generate_address(pk)[0]
            for pk in private_keys
        ]

    def get_optimization_info(self) -> dict:
        """Get optimization configuration information.

        Returns:
            Dictionary with optimization status and details

        """
        info = {
            "precomputed_table": {
                "enabled": self.use_precomputed_table,
                "window_size": self.window_size if self.use_precomputed_table else None,
            },
            "simd_hash": {
                "enabled": self.use_simd_hash,
            },
            "memory_pool": {
                "enabled": self.use_memory_pool,
                "batch_size": self.batch_size if self.use_memory_pool else None,
            },
        }
        return info

    def generate_from_private_key(self, private_key: bytes) -> str:
        """Generate address from private key (convenience method).

        Args:
            private_key: 32-byte private key

        Returns:
            Bitcoin address string

        """
        address, _, _ = self.generate_address(private_key)
        return address
