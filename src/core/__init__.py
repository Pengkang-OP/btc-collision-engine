"""核心算法模块包"""
from .secp256k1 import Secp256k1, ECPoint, EllipticCurve
from .hash_utils import HashUtils
from .base58 import Base58
from .wif import WIF
from .address_generator import BaseAddressGenerator, P2PKHAddressGenerator
from .crypto_backend import (
    CryptoBackend,
    BackendType,
    CryptoBackendManager,
    get_crypto_backend,
    generate_public_key,
    set_crypto_backend,
    get_available_backends,
    PurePythonBackend,
    OpenSSLBackend,
    CoincurveBackend,
    ECDSABackend
)
from .simd_optimizer import (
    SIMDVectorizedOperations,
    BatchCollisionProcessor,
    NumpyOptimizedAddressGenerator,
    create_simd_optimizer,
    create_batch_processor
)
from .precomputed_table import (
    PrecomputedPointTable,
    PrecomputedTableManager,
    get_precomputed_table,
    precomputed_table_manager
)
from .bigint_optimizer import (
    BigIntOptimizer,
    get_bigint_optimizer,
    bigint_optimizer
)
from .simd_hash import (
    SIMDHashOptimizer,
    get_simd_hash_optimizer,
    simd_hash_optimizer
)
from .memory_pool import (
    ObjectPool,
    ECPointPool,
    ByteArrayPool,
    GlobalPoolManager,
    pool_manager,
    get_pool_manager
)
from .thread_pool import (
    WorkStealingThreadPool,
    TaskBatch,
    GlobalThreadPoolManager,
    thread_pool_manager,
    get_thread_pool
)
from .optimized_address_generator import (
    OptimizedP2PKHAddressGenerator
)
from .target_address_table import BitcoinTargetTable
from .key_generator import SecureKeyGenerator
from .address_converter import AddressConverter
from .compliance_validator import BitcoinComplianceValidator

__all__ = [
    'Secp256k1',
    'ECPoint',
    'EllipticCurve',
    'HashUtils',
    'Base58',
    'WIF',
    'BaseAddressGenerator',
    'P2PKHAddressGenerator',
    # 加密后端
    'CryptoBackend',
    'BackendType',
    'CryptoBackendManager',
    'get_crypto_backend',
    'generate_public_key',
    'set_crypto_backend',
    'get_available_backends',
    'PurePythonBackend',
    'OpenSSLBackend',
    'CoincurveBackend',
    'ECDSABackend',
    # SIMD优化
    'SIMDVectorizedOperations',
    'BatchCollisionProcessor',
    'NumpyOptimizedAddressGenerator',
    'create_simd_optimizer',
    'create_batch_processor',
    # 预计算表
    'PrecomputedPointTable',
    'PrecomputedTableManager',
    'get_precomputed_table',
    'precomputed_table_manager',
    # 大整数优化
    'BigIntOptimizer',
    'get_bigint_optimizer',
    'bigint_optimizer',
    # SIMD哈希优化
    'SIMDHashOptimizer',
    'get_simd_hash_optimizer',
    'simd_hash_optimizer',
    # 内存池
    'ObjectPool',
    'ECPointPool',
    'ByteArrayPool',
    'GlobalPoolManager',
    'pool_manager',
    'get_pool_manager',
    # 线程池
    'WorkStealingThreadPool',
    'TaskBatch',
    'GlobalThreadPoolManager',
    'thread_pool_manager',
    'get_thread_pool',
    # 优化版地址生成器
    'OptimizedP2PKHAddressGenerator',
    # 业务逻辑核心模块
    'BitcoinTargetTable',
    'SecureKeyGenerator',
    'AddressConverter',
    'BitcoinComplianceValidator'
]
