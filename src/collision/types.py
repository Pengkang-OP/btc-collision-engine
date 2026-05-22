#!/usr/bin/env python3
"""
Type definitions and data structures for collision detection.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SearchMode(Enum):
    """Collision search mode."""
    RANDOM = "random"
    SEQUENTIAL = "sequential"
    HYBRID = "hybrid"


class AddressFormat(Enum):
    """Bitcoin address format."""
    P2PKH = "p2pkh"
    P2SH = "p2sh"
    BECH32 = "bech32"
    UNKNOWN = "unknown"


@dataclass
class MatchResult:
    """Collision match result."""
    private_key: bytes
    address: str
    wif: str
    worker_id: int = 0
    device_idx: int = 0


from typing import Callable, Optional

# Callback type aliases
MatchCallback = Callable[..., None]
ProgressCallback = Callable[..., None]
CompleteCallback = Callable[..., None]


@dataclass
class EngineStats:
    """Collision engine statistics."""
    total_keys_checked: int = 0
    total_matches: int = 0
    elapsed_seconds: float = 0.0
    throughput: float = 0.0
    worker_count: int = 0
    device_count: int = 0
