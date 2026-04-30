# -*- coding: utf-8 -*-
"""P2PKH比特币地址生成器

提供地址生成的共享基类和标准实现。
- BaseAddressGenerator: 共享基类（私钥生成、公钥推导、地址编码）
- P2PKHAddressGenerator: 标准实现（crypto_backend路径、性能检查）
- OptimizedP2PKHAddressGenerator: 优化实现（预计算表+SIMD+内存池，在 optimized_address_generator.py）
"""

import secrets
import hashlib
import ctypes
from typing import Tuple, Optional
from abc import ABC, abstractmethod
from .secp256k1 import EllipticCurve, Secp256k1
from .hash_utils import HashUtils
from .base58 import Base58

# 导入日志配置
from ..utils import init_logging, get_configured_logger

# 初始化日志系统（如果尚未初始化）
init_logging()

# 获取模块日志记录器
logger = get_configured_logger("AddressGenerator")


class PerformanceWarning(UserWarning):
    """性能警告：当前配置可能不是最优"""

    pass


def secure_clear_bytearray(buffer: bytearray) -> None:
    """
    安全清零bytearray内存

    使用ctypes直接清零bytearray的内存，防止敏感数据在内存中残留。

    参数:
        buffer: 要清零的bytearray对象（必须是可变的bytearray）

    注意:
        - bytes对象不可变，无法清零，必须先转换为bytearray
        - Python的垃圾回收机制可能会复制对象，此方法仅能清零当前引用
        - 对于最高安全要求，建议使用专门的密码学库（如cryptography.io）
        - 此方法适用于临时存储私钥的bytearray对象

    示例:
        >>> # 正确用法：使用bytearray
        >>> private_key = bytearray(secrets.token_bytes(32))
        >>> # 使用私钥...
        >>> secure_clear_bytearray(private_key)  # 清零

        >>> # 错误用法：bytes不可变
        >>> private_key = secrets.token_bytes(32)  # bytes类型
        >>> # secure_clear_bytearray(private_key)  # 会失败！

    Raises:
        TypeError: 如果传入的不是bytearray类型
    """
    if not isinstance(buffer, bytearray):
        raise TypeError(
            f"必须传入bytearray类型，当前为{type(buffer).__name__}。"
            f"bytes对象不可变，无法清零。请先转换为bytearray。"
        )

    try:
        # 使用ctypes.memset直接清零bytearray的内存
        ctypes.memset(ctypes.addressof(ctypes.c_char.from_buffer(buffer)), 0, len(buffer))
    except (TypeError, ValueError, OSError) as e:
        # 如果buffer已被释放或无法访问，静默失败
        # 记录调试信息（不泄露敏感数据）
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(f"清零buffer失败: {type(e).__name__}")


class BaseAddressGenerator(ABC):
    """地址生成器共享基类

    定义地址生成的通用流程，子类只需实现 private_key_to_public_key()。
    所有地址生成器（标准版和优化版）都继承此类，消除代码重复。

    属性:
        ec: 椭圆曲线运算器实例

    子类必须实现:
        private_key_to_public_key(private_key, compressed) -> bytes
    """

    def __init__(self) -> None:
        """初始化基类 — 创建椭圆曲线运算器"""
        self.ec = EllipticCurve()

    @abstractmethod
    def private_key_to_public_key(self, private_key: bytes, compressed: bool = True) -> bytes:
        """从私钥推导公钥（子类必须实现）

        Args:
            private_key: 32字节私钥
            compressed: 是否使用压缩格式

        Returns:
            公钥字节串
        """
        ...

    def public_key_to_address(self, public_key: bytes) -> str:
        """从公钥生成比特币地址

        执行Hash160和Base58Check编码。子类可覆盖以使用优化路径（如SIMD）。

        Args:
            public_key: 公钥字节串（压缩或非压缩）

        Returns:
            以'1'开头的比特币地址
        """
        hash160 = HashUtils.hash160(public_key)
        address = Base58.check_encode(0x00, hash160)
        return address

    def generate_address(
        self, private_key: bytes, compressed: bool = True
    ) -> Tuple[str, bytes, bytes]:
        """从私钥生成完整地址

        Args:
            private_key: 32字节私钥（必须提供）
            compressed: 是否使用压缩公钥格式

        Returns:
            (address, public_key, private_key) 元组
        """
        public_key = self.private_key_to_public_key(private_key, compressed)
        address = self.public_key_to_address(public_key)
        return address, public_key, private_key

    def generate_private_key(self, max_retries: int = 100) -> bytes:
        """生成随机私钥

        使用加密安全的随机数生成器生成32字节私钥。
        确保私钥在有效范围内（1 <= key < N）。

        Args:
            max_retries: 最大重试次数，默认100次

        Returns:
            32字节私钥

        Raises:
            KeyGenerationError: 当无法在max_retries次内生成有效私钥时
        """
        from ..utils.exceptions import KeyGenerationError

        for attempt in range(max_retries):
            try:
                private_key = secrets.token_bytes(32)
                key_int = int.from_bytes(private_key, "big")

                if 1 <= key_int < Secp256k1.N:
                    logger.debug(f"私钥生成成功 (尝试 {attempt + 1}/{max_retries})")
                    return private_key
            except Exception as e:
                if isinstance(e, KeyGenerationError):
                    logger.error(
                        "生成私钥时出错 (尝试 %d/%d): 错误码=%d",
                        attempt + 1,
                        max_retries,
                        e.error_code,
                    )
                elif isinstance(e, (ValueError, TypeError, OverflowError)):
                    logger.error(
                        "生成私钥时出错 (尝试 %d/%d): %s",
                        attempt + 1,
                        max_retries,
                        type(e).__name__,
                    )
                else:
                    msg_hash = hashlib.sha256(str(e).encode()).hexdigest()[:8]
                    logger.error(
                        "生成私钥时出错 (尝试 %d/%d): %s [hash:%s]",
                        attempt + 1,
                        max_retries,
                        type(e).__name__,
                        msg_hash,
                    )

        logger.error(f"私钥生成失败: 超过最大重试次数 {max_retries}")
        raise KeyGenerationError(
            f"无法在 {max_retries} 次尝试内生成有效私钥",
            error_code=1001,
            context={"max_retries": max_retries},
        )


