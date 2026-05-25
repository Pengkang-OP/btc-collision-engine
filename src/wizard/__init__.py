"""Setup wizard package."""

from .events import EventDispatcher, WizardEvent, WizardEventType
from .interfaces import WizardConfig, WizardMode, WizardResult
from .selector_protocol import SelectorProtocol
from .wizard_engine import WizardEngine

__version__ = "5.0.0"
__all__ = [
    "WizardEngine",
    "WizardResult",
    "WizardConfig",
    "WizardMode",
    "WizardEvent",
    "EventDispatcher",
    "WizardEventType",
    "SelectorProtocol",
]
