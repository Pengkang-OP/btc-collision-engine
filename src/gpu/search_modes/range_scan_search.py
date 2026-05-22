"""Range scan search mode for GPU collision detection."""
from .base_search import BaseSearchMode


class RangeScanSearchMode(BaseSearchMode):
    """Scans a specific range of private keys."""

    def name(self) -> str:
        return "range_scan"
