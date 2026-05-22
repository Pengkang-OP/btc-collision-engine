"""Optimization-specific configuration models."""

from dataclasses import dataclass, field


@dataclass
class OptimizationConfig:
    """Configuration for performance optimization."""
    enabled: bool = True
    batch_size: int = 100000
    precompute_tables: bool = True
    memory_pool_enabled: bool = True
    thread_count: int = 4
    use_gpu: bool = False
