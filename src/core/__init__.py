"""Core cryptographic and utility modules for the collision engine."""

# 地址生成
from .address_generator import BaseAddressGenerator, P2PKHAddressGenerator
from .optimized_address_generator import OptimizedP2PKHAddressGenerator
from .multi_format_generator import MultiFormatAddressGenerator, AddressFormat

# 编解码
from .base58 import Base58
from .wif import WIF

# 哈希
from .hash_utils import HashUtils
from .simd_hash import batch_sha256, batch_hash160, batch_double_sha256

# 椭圆曲线
from .secp256k1 import ECPoint, EllipticCurve, Secp256k1

# 加密后端
from .crypto_backend import (
    BackendType,
    CryptoBackendManager,
    get_crypto_backend,
    set_crypto_backend,
    generate_public_key,
    verify_production_ready,
)

# 密钥
from .key_generator import SecureKeyGenerator
from .secure_key_manager import (
    SecureKeyManager, secure_key_context, generate_secure_key, validate_private_key,
)
from .bitcoin_key_validator import (
    BitcoinKeyValidator, AddressType, KeyValidationResult, validate_bitcoin_key_chain,
)

# 性能优化
from .memory_pool import (
    GlobalPoolManager, get_pool_manager, ObjectPool, ECPointPool, ByteArrayPool,
)
from .precomputed_table import get_precomputed_table, PrecomputedPointTable, PrecomputedTableManager
from .simd_optimizer import (
    BatchOptimizer, BatchCollisionProcessor, create_batch_optimizer, create_batch_processor,
)
from .thread_pool import (
    WorkStealingThreadPool, GlobalThreadPoolManager, TaskBatch, get_thread_pool,
)

__all__ = [
    # 地址生成
    "BaseAddressGenerator",
    "P2PKHAddressGenerator",
    "OptimizedP2PKHAddressGenerator",
    "MultiFormatAddressGenerator",
    "AddressFormat",
    # 编解码
    "Base58",
    "WIF",
    # 哈希
    "HashUtils",
    "batch_sha256",
    "batch_hash160",
    "batch_double_sha256",
    # 椭圆曲线
    "ECPoint",
    "EllipticCurve",
    "Secp256k1",
    # 加密后端
    "BackendType",
    "CryptoBackendManager",
    "get_crypto_backend",
    "set_crypto_backend",
    "generate_public_key",
    "verify_production_ready",
    # 密钥
    "SecureKeyGenerator",
    "SecureKeyManager",
    "secure_key_context",
    "generate_secure_key",
    "validate_private_key",
    "BitcoinKeyValidator",
    "AddressType",
    "KeyValidationResult",
    "validate_bitcoin_key_chain",
    # 性能优化
    "GlobalPoolManager",
    "get_pool_manager",
    "ObjectPool",
    "ECPointPool",
    "ByteArrayPool",
    "get_precomputed_table",
    "PrecomputedPointTable",
    "PrecomputedTableManager",
    "BatchOptimizer",
    "BatchCollisionProcessor",
    "create_batch_optimizer",
    "create_batch_processor",
    "WorkStealingThreadPool",
    "GlobalThreadPoolManager",
    "TaskBatch",
    "get_thread_pool",
]
