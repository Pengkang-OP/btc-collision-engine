"""GPU seed generation and management utilities."""

import secrets


def generate_seed() -> bytes:
    """Generate a cryptographically secure seed for GPU kernels.

    Returns:
        32-byte random seed
    """
    return secrets.token_bytes(32)


def generate_batch_seeds(
    count: int,
) -> list[bytes]:
    """Generate multiple seeds for batch processing.

    Args:
        count: Number of seeds to generate

    Returns:
        List of 32-byte seeds
    """
    return [secrets.token_bytes(32) for _ in range(count)]
