"""Optimized P2PKH address generator with precomputed tables and SIMD."""

from .address_generator import (
    P2PKHAddressGenerator,
    secure_clear_bytearray,
)
from .precomputed_table import get_precomputed_table
from .simd_optimizer import BatchOptimizer


class OptimizedP2PKHAddressGenerator(P2PKHAddressGenerator):
    """
    Optimized P2PKH Bitcoin address generator.

    Uses precomputed point tables and batch processing for improved
    performance:
    - Precomputed point tables accelerate scalar multiplication
    - Batch processing reduces per-key overhead
    - Memory pool reduces allocation cost
    """

    def __init__(
        self, window_size: int = 8, batch_size: int = 1000
    ) -> None:
        """
        Initialize optimized address generator.

        Args:
            window_size: Precomputed table window size (4-8)
            batch_size: Batch processing size
        """
        super().__init__()
        self.window_size = window_size
        self.batch_size = batch_size
        self._table = get_precomputed_table(window_size)
        self._batch_optimizer = BatchOptimizer(batch_size)

    def private_key_to_public_key(
        self,
        private_key: bytes,
        compressed: bool = True,
    ) -> bytes:
        """
        Generate public key using precomputed table.

        Uses window method with precomputed point table for
        2-3x faster scalar multiplication.

        Args:
            private_key: 32-byte private key
            compressed: Whether to use compressed format

        Returns:
            Public key bytes
        """
        k = int.from_bytes(private_key, "big")
        public_point = self._table.scalar_multiply_with_table(
            k
        )

        if public_point.is_infinity:
            raise ValueError(
                "Generated public key is infinity point, "
                "invalid private key"
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
        else:
            return (
                b"\x04"
                + public_point.x.to_bytes(32, "big")
                + public_point.y.to_bytes(32, "big")
            )
