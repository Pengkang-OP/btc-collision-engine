"""Log event type definitions."""

from dataclasses import dataclass


@dataclass
class LogEvent:
    """Base log event."""

    level: str = "INFO"
    message: str = ""
    timestamp: float = 0.0


@dataclass
class SecurityLogEvent(LogEvent):
    """Security-related log event."""

    pattern_type: str = ""
    masked: bool = False