class P2PKHAddressGenerator(BaseAddressGenerator):
    """
    P2PKH比特币地址生成器（标准实现）

    继承自 BaseAddressGenerator，使用 crypto_backend 进行公钥推导。
    支持自动生成私钥（generate_address() 不传参时）。

    属性:
        ec: 椭圆曲线运算器实例（继承自基类）

    示例:
        >>> generator = P2PKHAddressGenerator()
        >>> address, compressed_pk, uncompressed_pk = generator.generate_address()
    """

    def __init__(self) -> None:
        """
        初始化地址生成器

        创建椭圆曲线运算器实例，并检查加密后端性能。
        """
        super().__init__()

        # 检查加密后端并发出性能警告
        self._check_crypto_backend_performance()

    def _check_crypto_backend_performance(self):
        """
        检查加密后端并发出性能警告

        如果当前使用纯Python后端，发出警告建议安装coincurve。
        """
        try:
            from .crypto_backend import crypto_manager

            backend = crypto_manager.current_backend

            if backend.name == "PURE_PYTHON":
                import warnings

                warnings.warn(
                    "当前使用纯Python加密后端，性能较低。"
                    "建议安装 coincurve 库以获得3-5倍性能提升：\n"
                    "  pip install coincurve>=18.0.0",
                    PerformanceWarning,
                    stacklevel=2,
                )
                logger.info(
                    "提示: 安装 coincurve 库可提升3-5倍性能 " "(pip install coincurve>=18.0.0)"
                )
        except ImportError as e:
            # 静默失败，不影响功能
            logger.debug(f"coincurve库不可用（将使用纯 Python 实现）: {e}")

    def generate_private_key(self, max_retries: int = 100) -> bytes:
        """生成随机私钥（委托给基类实现）"""
        return super().generate_private_key(max_retries)

    def private_key_to_public_key(self, private_key: bytes, compressed: bool = True) -> bytes:
        """
        从私钥生成公钥

        参数:
            private_key: 32字节私钥
            compressed: 是否使用压缩格式，默认True

        返回:
            公钥字节串
        """
        # 优先使用加密后端管理器（支持多种后端）
        try:
            from .crypto_backend import crypto_manager

            return crypto_manager.generate_public_key(private_key, compressed)
        except (ImportError, AttributeError) as e:
            # 回退到纯 Python 实现
            logger.debug(f"加密后端不可用，使用纯 Python 实现: {type(e).__name__}")
            return self.ec.generate_public_key(private_key, compressed)

    def public_key_to_address(self, public_key: bytes) -> str:
        """从公钥生成比特币地址（委托给基类实现）"""
        return super().public_key_to_address(public_key)

    def generate_address(
        self,
        private_key: Optional[bytes] = None,
        compressed: bool = True,
    ) -> Tuple[str, bytes, bytes]:
        """
        生成完整的比特币地址

        从私钥生成地址。P2PKHAddressGenerator 始终返回两种格式的公钥
        (compressed_public_key, uncompressed_public_key)，因此 compressed
        参数被接受但仅用于与基类接口兼容，不影响实际行为。

        参数:
            private_key: 可选的32字节私钥，None则随机生成
            compressed: 基类兼容参数，不影响 P2PKHAddressGenerator 行为

        返回:
            (address, compressed_public_key, uncompressed_public_key)元组

        异常:
            ValueError: 当私钥长度无效或超出有效范围时
        """
        # 生成或验证私钥
        if private_key is None:
            private_key = self.generate_private_key()
        elif len(private_key) != 32:
            raise ValueError(f"私钥长度必须为32字节，当前为{len(private_key)}字节")
        else:
            # 验证私钥在有效范围内 [1, N)
            key_int = int.from_bytes(private_key, "big")
            if key_int == 0:
                raise ValueError("私钥不能为零，必须在范围 [1, N) 内")
            elif key_int >= Secp256k1.N:
                raise ValueError(f"私钥超出曲线阶 N = {Secp256k1.N}。" f"私钥必须在范围 [1, N) 内")

        # 生成压缩公钥
        compressed_pk = self.private_key_to_public_key(private_key, compressed=True)

        # 生成非压缩公钥
        uncompressed_pk = self.private_key_to_public_key(private_key, compressed=False)

        # 生成地址
        address = self.public_key_to_address(compressed_pk)

        return address, compressed_pk, uncompressed_pk


# 向后兼容别名 (simd_optimizer.py 等旧代码引用)
AddressGenerator = P2PKHAddressGenerator
