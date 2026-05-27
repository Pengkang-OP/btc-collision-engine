"""Log processor for filtering and transforming log entries."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from ..utils import get_configured_logger

if TYPE_CHECKING:
    from src.log_engine.events import LogEvent  # pragma: no cover

logger = get_configured_logger(__name__)


class LogProcessor:
    """Processes and transforms log events."""

    def __init__(self) -> None:
        """Initialize the log processor."""
        self._filters: list[Any] = []
        self._transforms: list[Any] = []

    def process(self, event: LogEvent) -> dict[str, Any] | None:
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
    # 注意：纯 64 字符 hex 可能是 txid 或哈希值，仅在特定上下文标记附近匹配
    SENSITIVE_PATTERNS: list[re.Pattern[str]] = [
        re.compile(
            r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])",
            re.IGNORECASE,
        ),  # 裸 64-char hex（私钥/哈希）
        re.compile(r"PrivateKey\s*[=:]\s*\S+", re.IGNORECASE),  # PrivateKey=...
        re.compile(
            r"(?:private_key|privkey|secret)\s*[=:]\s*[0-9a-fA-F]{64}",
            re.IGNORECASE,
        ),  # 带标记的私钥 hex
        re.compile(r"[x-z]prv[a-zA-Z0-9]{107,111}", re.IGNORECASE),  # BIP32 extended private keys
        re.compile(r"[13][a-km-zA-HJ-NP-Z1-9]{25,34}"),  # P2PKH + P2SH
        re.compile(r"bc1[ac-hj-np-z02-9]{6,87}", re.IGNORECASE),  # Bech32
        re.compile(r"bc1p[ac-hj-np-z02-9]{6,87}", re.IGNORECASE),  # Bech32m (Taproot)
        re.compile(r"[KL5][1-9A-HJ-NP-Za-km-z]{50,51}"),  # WIF private key
    ]

    def __init__(self, patterns: list[tuple[re.Pattern[str], str]] | None = None):
        """Initialize the log redactor."""
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
        # Bare 64-hex private key (highest priority: catch raw hex keys)
        message = re.sub(
            r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])",
            "***REDACTED***",
            message,
            flags=re.IGNORECASE,
        )
        # PrivateKey=... pattern
        message = re.sub(
            r"PrivateKey\s*[=:]\s*\S+",
            "PrivateKey=***REDACTED***",
            message,
            flags=re.IGNORECASE,
        )
        # BIP32 extended keys (xprv, xpub, yprv, zprv, etc.)
        message = re.sub(
            r"[x-z]prv[a-zA-Z0-9]{107,111}",
            "[BIP32_EXTENDED_KEY]",
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
        # WIF uncompressed (starts with '5')
        message = re.sub(
            r"5[1-9A-HJ-NP-Za-km-z]{50,51}",
            "[WIF_UNCOMPRESSED_KEY]",
            message,
        )
        # WIF compressed (starts with 'K' or 'L')
        message = re.sub(
            r"[KL][1-9A-HJ-NP-Za-km-z]{50,51}",
            "[WIF_COMPRESSED_KEY]",
            message,
        )
        return message

    @staticmethod
    def redact_data(data: dict[str, Any] | list[Any] | str) -> dict[str, Any] | list[Any] | str:
        """Recursively redact sensitive data from dicts, lists, or strings.

        Args:
            data: Data structure to redact (dict, list, or str)

        Returns:
            Redacted data structure of the same type

        """
        if isinstance(data, dict):
            return {key: SensitiveDataFilter.redact_data(value) for key, value in data.items()}
        if isinstance(data, list):
            return [SensitiveDataFilter.redact_data(item) for item in data]
        if isinstance(data, str):
            return SensitiveDataFilter.redact(data)
        return data

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and mask sensitive data in log records.

        Args:
            record: Log record

        Returns:
            False if sensitive data was detected in record.data (filter it out);
            True otherwise (let the record through after normal msg redaction).

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
                    # Redact in-place instead of discarding the record
                    redacted = SensitiveDataFilter.redact(data_str)
                    record.data = {"_redacted": True, "_original_type": type(record_data).__name__}
                    record.msg = f"[Sensitive data redacted] {redacted[:200]}"
                    return False  # Filter out records containing raw sensitive data in .data

        return True
