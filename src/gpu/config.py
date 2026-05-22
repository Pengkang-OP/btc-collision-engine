"""GPU configuration models and validation."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GPUConfig:
    """GPU configuration container."""
    enabled: bool = False
    device_ids: list[int] = field(default_factory=list)
    platform: str = ""
    batch_size: int = 100000
    timeout: int = 300
    max_devices: int = 4


def validate_config(config: dict) -> list[str]:
    """Validate GPU configuration.

    Args:
        config: Configuration dictionary

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    if config.get("gpu_enabled", False):
        batch = config.get("gpu_batch_size", 100000)
        if not (1 <= batch <= 10_000_000):
            errors.append(
                f"GPU batch size must be 1-10M, got {batch}"
            )
    return errors
