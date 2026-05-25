#!/usr/bin/env python3
"""Checkpoint manager for saving and restoring collision engine state.

Provides crash recovery by periodically saving progress to JSON
files with CRC32 integrity verification and atomic writes.
"""

import json
import threading
import time
import zlib
from contextlib import suppress
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
        """Check if auto-save should trigger.

        When interval is 0, always returns True (immediate auto-save).
        Otherwise requires dirty state and elapsed interval.
        """
        if self._interval == 0:
            return True
        return self._dirty and time.time() - self._last_save >= self._interval

    def save(
        self,
        state: dict | None = None,
        **kwargs,
    ) -> None:
        """Save checkpoint with state data.

        Args:
            state: Engine state dictionary
            **kwargs: Legacy keyword arguments (mode, targets, current_position,
                      total_checked, matches, force, etc.) — converted to dict
                      when state is not provided.

        """
        if state is None and kwargs:
            # Support legacy test calls that pass keyword arguments
            state = {}
            for k, v in kwargs.items():
                if k == "force":
                    continue
                # Convert set to list for JSON serialization
                if isinstance(v, set):
                    state[k] = list(v)
                else:
                    state[k] = v
        if state is None:
            state = {}
        with self._lock:
            self._buffer = state
            self._dirty = True
            if kwargs.get("force", False) or self._dirty and self._last_save == 0.0:
                self._flush_buffer()

    def load(self) -> dict | None:
        """Load checkpoint from file.

        Returns:
            State dictionary or None if no checkpoint

        """
        if not self.filepath.exists():
            # Attempt recovery from .tmp file
            temp_file = self.filepath.with_suffix(".json.tmp")
            if temp_file.exists():
                try:
                    temp_file.replace(self.filepath)
                    logger.info("Recovered checkpoint from .tmp file")
                except (OSError, Exception):
                    logger.warning("Failed to recover from .tmp file")
                    return None
            else:
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
                    "Checkpoint version mismatch: expected %s, got %s",
                    CHECKPOINT_VERSION,
                    data.get("version"),
                )
                return None
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
                with suppress(OSError, Exception):
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
        data["security_note"] = (
            "This checkpoint file may contain sensitive information. "
            "Do not share or commit to version control."
        )
        # Sanitize matches: strip sensitive fields
        if "matches" in data and isinstance(data["matches"], list):
            for match in data["matches"]:
                if isinstance(match, dict):
                    match.pop("private_key_hex", None)
                    match.pop("private_key_wif", None)
        # Compute CRC on data without crc32 field, then add it and re-serialize
        serialized = fast_dumps(data, sort_keys=True)
        crc = zlib.crc32(serialized.encode())
        data["crc32"] = crc
        serialized = fast_dumps(data, sort_keys=True)
        temp_path = self.filepath.with_suffix(".json.tmp")
        # Ensure parent directory exists
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(serialized, encoding="utf-8")
        temp_path.replace(self.filepath)
        self._last_save = time.time()
        self._dirty = False

    def _cleanup_temp_file(self, path: str) -> None:
        """Clean up a temporary file, silencing errors.

        Args:
            path: Path to the temporary file to remove.

        """
        try:
            p = Path(path)
            if p.exists():
                p.unlink()
        except OSError:
            pass

    @staticmethod
    def _check_win32_security() -> bool:
        """Check if win32 security (pywin32) is available.

        Returns:
            True if pywin32 is available and can set ACLs.

        """
        if CheckpointManager._has_win32_security is not None:
            return CheckpointManager._has_win32_security
        try:
            import win32security  # noqa: F401

            CheckpointManager._has_win32_security = True
        except ImportError:
            CheckpointManager._has_win32_security = False
        return CheckpointManager._has_win32_security

    _has_win32_security: bool | None = None
