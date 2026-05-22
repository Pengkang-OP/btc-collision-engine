#!/usr/bin/env python3
"""
Event types and event bus integration for collision detection.
"""

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
    stats: dict | None = None
    reason: str = ""


@dataclass
class EngineCompleteEvent(EngineEvent):
    """Event emitted when engine completes."""
    stats: dict | None = None
    duration: float = 0.0


@dataclass
class EngineMatchEvent(EngineEvent):
    """Event emitted when a match is found."""
    private_key: bytes = b""
    address: str = ""
    wif: str = ""
    target_address: str = ""
    device_idx: int = 0
    worker_id: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineErrorEvent(EngineEvent):
    """Event emitted when an engine error occurs."""
    error_type: str = ""
    error_message: str = ""
    exception: Exception | None = None
    context: dict[str, Any] = field(default_factory=dict)
    recoverable: bool = False


@dataclass
class EngineProgressEvent(EngineEvent):
    """Event emitted for progress updates."""
    keys_checked: int = 0
    elapsed_seconds: float = 0.0
    throughput: float = 0.0
    matches_found: int = 0


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
