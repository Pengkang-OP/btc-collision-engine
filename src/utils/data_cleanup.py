"""Data cleanup module.

Automatically cleans expired temporary files, logs, and monitoring
data to prevent disk space exhaustion.
"""

import time
from pathlib import Path

from .logging_config import get_configured_logger

logger = get_configured_logger(__name__)

# 项目根目录 (src/utils/../../ = 项目根)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class DataCleaner:
    """Cleans expired data files to manage disk usage."""

    def __init__(
        self,
        retention_days: int = 7,
        target_dirs: list[str] | None = None,
    ):
        """Initialize data cleanup."""
        self._retention_seconds = retention_days * 86400
        if target_dirs is None:
            # 默认目录解析为项目根下的绝对路径，确保 CWD 无关
            self._target_dirs: list[Path] = [_PROJECT_ROOT / d for d in ("data_logs", "logs", "temp")]
        else:
            # 调用者提供的路径按原样使用（保持相对/绝对语义）
            self._target_dirs = [Path(d) for d in target_dirs]

    def clean_all(self) -> int:
        """Clean all expired files.

        Returns:
            Number of files cleaned

        """
        total = 0
        now = time.time()
        for path in self._target_dirs:
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
                                "Cleaned: %s",
                                f,
                            )
                        except OSError as e:
                            logger.warning(
                                "Failed to clean %s: %s",
                                f,
                                e,
                            )
        logger.info(
            "Data cleanup complete: %s files removed",
            total,
        )
        return total
