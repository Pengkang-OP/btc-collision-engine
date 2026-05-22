"""Collision detection engine package.

Provides private key collision detection against target Bitcoin
address sets using CPU and GPU acceleration.
"""

from .base_engine import BaseCollisionEngine
from .collision_stats import CollisionStats
from .checkpoint_manager import CheckpointManager

__all__ = [
    "BaseCollisionEngine",
    "CollisionStats",
    "CheckpointManager",
]
