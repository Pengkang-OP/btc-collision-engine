"""Log processor for filtering and transforming log entries."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.log_engine.events import LogEvent  # pragma: no cover

logger = logging.getLogger(__name__)


class LogProcessor:
    """Processes and transforms log events."""

    def __init__(self) -> None:
        self._filters: list = []
        self._transforms: list = []

    def process(self, event: LogEvent) -> dict | None:  # noqa: F821
        """Process a log event into a dictionary.

        Args:
            event: LogEvent instance

        Returns:
            Processed event dict, or None if filtered out

        """
        result = {
            "event_type": getattr(event, "event_type", None),
            "data": getattr(event, "data", {}),
            "level": getattr(event, "level", "INFO"),
            "message": getattr(event, "message", ""),
            "timestamp": getattr(event, "timestamp", 0.0),
        }
        # Run filters
        for f in self._filters:
            if not f(result):
                return None
        # Run transforms
        for t in self._transforms:
            result = t(result)
        return result


class SensitiveDataFilter(logging.Filter):
    """Filters sensitive data from log records."""

    # Class-level compiled patterns for address/private key detection
    SENSITIVE_PATTERNS: list[re.Pattern] = [
        re.compile(r"[0-9a-fA-F]{64}"),  # private key hex
        re.compile(r"PrivateKey\s*[=:]\s*\S+", re.IGNORECASE),  # PrivateKey=...
        re.compile(r"[13][a-km-zA-HJ-NP-Z1-9]{25,34}"),  # P2PKH + P2SH
        re.compile(r"bc1[ac-hj-np-z02-9]{6,87}", re.IGNORECASE),  # Bech32
        re.compile(r"bc1p[ac-hj-np-z02-9]{6,87}", re.IGNORECASE),  # Bech32m (Taproot)
        re.compile(r"[KL5][1-9A-HJ-NP-Za-km-z]{50,51}"),  # WIF private key
    ]

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
        # PrivateKey=... pattern
        message = re.sub(
            r"PrivateKey\s*[=:]\s*\S+",
            "PrivateKey=***REDACTED***",
            message,
            flags=re.IGNORECASE,
        )
        # Bech32m (Taproot) first (more specific), then Bech32
        message = re.sub(
            r"bc1p[ac-hj-np-z02-9]{6,87}",
            "[BECH32M_ADDRESS]",
            message,
            flags=re.IGNORECASE,
        )
        message = re.sub(
            r"bc1[ac-hj-np-z02-9]{6,87}",
            "[BECH32_ADDRESS]",
            message,
            flags=re.IGNORECASE,
        )
        # P2PKH + P2SH
        message = re.sub(r"[13][a-km-zA-HJ-NP-Z1-9]{25,34}", "[P2PKH_ADDRESS]", message)
        # WIF
        message = re.sub(r"[KL5][1-9A-HJ-NP-Za-km-z]{50,51}", "[REDACTED_WIF]", message)
        return message

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and mask sensitive data in log records.

        Args:
            record: Log record

        Returns:
            False if sensitive data detected, True otherwise

        """
        # Check record.msg for sensitive patterns
        if hasattr(record, "msg") and isinstance(
            record.msg,
            str,
        ):
            for pattern, mask in self._patterns:
                record.msg = pattern.sub(
                    mask,
                    record.msg,
                )

        # Check record.data for sensitive content (LogEvent-style records)
        record_data = getattr(record, "data", {})
        if isinstance(record_data, dict):
            data_str = str(record_data)
            for pattern in SensitiveDataFilter.SENSITIVE_PATTERNS:
                if pattern.search(data_str):
                    return False

        return True
