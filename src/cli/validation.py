"""CLI input validation utilities."""


def validate_batch_size(value: str) -> int:
    """Validate and convert batch size argument.

    Args:
        value: Batch size string

    Returns:
        Validated batch size integer

    Raises:
        ValueError: If value is invalid
    """
    n = int(value)
    if not (1 <= n <= 10_000_000):
        raise ValueError(
            f"Batch size must be between 1 and 10,000,000, "
            f"got {n}"
        )
    return n


def validate_worker_count(value: str) -> int:
    """Validate and convert worker count argument.

    Args:
        value: Worker count string

    Returns:
        Validated worker count

    Raises:
        ValueError: If value is invalid
    """
    n = int(value)
    if not (1 <= n <= 1024):
        raise ValueError(
            f"Worker count must be between 1 and 1024, "
            f"got {n}"
        )
    return n
