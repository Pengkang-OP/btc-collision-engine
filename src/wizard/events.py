"""Wizard event definitions."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WizardEvent:
    """Base wizard event."""

    type: str = ""
    data: dict[str, Any] = field(default_factory=dict)
