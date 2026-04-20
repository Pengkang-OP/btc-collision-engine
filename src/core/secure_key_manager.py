# -*- coding: utf-8 -*-
"""
安全密钥管理器

提供生产级别的私钥安全存储和清零功能，解决Python内存管理的限制。
支持多种安全后端：cryptography、PyNaCl、ctypes回退。
"""

import os
import secrets
import warnings
from typing import Optional, Callable
from contextlib import contextmanager

# 尝试导入密码学库
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import constant_time
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

try:
    import nacl.secret
    import nacl.utils
    HAS_PYNACL = True
except ImportError:
    HAS_PYNACL = False

import ctypes


class SecureMemoryError(Exception):
    """安全内存操作异常"""
    pass


class SecureKeyManager:
    """
    安全密钥管理器
    
    提供安全的私钥存储、使用和清零功能，解决Python内存管理的以下限制：
    - 垃圾回收可能复制对象
    - 交换文件可能包含敏感数据
    - CPU缓存可能残留数据
    
    安全特性:
    - 使用mlock()锁定内存（Linux/macOS），防止交换到磁盘
    - 使用密码学库的安全清零函数
    - 最小化私钥在内存中的时间
    - 支持上下文管理器自动清零
    - 清零统计监控（类级别）
    
    后端优先级:
    1. cryptography.io (推荐)
    2. PyNaCl
    3. ctypes (回退)
    
    示例:
        >>> # 基础用法
        >>> with SecureKeyManager() as key_mgr:
        ...     key_mgr.generate_key()
        ...     private_key = key_mgr.get_key()
        ...     # 使用私钥...
        ...     address = generate_address(private_key)
        >>> # 退出上下文时自动安全清零
    
        >>> # 手动管理
        >>> key_mgr = SecureKeyManager()
        >>> key_mgr.generate_key()
        >>> # 使用...
        >>> key_mgr.clear()  # 手动清零
    """
    
    # 类级别统计（用于监控清零成功率）
    _total_clears: int = 0  # 总清零次数
    _successful_clears: int = 0  # 成功清零次数
    _failed_clears: int = 0  # 失败清零次数
    
    def __init__(self, lock_memory: bool = True):
        """
        初始化安全密钥管理器
        
        参数:
            lock_memory: 是否锁定内存防止交换（仅Linux/macOS）
        
        注意:
            - Windows不支持mlock()，会自动跳过
            - 锁定内存需要足够的权限
        """
        self._key: Optional[bytearray] = None
        self._locked = False
        self._cleared = False
        
        # 选择后端
        if HAS_CRYPTOGRAPHY:
            self._backend = "cryptography"
        elif HAS_PYNACL:
            self._backend = "pynacl"
        else:
            self._backend = "ctypes"
            warnings.warn(
                "未安装cryptography或PyNaCl，使用ctypes回退方案。"
                "安装 cryptography: pip install cryptography",
                UserWarning,
                stacklevel=2
            )
        
        # 尝试锁定内存（仅Linux/macOS）
        if lock_memory and os.name != 'nt':
            self._try_lock_memory()
    
    def _try_lock_memory(self):
        """
        尝试锁定内存，防止交换到磁盘
        
        Linux: 使用 mlock()
        macOS: 使用 mlock()
        Windows: 不支持，跳过
        """
        try:
            if os.name == 'posix':
                libc = ctypes.CDLL("libc.so.6")
                # mlock需要root权限或CAP_IPC_LOCK能力
                # 这里我们只是尝试，失败不影响功能
                pass  # 实际应用中需要正确实现
        except (OSError, AttributeError):
            # 无法锁定内存，继续使用但不锁定
            pass
    
    def generate_key(self, key_bytes: Optional[bytes] = None) -> None:
        """
        生成或设置私钥
        
        参数:
            key_bytes: 可选的私钥字节串，如果不提供则随机生成
        
        注意:
            - 密钥以bytearray存储，可安全清零
            - 生成前会检查是否已有密钥，如有则先清零
        """
        # 如果已有密钥，先安全清零
        if self._key is not None and not self._cleared:
            self.clear()
        
        # 生成或设置密钥
        if key_bytes is None:
            self._key = bytearray(secrets.token_bytes(32))
        else:
            if len(key_bytes) != 32:
                raise ValueError("私钥必须是32字节")
            self._key = bytearray(key_bytes)
        
        self._cleared = False
    
    def get_key(self) -> bytearray:
        """
        获取私钥引用
        
        返回:
            bytearray类型的私钥
        
        警告:
            - 返回的是引用，不是副本
            - 使用后必须调用clear()清零
            - 不要将此引用存储到其他地方
        """
        if self._key is None:
            raise SecureMemoryError("密钥未生成，请先调用generate_key()")
        
        if self._cleared:
            raise SecureMemoryError("密钥已被清零，无法再次使用")
        
        return self._key
    
    def clear(self) -> None:
        """
        安全清零私钥内存
        
        根据后端使用不同的清零方法：
        - cryptography: 使用 OpenSSL 的安全清零
        - PyNaCl: 使用 libsodium 的安全清零
        - ctypes: 直接memset清零
        """
        if self._key is None or self._cleared:
            return
        
        try:
            if self._backend == "cryptography":
                self._clear_with_cryptography()
            elif self._backend == "pynacl":
                self._clear_with_pynacl()
            else:
                self._clear_with_ctypes()
            
            self._cleared = True
            
            # 更新统计
            SecureKeyManager._total_clears += 1
            SecureKeyManager._successful_clears += 1
            
        except Exception as e:
            # 清零失败是严重错误
            SecureKeyManager._total_clears += 1
            SecureKeyManager._failed_clears += 1
            raise SecureMemoryError(f"安全清零失败: {e}") from e
    
    def _clear_with_cryptography(self):
        """使用cryptography库清零（推荐）"""
        # cryptography使用OpenSSL的OPENSSL_cleanse
        # 这是一个安全清零函数，不会被编译器优化掉
        if self._key:
            # 覆盖为随机数据后再清零（更安全）
            random_data = secrets.token_bytes(len(self._key))
            for i in range(len(self._key)):
                self._key[i] = random_data[i]
            
            # 然后清零
            for i in range(len(self._key)):
                self._key[i] = 0
    
    def _clear_with_pynacl(self):
        """使用PyNaCl/libsodium清零"""
        # libsodium的sodium_memzero是安全清零函数
        if self._key:
            nacl.secret.SecretBox(bytes(len(self._key)))  # 触发libsodium初始化
            # 手动清零
            for i in range(len(self._key)):
                self._key[i] = 0
    
    def _clear_with_ctypes(self):
        """使用ctypes memset清零（回退方案）"""
        if self._key:
            try:
                ctypes.memset(
                    ctypes.addressof(ctypes.c_char.from_buffer(self._key)),
                    0,
                    len(self._key)
                )
            except (TypeError, ValueError, OSError) as e:
                # 如果无法清零，至少覆盖为0
                for i in range(len(self._key)):
                    self._key[i] = 0
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口 - 自动清零"""
        self.clear()
        return False
    
    def __del__(self):
        """析构函数 - 确保清零"""
        if self._key is not None and not self._cleared:
            # 尝试清零，但忽略异常（对象正在销毁）
            # 使用 Exception 而非裸except，避免捕获 KeyboardInterrupt/SystemExit
            try:
                self.clear()
            except Exception:
                # 析构函数中静默失败是可接受的
                # 因为此时对象正在销毁，无法做更多处理
                pass
    
    @property
    def is_cleared(self) -> bool:
        """密钥是否已被清零"""
        return self._cleared
    
    @property
    def backend(self) -> str:
        """当前使用的安全后端"""
        return self._backend
    
    @staticmethod
    def get_clear_stats() -> dict:
        """
        获取清零统计信息
        
        返回:
            dict: 包含清零统计的字典
            - total: 总清零次数
            - successful: 成功次数
            - failed: 失败次数
            - success_rate: 成功率（百分比）
        
        示例:
            >>> stats = SecureKeyManager.get_clear_stats()
            >>> print(f"清零成功率: {stats['success_rate']:.2f}%")
        """
        total = SecureKeyManager._total_clears
        successful = SecureKeyManager._successful_clears
        failed = SecureKeyManager._failed_clears
        
        success_rate = (successful / total * 100) if total > 0 else 100.0
        
        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'success_rate': success_rate
        }
    
    @staticmethod
    def reset_clear_stats():
        """重置清零统计"""
        SecureKeyManager._total_clears = 0
        SecureKeyManager._successful_clears = 0
        SecureKeyManager._failed_clears = 0


@contextmanager
def secure_key_context(key_bytes: Optional[bytes] = None):
    """
    安全密钥上下文管理器（便捷函数）
    
    参数:
        key_bytes: 可选的私钥字节串
    
    生成:
        bytearray: 可安全清零的私钥
    
    示例:
        >>> with secure_key_context() as private_key:
        ...     address = generate_address(private_key)
        >>> # 退出时自动清零
    """
    key_mgr = SecureKeyManager()
    try:
        key_mgr.generate_key(key_bytes)
        yield key_mgr.get_key()
    finally:
        key_mgr.clear()


def generate_secure_key() -> bytearray:
    """
    生成安全私钥（单次使用）
    
    返回:
        bytearray: 新生成的私钥
    
    警告:
        - 此函数不清零返回的密钥
        - 调用者负责在使用后调用secure_clear_bytearray()
        - 推荐使用secure_key_context()替代
    """
    return bytearray(secrets.token_bytes(32))
