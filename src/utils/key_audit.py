"""Key auditing utilities for security compliance."""

from ..utils import get_configured_logger
from typing import Any

logger = get_configured_logger("KeyAudit")


class KeyAuditor:
    """Audits private key generation and usage for compliance."""

    def __init__(self) -> None:
        """Initialize the key auditor."""
        self._audit_log: list[dict[str, Any]] = []

    def record_generation(
        self,
        key_hash: str,
    ) -> None:
        """Record a key generation event.

        Args:
            key_hash: SHA-256 hash of generated key

        """
        self._audit_log.append(
            {
                "event": "generation",
                "key_hash": key_hash,
            },
        )
        logger.debug(f"Key generation recorded: {key_hash[:8]}...")

    def get_report(self) -> list[dict[str, Any]]:
        """Get audit report.

        Returns:
            List of audit events

        """
        return list(self._audit_log)

    def clear(self) -> None:
        """Clear audit log."""
        self._audit_log.clear()
