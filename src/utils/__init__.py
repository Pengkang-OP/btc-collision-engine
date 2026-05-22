"""Utility package for the BTC collision engine.

Provides logging, exception handling, encoding, and other shared
utilities used across the project.
"""

from .sensitive_patterns import (
    BECH32_ADDRESS,
    BECH32M_ADDRESS,
    BIP32_EXTENDED_KEY,
    BIP32_EXTENDED_PUBKEY,
    BIP39_CONTEXT_KEYWORDS,
    BIP39_PHRASE_12,
    BIP39_PHRASE_24,
    P2PKH_ADDRESS,
    P2SH_ADDRESS,
    PRIVATE_KEY_HEX,
    PRIVATE_KEY_CONTEXT,
    RAW_KEY,
    WIF_COMPRESSED,
    WIF_UNCOMPRESSED,
)
from .bech32_codec import (
    bech32_decode,
    bech32_encode,
    decode_segwit_address,
)
from .encoding_utils import EncodingUtils
from .exception_handler import ExceptionHandler
from .exceptions import (
    AddressGenerationError,
    CheckpointError,
    CollisionError,
    CollisionEngineError,
    ConfigError,
    CryptoBackendError,
    DeduplicationError,
    GPUError,
    KeyGenerationError,
    TargetResolutionError,
    ValidationError,
)
from .file_utils import (
    atomic_json_read,
    atomic_json_write,
    atomic_write,
    ensure_directory,
    get_file_size_safe,
    safe_file_delete,
)
from .logging_config import (
    LoggingConfig,
    get_configured_logger,
    init_logging,
)

__all__ = [
    "get_configured_logger",
    "LoggingConfig",
    "init_logging",
    "CollisionError",
    "CollisionEngineError",
    "ConfigError",
    "ValidationError",
    "KeyGenerationError",
    "AddressGenerationError",
    "CheckpointError",
    "DeduplicationError",
    "TargetResolutionError",
    "CryptoBackendError",
    "GPUError",
    "ExceptionHandler",
    "EncodingUtils",
    "atomic_json_write",
    "atomic_json_read",
    "atomic_write",
    "safe_file_delete",
    "get_file_size_safe",
    "ensure_directory",
    "bech32_decode",
    "bech32_encode",
    "decode_segwit_address",
    "PRIVATE_KEY_HEX",
    "WIF_UNCOMPRESSED",
    "WIF_COMPRESSED",
    "RAW_KEY",
    "PRIVATE_KEY_CONTEXT",
    "P2PKH_ADDRESS",
    "P2SH_ADDRESS",
    "BECH32_ADDRESS",
    "BECH32M_ADDRESS",
    "BIP32_EXTENDED_KEY",
    "BIP32_EXTENDED_PUBKEY",
    "BIP39_CONTEXT_KEYWORDS",
    "BIP39_PHRASE_12",
    "BIP39_PHRASE_24",
]
