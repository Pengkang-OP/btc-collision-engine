#!/usr/bin/env python3
"""GPU-accelerated private key batch generator."""

import secrets

from ...utils import get_configured_logger

logger = get_configured_logger("GPUKeyGenerator")


class GPUKeyGenerator:
    """Generates private keys in batches for GPU processing."""

    def __init__(self, config: dict):
        self._batch_size = config.get(
            "gpu_batch_size", 100000
        )
        logger.info(
            f"GPU key generator initialized: "
            f"batch_size={self._batch_size}"
        )

    def generate_batch(
        self, count: int | None = None
    ) -> list[bytes]:
        """Generate a batch of private keys.

        Args:
            count: Number of keys to generate,
                defaults to batch_size

        Returns:
            List of 32-byte private keys
        """
        n = count or self._batch_size
        return [secrets.token_bytes(32) for _ in range(n)]

    def generate_single(self) -> bytes:
        """Generate a single private key.

        Returns:
            32-byte private key
        """
        return secrets.token_bytes(32)
