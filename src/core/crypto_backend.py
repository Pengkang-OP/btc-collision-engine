#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
加密后端抽象层

提供统一的椭圆曲线运算接口，支持多种后端实现：
- 纯Python实现（默认）
- OpenSSL（通过cryptography库）
- coincurve（libsecp256k1绑定）
- ecdsa库

使用策略模式允许运行时切换后端。

线程安全说明:
- CryptoBackendManager 使用 RLock 保护全局状态
- 后端切换操作是线程安全的
- 加密操作本身在锁外执行，避免性能瓶颈
"""

import threading
import time
import logging
from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any, cast
from enum import Enum, auto

# 导入日志配置
from ..utils import get_configured_logger

# 注意：不在模块级别调用init_logging()，由CLI入口统一初始化
# init_logging()  # ← 已移除，避免重复初始化

# 获取模块日志记录器
logger = get_configured_logger("CryptoBackend")


class BackendType(Enum):
    """加密后端类型"""

    PURE_PYTHON = auto()  # 纯Python实现
    OPENSSL = auto()  # OpenSSL (cryptography)
    COINCURVE = auto()  # coincurve (libsecp256k1)
    ECDSA = auto()  # ecdsa库


class CryptoBackend(ABC):
    """
    加密后端抽象基类

    定义椭圆曲线运算的统一接口。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """后端名称"""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """检查后端是否可用"""

    @abstractmethod
    def generate_public_key(self, private_key: bytes, compressed: bool = True) -> bytes:
        """
        从私钥生成公钥

        参数:
            private_key: 32字节私钥
            compressed: 是否使用压缩格式

        返回:
            公钥字节串
        """

    @abstractmethod
    def scalar_multiply(self, k: int, point_x: int, point_y: int) -> Tuple[int, int]:
        """
        椭圆曲线标量乘法

        参数:
            k: 标量
            point_x: 点的x坐标
            point_y: 点的y坐标

        返回:
            (rx, ry) 结果点坐标
        """

    @abstractmethod
    def is_constant_time(self) -> bool:
        """
        检查此后端是否使用恒定时间算法

        返回:
            True表示使用恒定时间算法
        """


class PurePythonBackend(CryptoBackend):
    """纯Python后端 - 使用现有的secp256k1.py实现"""

    def __init__(self, use_const_time: bool = False) -> None:
        from .secp256k1 import EllipticCurve, Secp256k1, ECPoint

        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        self._use_const_time = use_const_time

    @property
    def name(self) -> str:
        return "Pure Python" + (" (Constant Time)" if self._use_const_time else "")

    @property
    def is_available(self) -> bool:
        return True

    def generate_public_key(self, private_key: bytes, compressed: bool = True) -> bytes:
        if self._use_const_time:
            return cast(Any, self.ec).generate_public_key_const_time(private_key, compressed)
        else:
            return self.ec.generate_public_key(private_key, compressed)

    def scalar_multiply(self, k: int, point_x: int, point_y: int) -> Tuple[int, int]:
        from .secp256k1 import ECPoint

        point = ECPoint(point_x, point_y)

        if self._use_const_time:
            result = self.ec.scalar_multiply_const_time(k, point)
        else:
            result = self.ec.scalar_multiply(k, point)

        return cast(Tuple[int, int], (result.x, result.y))

    def is_constant_time(self) -> bool:
        return self._use_const_time


