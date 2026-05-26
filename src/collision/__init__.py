"""Collision detection engine package.

Provides private key collision detection against target Bitcoin
address sets using CPU and GPU acceleration.
"""

from src import __version__ as __version__  # noqa: F401

from .base_engine import BaseCollisionEngine
from .checkpoint_manager import CheckpointManager
from .collision_stats import CollisionStats
from .targets.resolver import TargetResolver

__all__ = [
    "BaseCollisionEngine",
    "CheckpointManager",
    "CollisionStats",
    "TargetResolver",
]
