"""Wizard interface definitions."""

from abc import ABC, abstractmethod
from typing import Any


class WizardStep(ABC):
    """Abstract wizard step."""

    @abstractmethod
    def render(self) -> str:
        """Render step UI."""

    @abstractmethod
    def handle_input(self, data: Any) -> bool:
        """Handle user input.

        Returns:
            True if step should advance

        """


class WizardPage(ABC):  # noqa: B024
    """Abstract wizard page."""