class OpenSSLBackend(CryptoBackend):
    """OpenSSL后端 - 使用cryptography库"""

    def __init__(self) -> None:
        self._available = self._check_availability()
        if self._available:
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.backends import default_backend

            self._ec = ec
            self._backend = default_backend()
            self._SECP256K1 = ec.SECP256K1()

    def _check_availability(self) -> bool:
        try:
            from cryptography.hazmat.primitives.asymmetric import ec  # noqa: F401

            return True
        except ImportError:
            return False

    @property
    def name(self) -> str:
        return "OpenSSL (cryptography)"

    @property
    def is_available(self) -> bool:
        return self._available

    def generate_public_key(self, private_key: bytes, compressed: bool = True) -> bytes:
        if not self._available:
            raise RuntimeError("OpenSSL backend not available")

        from cryptography.hazmat.primitives.asymmetric import ec

        # 使用私钥创建椭圆曲线私钥对象
        private_value = int.from_bytes(private_key, "big")
        private_key_obj = ec.derive_private_key(private_value, self._SECP256K1, self._backend)

        # 获取公钥
        public_key = private_key_obj.public_key()
        public_numbers = public_key.public_numbers()

        # 转换为字节格式
        x = public_numbers.x
        y = public_numbers.y

        x_bytes = x.to_bytes(32, "big")

        if compressed:
            # 压缩格式: 0x02 (y为偶数) 或 0x03 (y为奇数) + x坐标
            prefix = b"\x02" if (y % 2 == 0) else b"\x03"
            return prefix + x_bytes
        else:
            # 非压缩格式: 0x04 + x坐标 + y坐标
            y_bytes = y.to_bytes(32, "big")
            return b"\x04" + x_bytes + y_bytes

    def scalar_multiply(self, k: int, point_x: int, point_y: int) -> Tuple[int, int]:
        """
        注意: cryptography库不直接暴露点乘运算，
        我们通过创建临时私钥来实现。
        """
        if not self._available:
            raise RuntimeError("OpenSSL backend not available")

        from cryptography.hazmat.primitives.asymmetric import ec

        # 创建一个基于目标点的公钥
        # 然后使用标量乘法
        point = ec.EllipticCurvePublicNumbers(  # noqa: F841
            x=point_x, y=point_y, curve=self._SECP256K1
        )  # noqa: F841, E501

        # 这里我们需要使用底层操作
        # 由于cryptography库的限制，我们使用纯Python实现作为回退
        # 在实际应用中，可以考虑使用更低级的OpenSSL绑定
        from .secp256k1 import EllipticCurve, ECPoint

        ec_impl = EllipticCurve()
        result = ec_impl.scalar_multiply(k, ECPoint(point_x, point_y))

        return cast(Tuple[int, int], (result.x, result.y))

    def is_constant_time(self) -> bool:
        # P1-6 fix: generate_public_key() IS constant-time (uses OpenSSL ec.derive_private_key),
        # but scalar_multiply() falls back to PurePython EllipticCurve.scalar_multiply()
        # which is NOT constant-time (non-Montgomery Ladder, variable-time mod_inverse).
        # Since is_constant_time() should reflect the ENTIRE backend, return False.
        #
        # For this project's main use case (collision detection via generate_public_key),
        # the actual execution path IS constant-time. This flag is conservatively False
        # because scalar_multiply() is not constant-time.
        return False


class CoincurveBackend(CryptoBackend):
    """coincurve后端 - 使用libsecp256k1"""

    def __init__(self) -> None:
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        try:
            import coincurve  # noqa: F401

            return True
        except ImportError:
            return False

    @property
    def name(self) -> str:
        return "coincurve (libsecp256k1)"

    @property
    def is_available(self) -> bool:
        return self._available

    def generate_public_key(self, private_key: bytes, compressed: bool = True) -> bytes:
        if not self._available:
            raise RuntimeError("coincurve backend not available")

        import coincurve

        # 使用coincurve生成公钥
        private_key_obj = coincurve.PrivateKey(private_key)
        return private_key_obj.public_key.format(compressed=compressed)

    def scalar_multiply(self, k: int, point_x: int, point_y: int) -> Tuple[int, int]:
        """
        coincurve标量乘法

        coincurve提供了高效的标量乘法实现。
        """
        if not self._available:
            raise RuntimeError("coincurve backend not available")

        import coincurve

        # 创建公钥对象
        # 注意: coincurve的API可能需要调整
        # 这里使用公钥乘法的概念
        pubkey_bytes = b"\x04" + point_x.to_bytes(32, "big") + point_y.to_bytes(32, "big")

        try:
            pubkey = coincurve.PublicKey(pubkey_bytes)
            # coincurve.PublicKey.multiply 返回 PublicKey 对象
            result = pubkey.multiply(k.to_bytes(32, "big"))

            # 将结果格式化为非压缩公钥字节串 (0x04 + x + y)
            result_bytes = result.format(compressed=False) if hasattr(result, 'format') else bytes(result)
            if result_bytes[0] == 0x04 and len(result_bytes) >= 65:
                rx = int.from_bytes(result_bytes[1:33], "big")
                ry = int.from_bytes(result_bytes[33:65], "big")
                return rx, ry
        except (AttributeError, TypeError, AssertionError):
            # 如果multiply不可用或返回类型不匹配，使用纯Python回退
            pass

        # 回退到纯Python实现
        from .secp256k1 import EllipticCurve, ECPoint

        ec_impl = EllipticCurve()
        ec_result = ec_impl.scalar_multiply(k, ECPoint(point_x, point_y))
        return cast(Tuple[int, int], (ec_result.x, ec_result.y))

    def is_constant_time(self) -> bool:
        # libsecp256k1使用恒定时间算法
        return True


