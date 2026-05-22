#!/usr/bin/env python3
"""Target address resolver for collision engine.

Resolves Bitcoin addresses from various input formats into normalized
representations for matching.
"""

import re

from ...utils import get_configured_logger

logger = get_configured_logger("TargetResolver")


class TargetResolver:
    """Resolves and normalizes Bitcoin target addresses.

    Supports P2PKH, P2SH, Bech32, and raw Hash160 formats with
    automatic format detection.
    """

    MAX_INPUT_LENGTH = 1000

    @staticmethod
    def detect_format(
        input_str: str,
    ) -> str:
        """Detect the format of an address input string.

        Args:
            input_str: Raw input string

        Returns:
            Format string: 'p2pkh', 'p2sh', 'bech32',
                'raw_hash160', or 'unknown'
        """
        if (
            len(input_str)
            > TargetResolver.MAX_INPUT_LENGTH
        ):
            logger.warning(
                f"Input too long: {len(input_str)}"
            )
            return "unknown"
        s = input_str.strip()
        if len(s) == 40 and all(
            c in "0123456789abcdefABCDEF" for c in s
        ):
            return "raw_hash160"
        if s.startswith("1"):
            return "p2pkh"
        if s.startswith("3"):
            return "p2sh"
        if s.startswith("bc1"):
            return "bech32"
        return "unknown"
