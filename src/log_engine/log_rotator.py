"""Log file rotation utilities."""
import os
import shutil
from pathlib import Path


class LogRotator:
    """Rotates log files to manage disk usage."""

    def __init__(
        self,
        max_size_mb: int = 100,
        backup_count: int = 5,
    ):
        self._max_size = max_size_mb * 1024 * 1024
        self._backup_count = backup_count

    def rotate(self, filepath: str | Path) -> bool:
        """Rotate a log file if it exceeds max size.

        Args:
            filepath: Path to log file

        Returns:
            True if rotation occurred
        """
        path = Path(filepath)
        if not path.exists():
            return False
        if path.stat().st_size < self._max_size:
            return False
        for i in range(
            self._backup_count - 1, 0, -1
        ):
            src = path.with_suffix(f".log.{i}")
            dst = path.with_suffix(f".log.{i + 1}")
            if src.exists():
                shutil.move(str(src), str(dst))
        shutil.move(
            str(path),
            str(path.with_suffix(".log.1")),
        )
        return True