class ECDSABackend(CryptoBackend):
    """ecdsa库后端"""

    def __init__(self) -> None:
        self._available = self._check_availability()
        if self._available:
            from ecdsa import SigningKey, SECP256k1, VerifyingKey

            self._SigningKey = SigningKey
            self._SECP256k1 = SECP256k1
            self._VerifyingKey = VerifyingKey

    def _check_availability(self) -> bool:
        try:
            import ecdsa  # noqa: F401

            return True
        except ImportError:
            return False

    @property
    def name(self) -> str:
        return "ecdsa"

    @property
    def is_available(self) -> bool:
        return self._available

    def generate_public_key(self, private_key: bytes, compressed: bool = True) -> bytes:
        if not self._available:
            raise RuntimeError("ecdsa backend not available")

        # 使用ecdsa生成公钥
        signing_key = self._SigningKey.from_string(private_key, curve=self._SECP256k1)
        verifying_key = signing_key.get_verifying_key()

        if compressed:
            return cast(bytes, verifying_key.to_string("compressed"))
        else:
            return cast(bytes, b"\x04" + verifying_key.to_string())

    def scalar_multiply(self, k: int, point_x: int, point_y: int) -> Tuple[int, int]:
        """
        ecdsa标量乘法

        ecdsa库不直接暴露点乘运算，使用纯Python回退。
        """
        from .secp256k1 import EllipticCurve, ECPoint

        ec_impl = EllipticCurve()
        result = ec_impl.scalar_multiply(k, ECPoint(point_x, point_y))
        return cast(Tuple[int, int], (result.x, result.y))

    def is_constant_time(self) -> bool:
        # ecdsa库可能不使用恒定时间算法
        return False


