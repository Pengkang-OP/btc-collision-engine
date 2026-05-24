"""Log processor for filtering and transforming log entries."""
import logging
import re

logger = logging.getLogger(__name__)


class SensitiveDataFilter(logging.Filter):
    """Filters sensitive data from log records."""

    def __init__(self, patterns: list[tuple[re.Pattern, str]] | None = None):
        super().__init__()
        self._patterns = patterns or []

    @staticmethod
    def redact(message: str) -> str:
        """Redact sensitive data from a message string.

        Args:
            message: Message to redact

        Returns:
            Redacted message

        """
        # Simple pattern-based redaction for common patterns
        message = re.sub(r"[13][a-km-zA-HJ-NP-Z1-9]{25,34}", "[REDACTED_ADDRESS]", message)
        message = re.sub(r"[KL][1-9A-HJ-NP-Za-km-z]{51}", "[REDACTED_WIF]", message)
        return message

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and mask sensitive data in log records.

        Args:
            record: Log record

        Returns:
            True (always includes record, but may modify it)

        """
        if hasattr(record, "msg") and isinstance(
            record.msg, str,
        ):
            for pattern, mask in self._patterns:
                record.msg = pattern.sub(
                    mask, record.msg,
                )
        return True
