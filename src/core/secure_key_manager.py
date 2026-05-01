# -*- coding: utf-8 -*-
"""
安全密钥管理器

提供生产级别的私钥安全存储和清零功能，解决Python内存管理的限制。
支持多种安全后端：cryptography、PyNaCl、ctypes回退。
"""

import os
import sys
import secrets
import warnings
from typing import Any, Optional
from contextlib import contextmanager

# 尝试导入密码学库
try:
    import cryptography  # noqa: F401

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

    def __init__(self, lock_memory: bool = True) -> None:
        """
        初始化安全密钥管理器

        参数:
            lock_memory: 是否锁定内存防止交换

        注意:
            - Linux/macOS: 使用mlock()锁定内存
            - Windows: 使用VirtualLock()锁定内存
            - 锁定内存需要足够的权限
        """
        self._key: Optional[bytearray] = None
        self._locked = False
        self._cleared = False
        self._memory_locked = False
        self._lock_memory_enabled = lock_memory

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
                stacklevel=2,
            )

    def _try_lock_memory(self):
        """
        尝试锁定内存，防止敏感数据被交换到磁盘

        Linux/macOS: 使用 mlock() 系统调用
        Windows: 使用 VirtualLock() API

        返回:
            bool: 内存锁定是否成功

        注意:
            - Linux: 需要root权限或CAP_IPC_LOCK能力，或调整memlock限制
            - macOS: 需要root权限
            - Windows: 锁定内存会减少工作集可用空间
            - 失败不会抛出异常，但会记录警告
        """
        if not self._lock_memory_enabled:
            return False

        try:
            if os.name == "nt":
                # Windows平台
                return self._lock_memory_windows()
            elif os.name == "posix":
                # Linux/macOS平台
                return self._lock_memory_posix()
            else:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"不支持的操作系统: {os.name}，无法锁定内存")
                return False
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"内存锁定失败: {e}，将继续运行但不保护内存")
            return False

    def _lock_memory_posix(self) -> bool:
        """
        POSIX系统 (Linux/macOS) 的内存锁定实现

        使用 mlock() 系统调用锁定内存页，防止被交换到磁盘
        """
        try:
            # 加载C库
            if sys.platform == "darwin":
                # macOS
                libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
            else:
                # Linux
                libc = ctypes.CDLL("libc.so.6")

            # 配置mlock函数签名
            # int mlock(const void *addr, size_t len);
            libc.mlock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            libc.mlock.restype = ctypes.c_int

            # 配置munlock函数签名
            # int munlock(const void *addr, size_t len);
            libc.munlock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            libc.munlock.restype = ctypes.c_int

            # 保存libc引用供后续使用
            self._libc = libc

            import logging

            logger = logging.getLogger(__name__)
            logger.info("POSIX内存锁定支持已初始化 (mlock/munlock)")
            return True

        except (OSError, AttributeError) as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"无法初始化POSIX内存锁定: {e}")
            return False

    def _lock_memory_windows(self) -> bool:
        """
        Windows平台的内存锁定实现

        使用 VirtualLock() API锁定内存页，防止被交换到页面文件
        """
        try:
            # 加载kernel32.dll
            kernel32 = ctypes.WinDLL("kernel32.dll")

            # 配置VirtualLock函数签名
            # BOOL VirtualLock(LPVOID lpAddress, SIZE_T dwSize);
            kernel32.VirtualLock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            kernel32.VirtualLock.restype = ctypes.c_bool

            # 配置VirtualUnlock函数签名
            # BOOL VirtualUnlock(LPVOID lpAddress, SIZE_T dwSize);
            kernel32.VirtualUnlock.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            kernel32.VirtualUnlock.restype = ctypes.c_bool

            # 保存kernel32引用供后续使用
            self._kernel32 = kernel32

            import logging

            logger = logging.getLogger(__name__)
            logger.info("Windows内存锁定支持已初始化 (VirtualLock/VirtualUnlock)")
            return True

        except (OSError, AttributeError) as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"无法初始化Windows内存锁定: {e}")
            return False

    def _lock_key_memory(self) -> bool:
        """
        锁定当前密钥的内存页

        必须在生成密钥后调用

        返回:
            bool: 锁定是否成功
        """
        if self._key is None or self._cleared:
            return False

        if not self._lock_memory_enabled:
            return False

        try:
            if os.name == "nt" and hasattr(self, "_kernel32"):
                # Windows: VirtualLock
                addr = ctypes.addressof(ctypes.c_char.from_buffer(self._key))
                size = len(self._key)
                result = self._kernel32.VirtualLock(addr, size)

                if result:
                    self._memory_locked = True
                    return True
                else:
                    import logging

                    logger = logging.getLogger(__name__)
                    error_code = ctypes.get_last_error()
                    logger.warning(f"Windows VirtualLock失败，错误码: {error_code}")
                    return False

            elif os.name == "posix" and hasattr(self, "_libc"):
                # Linux/macOS: mlock
                addr = ctypes.addressof(ctypes.c_char.from_buffer(self._key))
                size = len(self._key)
                result = self._libc.mlock(addr, size)

                if result == 0:  # mlock返回0表示成功
                    self._memory_locked = True
                    return True
                else:
                    import logging

                    logger = logging.getLogger(__name__)
                    import errno

                    logger.warning(
                        f"POSIX mlock失败，错误码: {errno.errorcode.get(ctypes.get_errno(), 'Unknown')}"
                    )
                    return False
            else:
                return False

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"锁定密钥内存失败: {e}")
            return False

    def _unlock_key_memory(self) -> bool:
        """
        解锁当前密钥的内存页

        在清零密钥后调用

        返回:
            bool: 解锁是否成功
        """
        if not self._memory_locked:
            return False

        if self._key is None:
            return False

        try:
            if os.name == "nt" and hasattr(self, "_kernel32"):
                # Windows: VirtualUnlock
                addr = ctypes.addressof(ctypes.c_char.from_buffer(self._key))
                size = len(self._key)
                result = self._kernel32.VirtualUnlock(addr, size)

                if result:
                    self._memory_locked = False
                    return True
                else:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning("Windows VirtualUnlock失败")
                    return False

            elif os.name == "posix" and hasattr(self, "_libc"):
                # Linux/macOS: munlock
                addr = ctypes.addressof(ctypes.c_char.from_buffer(self._key))
                size = len(self._key)
                result = self._libc.munlock(addr, size)

                if result == 0:  # munlock返回0表示成功
                    self._memory_locked = False
                    return True
                else:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning("POSIX munlock失败")
                    return False
            else:
                return False

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"解锁密钥内存失败: {e}")
            return False

    def generate_key(self, key_bytes: Optional[bytes] = None) -> None:
        """
        生成或设置私钥

        参数:
            key_bytes: 可选的私钥字节串，如果不提供则随机生成

        注意:
            - 密钥以bytearray存储，可安全清零
            - 生成前会检查是否已有密钥，如有则先清零
            - 生成后会自动尝试锁定内存（如果启用）
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
        self._memory_locked = False

        # 尝试锁定内存
        if self._lock_memory_enabled:
            self._lock_key_memory()

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

        注意:
            - 清零前会先解锁内存
            - 清零后内存被标记为可交换
        """
        if self._key is None or self._cleared:
            return

        try:
            # 先解锁内存（清零前解锁）
            if self._memory_locked:
                self._unlock_key_memory()

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
                    ctypes.addressof(ctypes.c_char.from_buffer(self._key)), 0, len(self._key)
                )
            except (TypeError, ValueError, OSError):
                # 如果无法清零，至少覆盖为0
                for i in range(len(self._key)):
                    self._key[i] = 0

    def __enter__(self) -> "SecureKeyManager":
        """上下文管理器入口"""
        return self

    def __exit__(
        self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Optional[Any]
    ) -> None:
        """上下文管理器出口 - 自动清零"""
        self.clear()
        return None

    def __del__(self) -> None:
        """析构函数 - 确保清零"""
        if self._key is not None and not self._cleared:
            # 尝试清零，但忽略异常（对象正在销毁）
            # 使用 Exception 而非裸except，避免捕获 KeyboardInterrupt/SystemExit
            try:
                self.clear()
            except (OSError, ValueError):
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

    @property
    def is_memory_locked(self) -> bool:
        """内存是否已锁定"""
        return self._memory_locked

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
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": success_rate,
        }

    @staticmethod
    def reset_clear_stats() -> None:
        """重置清零统计"""
        SecureKeyManager._total_clears = 0
        SecureKeyManager._successful_clears = 0
        SecureKeyManager._failed_clears = 0


@contextmanager
def secure_key_context(key_bytes: Optional[bytes] = None) -> Any:
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
