"""Utility package for the BTC collision engine.

Provides logging, exception handling, encoding, and other shared
utilities used across the project.
"""

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
    CollisionEngineError,
    CollisionError,
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
    PRIVATE_KEY_CONTEXT,
    PRIVATE_KEY_HEX,
    RAW_KEY,
    WIF_COMPRESSED,
    WIF_UNCOMPRESSED,
)

__all__ = [
    "BECH32M_ADDRESS",
    "BECH32_ADDRESS",
    "BIP32_EXTENDED_KEY",
    "BIP32_EXTENDED_PUBKEY",
    "BIP39_CONTEXT_KEYWORDS",
    "BIP39_PHRASE_12",
    "BIP39_PHRASE_24",
    "P2PKH_ADDRESS",
    "P2SH_ADDRESS",
    "PRIVATE_KEY_CONTEXT",
    "PRIVATE_KEY_HEX",
    "RAW_KEY",
    "WIF_COMPRESSED",
    "WIF_UNCOMPRESSED",
    "AddressGenerationError",
    "CheckpointError",
    "CollisionEngineError",
    "CollisionError",
    "ConfigError",
    "CryptoBackendError",
    "DeduplicationError",
    "EncodingUtils",
    "ExceptionHandler",
    "GPUError",
    "KeyGenerationError",
    "LoggingConfig",
    "TargetResolutionError",
    "ValidationError",
    "atomic_json_read",
    "atomic_json_write",
    "atomic_write",
    "bech32_decode",
    "bech32_encode",
    "decode_segwit_address",
    "ensure_directory",
    "get_configured_logger",
    "get_file_size_safe",
    "init_logging",
    "safe_file_delete",
]
