"""Setup wizard package."""

from .wizard_engine import WizardEngine
from .events import EventDispatcher, WizardEvent, WizardEventType
from .interfaces import WizardConfig, WizardMode, WizardResult
from .selector_protocol import SelectorProtocol

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
