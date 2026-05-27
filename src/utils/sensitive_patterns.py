"""Sensitive data pattern constants.

Centralizes regex patterns for detecting sensitive data shared by
SecurityLogFilter and SensitiveDataFilter.

v4.5.1: Extracted common patterns, eliminated regex duplication
between two filters.
"""

import re

# ====================================================================
# Private key patterns
# ====================================================================

# 64-char hex (32-byte private key), supports 0x prefix
PRIVATE_KEY_HEX = re.compile(
    r"(?<![0-9a-fA-F])(?:0x)?"
    r"[0-9a-fA-F]{64}"
    r"(?![0-9a-fA-F])",
)

# WIF uncompressed: starts with 5, 51 chars
WIF_UNCOMPRESSED = re.compile(
    r"\b5[HJK][1-9A-HJ-NP-Za-km-z]{48,49}\b",
)
# WIF compressed: starts with K or L, 52 chars
WIF_COMPRESSED = re.compile(
    r"\b[KL][1-9A-HJ-NP-Za-km-z]{50,51}\b",
)

# Raw byte pattern (32 bytes)
RAW_KEY = re.compile(
    r"(?<![\\/:a-zA-Z0-9])"
    r"b'\\x[0-9a-fA-F]{2}"
    r"(?:\\x[0-9a-fA-F]{2}){31}'"
    r"(?![\\/])",
)

# PrivateKey context pattern (used in SensitiveDataFilter only)
PRIVATE_KEY_CONTEXT = re.compile(
    r'PrivateKey["\']?\s*[:=]\s*'
    r'["\']?[0-9a-fA-F]{64}',
)

# ====================================================================
# Bitcoin address patterns
# ====================================================================

P2PKH_ADDRESS = re.compile(
    r"\b1[1-9A-HJ-NP-Za-km-z]{24,33}\b",
)
P2SH_ADDRESS = re.compile(
    r"\b3[1-9A-HJ-NP-Za-km-z]{24,33}\b",
)
BECH32_ADDRESS = re.compile(
    r"\bbc1[ac-hj-np-z02-9]{38,58}\b",
)
BECH32M_ADDRESS = re.compile(
    r"\bbc1p[ac-hj-np-z02-9]{58}\b",
)

# ====================================================================
# BIP32 extended key patterns
# ====================================================================

BIP32_EXTENDED_KEY = re.compile(
    r"\b[xXtT]prv[1-9A-HJ-NP-Za-km-z]{107,108}\b",
)
BIP32_EXTENDED_PUBKEY = re.compile(
    r"\b[xXtT]pub[1-9A-HJ-NP-Za-km-z]{107,108}\b",
)

# ====================================================================
# BIP39 seed phrase patterns
# ====================================================================

BIP39_CONTEXT_KEYWORDS = re.compile(
    r"\b(seed|mnemonic|recovery|phrase|bip39)\b",
    re.IGNORECASE,
)

BIP39_PHRASE_12 = re.compile(
    r"\b(?:[a-z]{3,8}\s+){11}[a-z]{3,8}\b",
    re.IGNORECASE,
)
BIP39_PHRASE_24 = re.compile(
    r"\b(?:[a-z]{3,8}\s+){23}[a-z]{3,8}\b",
    re.IGNORECASE,
)
