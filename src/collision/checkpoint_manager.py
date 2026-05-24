#!/usr/bin/env python3
"""Checkpoint manager for saving and restoring collision engine state.

Provides crash recovery by periodically saving progress to JSON
files with CRC32 integrity verification and atomic writes.
"""

import json
import threading
import time
import zlib
from pathlib import Path

from ..utils import get_configured_logger
from ..utils.fast_json import fast_dumps, fast_loads

logger = get_configured_logger("CheckpointManager")

CHECKPOINT_VERSION = 2
MAX_CHECKPOINT_SIZE = 10 * 1024 * 1024  # 10MB


class CheckpointError(Exception):
    """Checkpoint operation error."""


class CRC32MismatchError(CheckpointError):
    """CRC32 checksum mismatch on checkpoint load."""


class CheckpointManager:
    """Manages checkpoint save/load for collision engine state."""

    def __init__(
        self,
        filepath: str | Path | None = None,
        interval: int = 60,
        max_size: int = MAX_CHECKPOINT_SIZE,
        auto_save_interval: int | None = None,
    ):
        self.filepath = Path(filepath) if filepath else Path("checkpoint.json")
        # Support auto_save_interval as alias for interval
        self._interval = auto_save_interval if auto_save_interval is not None else interval
        self._max_size = max_size
        self._lock = threading.Lock()
        self._buffer: dict | None = None
        self._dirty = False
        self._last_save = 0.0

    @property
    def exists(self) -> bool:
        """Check if checkpoint file exists."""
        return self.filepath.exists()

    @property
    def should_auto_save(self) -> bool:
        """Alias for should_save()."""
        return self.should_save()

    def should_save(self) -> bool:
        return self._dirty and time.time() - self._last_save >= self._interval

    def save(
        self,
        state: dict,
    ) -> None:
        """Save checkpoint with state data.

        Args:
            state: Engine state dictionary

        """
        with self._lock:
            self._buffer = state
            self._dirty = True
            self._flush_buffer()

    def load(self) -> dict | None:
        """Load checkpoint from file.

        Returns:
            State dictionary or None if no checkpoint

        """
        if not self.filepath.exists():
            return None
        try:
            raw = self.filepath.read_bytes()
            if len(raw) > self._max_size:
                raise CheckpointError(
                    f"Checkpoint too large: {len(raw)} bytes",
                )
            data = fast_loads(raw.decode("utf-8"))
            if data.get("version") != CHECKPOINT_VERSION:
                logger.warning(
                    "Checkpoint version mismatch",
                )
            stored_crc = data.pop("crc32", None)
            if stored_crc is not None:
                # Compute CRC on data without crc32 field, single serialization
                serialized = fast_dumps(data, sort_keys=True)
                computed = zlib.crc32(serialized.encode())
                if computed != stored_crc:
                    raise CRC32MismatchError(
                        "CRC32 checksum mismatch",
                    )
            return data
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
            CheckpointError,
        ) as e:
            logger.error(
                "Failed to load checkpoint: %s",
                e,
            )
            return None

    def delete(self) -> None:
        """Delete checkpoint file."""
        with self._lock:
            if self.filepath.exists():
                self.filepath.unlink()
            self._buffer = None
            self._dirty = False

    def _flush_buffer(self) -> None:
        """Write buffered state to file atomically."""
        if self._buffer is None:
            return
        data = dict(self._buffer)
        data["version"] = CHECKPOINT_VERSION
        data["timestamp"] = time.time()
        # Compute CRC on data without crc32 field, then add it and re-serialize
        serialized = fast_dumps(data, sort_keys=True)
        crc = zlib.crc32(serialized.encode())
        data["crc32"] = crc
        serialized = fast_dumps(data, sort_keys=True)
        temp_path = self.filepath.with_suffix(".json.tmp")
        temp_path.write_text(serialized, encoding="utf-8")
        temp_path.replace(self.filepath)
        self._last_save = time.time()
        self._dirty = False
