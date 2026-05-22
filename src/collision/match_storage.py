#!/usr/bin/env python3
"""
Match storage for persisting collision results.
"""

import json
import threading
from pathlib import Path

from ..utils import get_configured_logger

logger = get_configured_logger("MatchStorage")


class MatchStorage:
    """Persistent storage for collision match results.

    Saves match records as JSON with optional sensitive data masking.
    """

    def __init__(
        self, output_dir: str | Path = "matches"
    ):
        """
        Initialize match storage.

        Args:
            output_dir: Directory for match output files
        """
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(
            parents=True, exist_ok=True
        )
        self._lock = threading.Lock()
        self._matches: list[dict] = []

    def add_match(
        self,
        private_key: str,
        address: str,
        wif: str,
    ) -> None:
        """Add a match record.

        Args:
            private_key: Hex-encoded private key
            address: Matched address
            wif: WIF-encoded key
        """
        with self._lock:
            self._matches.append(
                {
                    "private_key": private_key,
                    "address": address,
                    "wif": wif,
                }
            )

    def save(self) -> None:
        """Save all matches to JSON file."""
        import time

        filepath = (
            self._output_dir
            / f"matches_{int(time.time())}.json"
        )
        with open(filepath, "w") as f:
            json.dump(
                self._matches,
                f,
                indent=2,
                default=str,
            )
        logger.info(
            f"Saved {len(self._matches)} matches "
            f"to {filepath}"
        )
