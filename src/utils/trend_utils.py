"""Trend analysis utilities for performance metrics."""


def calculate_trend(
    values: list[float],
) -> float:
    """Calculate linear trend slope from a series of values.

    A positive result indicates upward trend, negative for downward.

    Args:
        values: List of numerical values

    Returns:
        Slope of the linear regression
    """
    n = len(values)
    if n < 2:
        return 0.0
    x_avg = (n - 1) / 2.0
    y_avg = sum(values) / n
    num = sum((i - x_avg) * (v - y_avg) for i, v in enumerate(values))
    den = sum((i - x_avg) ** 2 for i in range(n))
    return num / den if den != 0 else 0.0


def is_trending_up(
    values: list[float],
    threshold: float = 0.0,
) -> bool:
    """Check if values show upward trend.

    Args:
        values: List of numerical values
        threshold: Minimum slope to consider significant

    Returns:
        True if slope exceeds threshold
    """
    return calculate_trend(values) > threshold
