# -*- coding: utf-8 -*-
"""P2PKH比特币地址生成器"""
import secrets
import hashlib
import ctypes
from typing import Tuple, Optional
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
        ctypes.memset(
            ctypes.addressof(ctypes.c_char.from_buffer(buffer)),
            0,
            len(buffer)
        )
    except (TypeError, ValueError, OSError) as e:
        # 如果buffer已被释放或无法访问，静默失败
        # 记录调试信息（不泄露敏感数据）
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"清零buffer失败: {type(e).__name__}")


class P2PKHAddressGenerator:
    """
    P2PKH比特币地址生成器
    
    协调整个地址生成流程，从私钥生成到最终比特币地址。
    使用版本字节0x00生成主网P2PKH地址（以'1'开头）。
    
    属性:
        ec: 椭圆曲线运算器实例
    
    示例:
        >>> generator = P2PKHAddressGenerator()
        >>> address, compressed_pk, uncompressed_pk = generator.generate_address()
    """
    
    def __init__(self):
        """
        初始化地址生成器
        
        创建椭圆曲线运算器实例，并检查加密后端性能。
        """
        self.ec = EllipticCurve()
        
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
            
            if backend.name == 'PURE_PYTHON':
                import warnings
                warnings.warn(
                    "当前使用纯Python加密后端，性能较低。"
                    "建议安装 coincurve 库以获得3-5倍性能提升：\n"
                    "  pip install coincurve>=18.0.0",
                    PerformanceWarning,
                    stacklevel=2
                )
                logger.info(
                    "提示: 安装 coincurve 库可提升3-5倍性能 "
                    "(pip install coincurve>=18.0.0)"
                )
        except ImportError as e:
            # 静默失败，不影响功能
            logger.debug(f"coincurve库不可用（将使用纯 Python 实现）: {e}")
    
    def generate_private_key(self, max_retries: int = 100) -> bytes:
        """
        生成随机私钥
        
        使用加密安全的随机数生成器生成32字节私钥。
        确保私钥在有效范围内（1 <= key < N）。
        
        参数:
            max_retries: 最大重试次数，默认100次
            
        返回:
            32字节私钥
            
        异常:
            KeyGenerationError: 当无法在max_retries次内生成有效私钥时
        """
        from ..utils.exceptions import KeyGenerationError
        
        for attempt in range(max_retries):
            try:
                # 使用加密安全的随机数生成器
                private_key = secrets.token_bytes(32)
                key_int = int.from_bytes(private_key, 'big')
                
                # 验证范围: 1 <= key < N
                if 1 <= key_int < Secp256k1.N:
                    logger.debug(f"私钥生成成功 (尝试 {attempt + 1}/{max_retries})")
                    return private_key
            except Exception as e:
                # 异常处理，避免泄露私钥信息
                # 采用分类处理策略：
                # 1. 自定义异常：记录错误码
                # 2. 标准异常：仅记录类型
                # 3. 未知异常：记录类型和消息哈希（用于追踪但不泄露）
                if isinstance(e, KeyGenerationError):
                    # 自定义异常：记录错误码，不记录详情
                    logger.error("生成私钥时出错 (尝试 %d/%d): 错误码=%d", 
                                attempt + 1, max_retries, e.error_code)
                elif isinstance(e, (ValueError, TypeError, OverflowError)):
                    # 标准异常：仅记录异常类型，不记录消息
                    logger.error("生成私钥时出错 (尝试 %d/%d): %s", 
                                attempt + 1, max_retries, type(e).__name__)
                else:
                    # 未知异常：记录类型和消息的哈希值（用于追踪但不泄露）
                    msg_hash = hashlib.sha256(str(e).encode()).hexdigest()[:8]
                    logger.error("生成私钥时出错 (尝试 %d/%d): %s [hash:%s]", 
                                attempt + 1, max_retries, type(e).__name__, msg_hash)
                # 继续尝试生成
        
        # 超过最大重试次数
        logger.error(f"私钥生成失败: 超过最大重试次数 {max_retries}")
        raise KeyGenerationError(
            f"无法在 {max_retries} 次尝试内生成有效私钥",
            error_code=1001,
            context={"max_retries": max_retries}
        )
    
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
        """
        从公钥生成比特币地址
        
        执行Hash160哈希和Base58Check编码。
        
        参数:
            public_key: 公钥字节串（压缩或非压缩）
            
        返回:
            以'1'开头的比特币地址
        """
        # Hash160哈希
        hash160 = HashUtils.hash160(public_key)
        
        # Base58Check编码（版本字节0x00）
        address = Base58.check_encode(0x00, hash160)
        
        return address
    
    def generate_address(self, private_key: Optional[bytes] = None) -> Tuple[str, bytes, bytes]:
        """
        生成完整的比特币地址
        
        从私钥生成地址，返回地址和两种格式的公钥。
        
        参数:
            private_key: 可选的32字节私钥，None则随机生成
            
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
            key_int = int.from_bytes(private_key, 'big')
            if key_int == 0:
                raise ValueError("私钥不能为零，必须在范围 [1, N) 内")
            elif key_int >= Secp256k1.N:
                raise ValueError(
                    f"私钥超出曲线阶 N = {Secp256k1.N}。"
                    f"私钥必须在范围 [1, N) 内"
                )
        
        # 生成压缩公钥
        compressed_pk = self.private_key_to_public_key(private_key, compressed=True)
        
        # 生成非压缩公钥
        uncompressed_pk = self.private_key_to_public_key(private_key, compressed=False)
        
        # 生成地址
        address = self.public_key_to_address(compressed_pk)
        
        return address, compressed_pk, uncompressed_pk
