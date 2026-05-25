#!/usr/bin/env python3
"""Event types and event bus integration for collision detection."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(Enum):
    """Event types for the collision engine."""

    ENGINE_START = "engine_start"
    ENGINE_STOP = "engine_stop"
    ENGINE_COMPLETE = "engine_complete"
    ENGINE_MATCH = "engine_match"
    ENGINE_ERROR = "engine_error"
    ENGINE_PROGRESS = "engine_progress"
    ENGINE_STATE = "engine_state"


class EngineEvent:
    """Base class for engine events."""

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary representation."""
        from dataclasses import asdict

        # All concrete subclasses are @dataclass; EngineEvent is just a base
        return asdict(self)  # type: ignore[call-overload]


@dataclass
class EngineStartEvent(EngineEvent):
    """Event emitted when engine starts."""

    config: dict | None = None
    mode: str = ""
    target_count: int = 0
    batch_size: int = 0


@dataclass
class EngineStopEvent(EngineEvent):
    """Event emitted when engine stops."""

    reason: str = ""
    stats: dict | None = None
    total_checked: int = 0


@dataclass
class EngineCompleteEvent(EngineEvent):
    """Event emitted when engine completes."""

    total_checked: int = 0
    matches_found: int = 0
    elapsed_time: float = 0.0
    avg_speed: float = 0.0
    stop_reason: str = ""
    stats: dict | None = None
    duration: float = 0.0


@dataclass
class EngineMatchEvent(EngineEvent):
    """Event emitted when a match is found.

    Security: WIF is automatically masked in __post_init__ to prevent
    accidental exposure in logs. The raw WIF is stored in _raw_wif.
    """

    private_key: bytes = b""
    address: str = ""
    wif: str = ""
    target_address: str = ""
    device_idx: int = 0
    worker_id: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Mask WIF for security – prevent accidental secrets in logs."""
        if self.wif and len(self.wif) > 10:
            self._raw_wif: str = self.wif
            self.wif = f"{self.wif[:6]}...{self.wif[-4:]}"

    @property
    def metadata(self) -> dict[str, Any]:
        """Return non-sensitive metadata suitable for logging."""
        return {
            "address": self.address,
            "target_address": self.target_address,
            "device_idx": self.device_idx,
            "worker_id": self.worker_id,
        }

    @property
    def event_type(self) -> EventType:
        """Get the EventType for this event."""
        return EventType.ENGINE_MATCH


@dataclass
class EngineErrorEvent(EngineEvent):
    """Event emitted when an engine error occurs."""

    error_type: str = ""
    error_message: str = ""
    exception: Exception | None = None
    context: dict[str, Any] = field(default_factory=dict)
    recoverable: bool = False

    @property
    def event_type(self) -> EventType:
        """Get the EventType for this event."""
        return EventType.ENGINE_ERROR


@dataclass
class EngineProgressEvent(EngineEvent):
    """Event emitted for progress updates."""

    total_checked: int = 0
    speed: float = 0.0
    avg_speed: float = 0.0  # average speed
    matches_found: int = 0
    elapsed_time: float = 0.0
    cpu_usage: float = 0.0  # CPU usage percentage
    memory_usage: float = 0.0  # memory usage percentage
    keys_checked: int = 0  # alias for backward compat
    elapsed_seconds: float = 0.0  # alias for backward compat
    throughput: float = 0.0  # alias for backward compat
    timestamp: float = field(default_factory=time.time)  # event timestamp

    @property
    def event_type(self) -> EventType:
        """Get the EventType for this event."""
        return EventType.ENGINE_PROGRESS


@dataclass
class EngineStateEvent(EngineEvent):
    """Event emitted on engine state changes."""

    state: str = ""
    message: str = ""


@dataclass
class CollisionEvent(EngineEvent):
    """Event emitted when a collision is found."""

    private_key: bytes = b""
    address: str = ""
    wif: str = ""
    target_address: str = ""
    event_type: str | None = None
