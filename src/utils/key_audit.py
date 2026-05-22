"""Key auditing utilities for security compliance."""

import hashlib

from ..utils import get_configured_logger

logger = get_configured_logger("KeyAudit")


class KeyAuditor:
    """Audits private key generation and usage for compliance."""

    def __init__(self):
        self._audit_log: list[dict] = []

    def record_generation(
        self, key_hash: str
    ) -> None:
        """Record a key generation event.

        Args:
            key_hash: SHA-256 hash of generated key
        """
        self._audit_log.append(
            {
                "event": "generation",
                "key_hash": key_hash,
            }
        )
        logger.debug(f"Key generation recorded: {key_hash[:8]}...")

    def get_report(self) -> list[dict]:
        """Get audit report.

        Returns:
            List of audit events
        """
        return list(self._audit_log)

    def clear(self) -> None:
        """Clear audit log."""
        self._audit_log.clear()
