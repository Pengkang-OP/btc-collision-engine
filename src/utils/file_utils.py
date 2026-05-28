"""File operation utility functions.

Provides atomic write, secure read, and other file operation
functions ensuring data integrity and consistency.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


def atomic_write(
    filepath: str | Path,
    content: str,
    encoding: str = "utf-8",
) -> None:
    """Atomically write content to a file.

    Args:
        filepath: Target file path
        content: Content to write
        encoding: File encoding

    Raises:
        OSError: If write fails

    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        shutil.move(tmp_path, str(path))
    except Exception:
        if Path(tmp_path).exists():
            Path(tmp_path).unlink()
        raise


def atomic_json_write(
    filepath: str | Path,
    data: Any,
    **kwargs: Any,
) -> None:
    """Atomically write JSON data to a file.

    Args:
        filepath: Target file path
        data: Data to serialize as JSON
        **kwargs: Passed to json.dumps

    """
    atomic_write(
        filepath,
        json.dumps(data, **kwargs),
    )


def atomic_json_read(filepath: str | Path) -> Any:
    """Atomically read JSON data from a file.

    Args:
        filepath: File path

    Returns:
        Deserialized JSON data, or None if file doesn't exist

    """
    path = Path(filepath)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def ensure_directory(filepath: str | Path) -> Path:
    """Ensure directory exists for a file path.

    Args:
        filepath: File or directory path

    Returns:
        Path object for the directory

    """
    path = Path(filepath)
    if path.suffix:
        path = path.parent
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_file_size_safe(filepath: str | Path) -> int:
    """Safely get file size, returning 0 on error.

    Args:
        filepath: File path

    Returns:
        File size in bytes, or 0 on error

    """
    try:
        return Path(filepath).stat().st_size
    except (OSError, FileNotFoundError):
        return 0


def safe_file_delete(filepath: str | Path) -> bool:
    """Safely delete a file, returning success status.

    Args:
        filepath: File path to delete

    Returns:
        True if deleted or not found

    """
    try:
        Path(filepath).unlink(missing_ok=True)
        return True
    except OSError:
        return False
