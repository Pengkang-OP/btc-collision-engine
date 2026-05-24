"""Wizard selector protocol definitions."""
from typing import Protocol


class SelectorProtocol(Protocol):
    """Protocol for wizard item selectors."""

    def get_selection(self) -> list[str]: ...
