"""Optimization-specific configuration models."""

from dataclasses import dataclass, field


def is_feature_enabled(feature: str) -> bool:
    """Check if an optimization feature is enabled."""
    features = {
        "batch_optimization": True,
        "precompute_tables": True,
        "memory_pool": True,
        "work_stealing": True,
    }
    return features.get(feature, False)


@dataclass
class OptimizationConfig:
    """Configuration for performance optimization."""
    enabled: bool = True
    batch_size: int = 100000
    precompute_tables: bool = True
    memory_pool_enabled: bool = True
    thread_count: int = 4
    use_gpu: bool = False
