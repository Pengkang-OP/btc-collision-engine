#!/usr/bin/env python3
"""Target address storage and persistence."""

import json
from pathlib import Path

from ...utils import get_configured_logger

logger = get_configured_logger("TargetStorage")


class TargetStorage:
    """Persistent storage for target address sets."""

    def __init__(self, storage_dir: str | Path = "targets"):
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, addresses: list[str]) -> None:
        """Save an address set to file.

        Args:
            name: Address set name
            addresses: List of addresses
        """
        filepath = self._storage_dir / f"{name}.json"
        with open(filepath, "w") as f:
            json.dump(addresses, f, indent=2)
        logger.info(
            f"Saved {len(addresses)} addresses to {filepath}"
        )

    def load(self, name: str) -> list[str]:
        """Load an address set from file.

        Args:
            name: Address set name

        Returns:
            List of addresses
        """
        filepath = self._storage_dir / f"{name}.json"
        if not filepath.exists():
            logger.warning(f"Address set not found: {name}")
            return []
        with open(filepath) as f:
            return json.load(f)

    def list_sets(self) -> list[str]:
        """List available address sets.

        Returns:
            List of set names
        """
        return [
            p.stem
            for p in self._storage_dir.glob("*.json")
        ]