class CryptoBackendManager:
    """
    加密后端管理器

    管理所有可用的加密后端，提供统一的访问接口。
    支持运行时切换后端。

    线程安全:
    - 使用 RLock 保护所有状态变更
    - 单例模式在模块导入时初始化，天然线程安全
    - 加密操作在锁外执行，避免性能瓶颈
    """

    _instance = None
    _lock = threading.RLock()  # 类级锁，保护单例创建
    _backends: Dict[Any, Any] = {}
    _current_backend = None
    _default_backend_type = BackendType.PURE_PYTHON

    def __new__(cls) -> "CryptoBackendManager":
        if cls._instance is None:
            with cls._lock:
                # 双重检查锁定模式
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_backends()
        return cls._instance

    def _init_backends(self):
        """初始化所有后端"""
        # 实例级锁，保护运行时状态
        self._instance_lock = threading.RLock()

        logger.debug("初始化加密后端...")

        # 按优先级顺序初始化
        self._backends[BackendType.PURE_PYTHON] = PurePythonBackend()
        self._backends[BackendType.OPENSSL] = OpenSSLBackend()
        self._backends[BackendType.COINCURVE] = CoincurveBackend()
        self._backends[BackendType.ECDSA] = ECDSABackend()

        # 设置默认后端
        self._select_best_backend()

        available = [bt.name for bt, backend in self._backends.items() if backend.is_available]
        assert self._current_backend is not None
        logger.info(f"加密后端初始化完成: 可用={available}, 当前={self._current_backend.name}")

    def _select_best_backend(self):
        """选择最佳可用后端（内部方法，调用者需持有锁）"""
        # 优先级: coincurve > OpenSSL > ecdsa > Pure Python
        priority_order = [
            BackendType.COINCURVE,
            BackendType.OPENSSL,
            BackendType.ECDSA,
            BackendType.PURE_PYTHON,
        ]

        with self._instance_lock:
            for backend_type in priority_order:
                backend = self._backends.get(backend_type)
                if backend and backend.is_available:
                    self._current_backend = backend
                    self._default_backend_type = backend_type
                    break

    def reset_to_best_backend(self) -> None:
        """
        重置为最佳可用后端（线程安全）

        公开的线程安全方法，替代直接调用 _select_best_backend
        """
        self._select_best_backend()

    @property
    def current_backend(self) -> CryptoBackend:
        """
        获取当前后端（线程安全）

        在锁内获取后端引用，确保获取的是一致的实例
        """
        with self._instance_lock:
            backend = self._current_backend
        if backend is None:
            raise RuntimeError("No crypto backend available")
        return cast(CryptoBackend, backend)

    def set_backend(self, backend_type: BackendType, **kwargs) -> bool:
        """
        设置当前后端（线程安全）

        所有状态更新在锁内原子完成，避免竞态条件。

        参数:
            backend_type: 后端类型
            **kwargs: 后端特定的参数

        返回:
            设置成功返回True
        """
        logger.debug(f"切换加密后端: {backend_type.name}, 参数={kwargs}")

        with self._instance_lock:
            if backend_type == BackendType.PURE_PYTHON:
                use_const_time = kwargs.get("use_const_time", False)
                existing = self._backends.get(backend_type)
                if existing is not None and isinstance(existing, PurePythonBackend):
                    existing._use_const_time = use_const_time
                else:
                    self._backends[backend_type] = PurePythonBackend(use_const_time)

            backend = self._backends.get(backend_type)
            if backend is None:
                logger.error(f"未知的后端类型: {backend_type}")
                raise ValueError(f"Unknown backend type: {backend_type}")

            if not backend.is_available:
                logger.error(f"后端不可用: {backend.name}")
                raise RuntimeError(f"Backend {backend.name} is not available")

            old_backend = self._current_backend.name if self._current_backend else "None"
            self._current_backend = backend
            self._default_backend_type = backend_type

        logger.info(f"加密后端已切换: {old_backend} -> {backend.name}")
        return True

    def get_available_backends(self) -> list:
        """获取所有可用后端列表（线程安全）"""
        with self._instance_lock:
            backends_copy = dict(self._backends)
        return [(bt, b.name) for bt, b in backends_copy.items() if b.is_available]

    def generate_public_key(self, private_key: bytes, compressed: bool = True) -> bytes:
        """
        使用当前后端生成公钥

        注意: 加密操作在锁外执行，避免性能瓶颈

        参数:
            private_key: 32字节私钥
            compressed: 是否使用压缩格式

        返回:
            公钥字节串
        """
        backend = self.current_backend  # 在锁内获取引用

        # 性能监控（仅在DEBUG级别）
        if logger.isEnabledFor(logging.DEBUG):
            start_time = time.perf_counter()
            result = backend.generate_public_key(private_key, compressed)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(f"公钥生成: {backend.name}, 耗时={elapsed_ms:.3f}ms")
            return result

        return backend.generate_public_key(private_key, compressed)

    def is_constant_time(self) -> bool:
        """检查当前后端是否使用恒定时间算法"""
        backend = self.current_backend  # 在锁内获取引用
        return backend.is_constant_time()


# 全局后端管理器实例
crypto_manager = CryptoBackendManager()


def get_crypto_backend() -> CryptoBackendManager:
    """
    获取加密后端管理器实例

    返回:
        CryptoBackendManager实例
    """
    return crypto_manager


# 便捷函数
def generate_public_key(private_key: bytes, compressed: bool = True) -> bytes:
    """
    使用当前后端生成公钥

    参数:
        private_key: 32字节私钥
        compressed: 是否使用压缩格式

    返回:
        公钥字节串
    """
    return crypto_manager.generate_public_key(private_key, compressed)


def set_crypto_backend(backend_type: BackendType, **kwargs) -> bool:
    """
    设置加密后端

    参数:
        backend_type: 后端类型
        **kwargs: 后端特定参数

    返回:
        设置成功返回True
    """
    return crypto_manager.set_backend(backend_type, **kwargs)


def get_available_backends() -> list:
    """获取所有可用后端"""
    return crypto_manager.get_available_backends()
