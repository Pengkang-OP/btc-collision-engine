"""搜索模式包.

将 GPUCollisionEngine 中的三种搜索模式提取为独立模块，
降低 gpu_collision_engine.py 的复杂度，提高可维护性。
"""

from .base_search import BaseSearchMode
from .brute_force_search import BruteForceSearchMode
from .random_search import RandomSearchMode
from .range_scan_search import RangeScanSearchMode

__all__ = [
    "BaseSearchMode",
    "BruteForceSearchMode",
    "RandomSearchMode",
    "RangeScanSearchMode",
]
