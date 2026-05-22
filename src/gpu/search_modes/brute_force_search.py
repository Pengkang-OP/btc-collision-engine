"""Brute force sequential search mode."""
from .base_search import BaseSearchMode


class BruteForceSearchMode(BaseSearchMode):
    """Sequential brute force search starting from a base key."""

    def name(self) -> str:
        return "brute_force"
