#!/usr/bin/env python3
"""
Collision detection helper functions.
"""

from typing import Any


def create_match_record(
    private_key: bytes,
    address: str,
    wif: str,
    worker_id: int = 0,
    device_idx: int = 0,
) -> dict[str, Any]:
    """Create a standardized match record.

    Args:
        private_key: Matched private key bytes
        address: Matched Bitcoin address
        wif: WIF-encoded private key
        worker_id: Worker thread ID
        device_idx: GPU device index

    Returns:
        Match record dictionary
    """
    return {
        "private_key": private_key,
        "address": address,
        "wif": wif,
        "worker_id": worker_id,
        "device_idx": device_idx,
    }


def is_match_found(stats: dict) -> bool:
    """Check if any matches were found from stats.

    Args:
        stats: Collision statistics dictionary

    Returns:
        True if matches found
    """
    return stats.get("total_matches", 0) > 0
