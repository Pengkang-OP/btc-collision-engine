"""Log processor for filtering and transforming log entries."""
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class SensitiveDataFilter(logging.Filter):
    """Filters sensitive data from log records."""

    def __init__(self, patterns: list[tuple[re.Pattern, str]] | None = None):
        super().__init__()
        self._patterns = patterns or []

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and mask sensitive data in log records.

        Args:
            record: Log record

        Returns:
            True (always includes record, but may modify it)
        """
        if hasattr(record, "msg") and isinstance(
            record.msg, str
        ):
            for pattern, mask in self._patterns:
                record.msg = pattern.sub(
                    mask, record.msg
                )
        return True
