"""核心算法模块包"""

from .address_converter import AddressConverter
from .address_generator import BaseAddressGenerator, P2PKHAddressGenerator
from .base58 import Base58
from .bigint_optimizer import BigIntOptimizer, bigint_optimizer, get_bigint_optimizer
from .compliance_validator import BitcoinComplianceValidator
from .crypto_backend import (
    BackendType,
    CoincurveBackend,
    CryptoBackend,
    CryptoBackendManager,
    ECDSABackend,
    OpenSSLBackend,
    PurePythonBackend,
    generate_public_key,
    get_available_backends,
    get_crypto_backend,
    set_crypto_backend,
)
from .hash_utils import HashUtils
from .key_generator import SecureKeyGenerator
from .memory_pool import (
    ByteArrayPool,
    ECPointPool,
    GlobalPoolManager,
    ObjectPool,
    get_pool_manager,
    pool_manager,
)
from .optimized_address_generator import OptimizedP2PKHAddressGenerator
from .precomputed_table import (
    PrecomputedPointTable,
    PrecomputedTableManager,
    get_precomputed_table,
    precomputed_table_manager,
)
from .secp256k1 import ECPoint, EllipticCurve, Secp256k1
from .simd_hash import SIMDHashOptimizer, get_simd_hash_optimizer, simd_hash_optimizer
from .simd_optimizer import (
    BatchCollisionProcessor,
    NumpyOptimizedAddressGenerator,
    SIMDVectorizedOperations,
    create_batch_processor,
    create_simd_optimizer,
)
from .target_address_table import BitcoinTargetTable
from .thread_pool import (
    GlobalThreadPoolManager,
    TaskBatch,
    WorkStealingThreadPool,
    get_thread_pool,
    thread_pool_manager,
)
from .wif import WIF

__all__ = [
    "Secp256k1",
    "ECPoint",
    "EllipticCurve",
    "HashUtils",
    "Base58",
    "WIF",
    "BaseAddressGenerator",
    "P2PKHAddressGenerator",
    # 加密后端
    "CryptoBackend",
    "BackendType",
    "CryptoBackendManager",
    "get_crypto_backend",
    "generate_public_key",
    "set_crypto_backend",
    "get_available_backends",
    "PurePythonBackend",
    "OpenSSLBackend",
    "CoincurveBackend",
    "ECDSABackend",
    # SIMD优化
    "SIMDVectorizedOperations",
    "BatchCollisionProcessor",
    "NumpyOptimizedAddressGenerator",
    "create_simd_optimizer",
    "create_batch_processor",
    # 预计算表
    "PrecomputedPointTable",
    "PrecomputedTableManager",
    "get_precomputed_table",
    "precomputed_table_manager",
    # 大整数优化
    "BigIntOptimizer",
    "get_bigint_optimizer",
    "bigint_optimizer",
    # SIMD哈希优化
    "SIMDHashOptimizer",
    "get_simd_hash_optimizer",
    "simd_hash_optimizer",
    # 内存池
    "ObjectPool",
    "ECPointPool",
    "ByteArrayPool",
    "GlobalPoolManager",
    "pool_manager",
    "get_pool_manager",
    # 线程池
    "WorkStealingThreadPool",
    "TaskBatch",
    "GlobalThreadPoolManager",
    "thread_pool_manager",
    "get_thread_pool",
    # 优化版地址生成器
    "OptimizedP2PKHAddressGenerator",
    # 业务逻辑核心模块
    "BitcoinTargetTable",
    "SecureKeyGenerator",
    "AddressConverter",
    "BitcoinComplianceValidator",
]
