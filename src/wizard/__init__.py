"""
Setup wizard package for interactive first-run configuration.

Provides the WizardEngine that guides users through GPU selection, search
mode selection, target address loading, and option configuration via
an interactive CLI wizard interface. Uses an event-driven architecture
with WizardEvent/EventDispatcher for decoupled component communication.
"""

from .events import EventDispatcher, WizardEvent, WizardEventType
from .interfaces import WizardConfig, WizardMode, WizardResult
from .selector_protocol import SelectorProtocol
from .wizard_engine import WizardEngine

from src import __version__ as __version__  # noqa: F401 — 从包根统一读取

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
