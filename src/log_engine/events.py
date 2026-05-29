"""Log event type definitions."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class LogEventType(Enum):
    """Log event type enumeration."""

    STATUS_UPDATE = auto()
    ERROR = auto()
    WARNING = auto()
    INFO = auto()
    DEBUG = auto()
    SECURITY = auto()


@dataclass
class LogEvent:
    """Base log event.

    Accepts event_type as first positional arg and data as second
    (for backward compatibility with tests).
    """

    event_type: "LogEventType | None" = None
    data: dict[str, Any] = field(default_factory=dict[str, Any])
    level: str = "INFO"
    message: str = ""
    timestamp: float = 0.0


@dataclass
class SecurityLogEvent(LogEvent):
    """Security-related log event."""

    pattern_type: str = ""
    masked: bool = False
