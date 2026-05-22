"""File operation utility functions.

Provides atomic write, secure read, and other file operation
functions ensuring data integrity and consistency.
"""

import os
import shutil
import tempfile
from pathlib import Path


def atomic_write(
    filepath: str | Path,
    content: str,
    encoding: str = "utf-8",
) -> None:
    """Atomically write content to a file.

    Writes to a temporary file first, then renames to the target
    path to prevent partial writes.

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
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def safe_read(
    filepath: str | Path,
    encoding: str = "utf-8",
) -> str | None:
    """Safely read file content.

    Args:
        filepath: File path
        encoding: File encoding

    Returns:
        File content or None if file doesn't exist
    """
    path = Path(filepath)
    if not path.exists():
        return None
    return path.read_text(encoding=encoding)
