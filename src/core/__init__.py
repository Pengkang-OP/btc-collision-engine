"""Core cryptographic and utility modules for the collision engine."""

# 地址生成
from .address_generator import BaseAddressGenerator, P2PKHAddressGenerator

# 编解码
from .base58 import Base58
from .bitcoin_key_validator import (
    AddressType,
    BitcoinKeyValidator,
    KeyValidationResult,
    validate_bitcoin_key_chain,
)

# 加密后端
from .crypto_backend import (
    BackendType,
    CryptoBackendManager,
    generate_public_key,
    get_crypto_backend,
    set_crypto_backend,
    verify_production_ready,
)

# 哈希
from .hash_utils import HashUtils

# 密钥
from .key_generator import SecureKeyGenerator

# 性能优化
from .memory_pool import (
    ByteArrayPool,
    ECPointPool,
    GlobalPoolManager,
    ObjectPool,
    get_pool_manager,
)
from .multi_format_generator import AddressFormat, MultiFormatAddressGenerator
from .optimized_address_generator import OptimizedP2PKHAddressGenerator
from .precomputed_table import PrecomputedPointTable, PrecomputedTableManager, get_precomputed_table

# 椭圆曲线
from .secp256k1 import ECPoint, EllipticCurve, Secp256k1
from .secure_key_manager import (
    SecureKeyManager,
    generate_secure_key,
    secure_key_context,
    validate_private_key,
)
from .simd_hash import batch_double_sha256, batch_hash160, batch_sha256
from .simd_optimizer import (
    BatchCollisionProcessor,
    BatchOptimizer,
    create_batch_optimizer,
    create_batch_processor,
)
from .thread_pool import (
    GlobalThreadPoolManager,
    TaskBatch,
    WorkStealingThreadPool,
    get_thread_pool,
)
from .wif import WIF

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
