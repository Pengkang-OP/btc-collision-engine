"""核心算法模块包"""
from .secp256k1 import Secp256k1, ECPoint, EllipticCurve
from .hash_utils import HashUtils
from .base58 import Base58
from .wif import WIF
from .address_generator import P2PKHAddressGenerator
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

__all__ = [
    'Secp256k1',
    'ECPoint',
    'EllipticCurve',
    'HashUtils',
    'Base58',
    'WIF',
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
    'create_batch_processor'
]
