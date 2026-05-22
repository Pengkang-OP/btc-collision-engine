"""Data cleanup module.

Automatically cleans expired temporary files, logs, and monitoring
data to prevent disk space exhaustion.
"""

import logging
import os
import shutil
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class DataCleaner:
    """Cleans expired data files to manage disk usage."""

    def __init__(
        self,
        retention_days: int = 7,
        target_dirs: list[str] | None = None,
    ):
        self._retention_seconds = (
            retention_days * 86400
        )
        self._target_dirs = target_dirs or [
            "data_logs",
            "logs",
            "temp",
        ]

    def clean_all(self) -> int:
        """Clean all expired files.

        Returns:
            Number of files cleaned
        """
        total = 0
        now = time.time()
        for dir_name in self._target_dirs:
            path = Path(dir_name)
            if not path.exists():
                continue
            for f in path.iterdir():
                if f.is_file():
                    age = now - f.stat().st_mtime
                    if age > self._retention_seconds:
                        try:
                            f.unlink()
                            total += 1
                            logger.debug(
                                f"Cleaned: {f}"
                            )
                        except OSError as e:
                            logger.warning(
                                f"Failed to clean {f}: "
                                f"{e}"
                            )
        logger.info(
            f"Data cleanup complete: "
            f"{total} files removed"
        )
        return total
