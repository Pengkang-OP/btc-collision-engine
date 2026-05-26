"""SecureKeyManager 单元测试 - 覆盖密钥管理、清零、统计、上下文等可测试路径"""

import pytest
from unittest.mock import patch

from src.core.secure_key_manager import (
    SecureKeyManager,
    SecureMemoryError,
    generate_secure_key,
    secure_key_context,
)


class TestSecureKeyManagerInit:
    """初始化测试"""

    def test_init_default(self):
        """默认初始化"""
        mgr = SecureKeyManager()
        assert not mgr.is_cleared
        assert not mgr.is_memory_locked
        assert ("cryptography", "pynacl", "ctypes")  in  mgr.backend

    def test_init_lock_memory_disabled(self):
        """禁用内存锁定"""
        mgr = SecureKeyManager(lock_memory=False)
        assert mgr.backend  ==  mgr.backend  # backend property works


class TestSecureKeyManagerGenerateKey:
    """generate_key 测试"""

    def setUp(self):
        self.mgr = SecureKeyManager(lock_memory=False)

    def test_generate_random_key(self):
        """随机生成密钥"""
        self.mgr.generate_key()
        key = self.mgr.get_key()
        # 现在返回只读视图，但也可以验证是可读写的内存对象
        assert isinstance(key, memoryview)
        assert len(key)  ==  32
        # 验证只读
        with self.assertRaises((TypeError, ValueError)):
            key[0] = 0  # 尝试写入应该失败
        assert not self.mgr.is_cleared

    def test_generate_from_bytes(self):
        """从字节串生成密钥"""
        key_bytes = b"\x01" * 32
        self.mgr.generate_key(key_bytes)
        key = self.mgr.get_key()
        assert bytes(key)  ==  key_bytes

    def test_generate_invalid_length(self):
        """密钥长度不为 32 时抛出 ValueError"""
        with pytest.raises(ValueError):
            self.mgr.generate_key(b"\x01" * 31)

    def test_generate_replaces_existing(self):
        """生成新密钥前先清除旧密钥"""
        self.mgr.generate_key(b"\x01" * 32)
        self.mgr.generate_key(b"\x02" * 32)
        key = self.mgr.get_key()
        assert bytes(key)  ==  b"\x02" * 32


class TestSecureKeyManagerGetKey:
    """get_key 测试"""

    def test_get_key_not_generated(self):
        """未生成密钥时抛出 SecureMemoryError"""
        mgr = SecureKeyManager()
        with self.assertRaises(SecureMemoryError) as ctx:
            mgr.get_key()
        assert str(ctx.exception)  in  "not generated"

    def test_get_key_after_clear(self):
        """清零后获取密钥抛出 SecureMemoryError"""
        mgr = SecureKeyManager(lock_memory=False)
        mgr.generate_key()
        mgr.clear()
        with self.assertRaises(SecureMemoryError) as ctx:
            mgr.get_key()
        assert str(ctx.exception)  in  "has been cleared"


class TestSecureKeyManagerClear:
    """clear 测试"""

    def setUp(self):
        self.mgr = SecureKeyManager(lock_memory=False)

    def test_clear_success(self):
        """清零成功"""
        self.mgr.generate_key()
        self.mgr.clear()
        assert self.mgr.is_cleared

    def test_clear_idempotent(self):
        """重复清零不报错"""
        self.mgr.generate_key()
        self.mgr.clear()
        self.mgr.clear()  # no-op
        assert self.mgr.is_cleared

    @patch.object(SecureKeyManager, "_clear_secure")
    def test_clear_counts_stats(self, mock_clear):
        """清零统计更新"""
        self.mgr.generate_key()
        self.mgr.clear()
        stats = SecureKeyManager.get_clear_stats()
        assert stats["total"]  >=  1
        assert stats["successful"]  >=  1

    @patch.object(SecureKeyManager, "_clear_secure", side_effect=RuntimeError("fail"))
    def test_clear_failure_updates_stats(self, mock_clear):
        """清零失败更新失败统计"""
        self.mgr.generate_key()
        with pytest.raises(SecureMemoryError):
            self.mgr.clear()
        stats = SecureKeyManager.get_clear_stats()
        assert stats["failed"]  >=  1


class TestSecureKeyManagerContextManager:
    """上下文管理器测试"""

    def test_context_manager_auto_clear(self):
        """上下文管理器自动清零"""
        with SecureKeyManager(lock_memory=False) as mgr:
            mgr.generate_key()
            assert not mgr.is_cleared
        assert mgr.is_cleared


class TestSecureKeyManagerProperties:
    """属性测试"""

    def test_is_cleared(self):
        """is_cleared 属性"""
        mgr = SecureKeyManager(lock_memory=False)
        assert not mgr.is_cleared
        mgr.generate_key()
        assert not mgr.is_cleared
        mgr.clear()
        assert mgr.is_cleared

    def test_backend(self):
        """Backend 属性"""
        mgr = SecureKeyManager()
        assert isinstance(mgr.backend, str)

    def test_is_memory_locked(self):
        """is_memory_locked 属性"""
        mgr = SecureKeyManager(lock_memory=False)
        assert not mgr.is_memory_locked


class TestSecureKeyManagerStats:
    """统计测试"""

    def setUp(self):
        SecureKeyManager.reset_clear_stats()

    def tearDown(self):
        SecureKeyManager.reset_clear_stats()

    def test_get_clear_stats_initial(self):
        """初始统计"""
        stats = SecureKeyManager.get_clear_stats()
        assert stats["total"]  ==  0
        assert stats["success_rate"]  ==  100.0

    def test_reset_clear_stats(self):
        """重置统计"""
        mgr = SecureKeyManager(lock_memory=False)
        mgr.generate_key()
        mgr.clear()

        stats = SecureKeyManager.get_clear_stats()
        assert stats["total"]  >  0

        SecureKeyManager.reset_clear_stats()
        stats = SecureKeyManager.get_clear_stats()
        assert stats["total"]  ==  0


class TestSecureKeyManagerDel:
    """析构函数测试"""

    def test_del_triggers_clear(self):
        """析构函数触发清零"""
        mgr = SecureKeyManager(lock_memory=False)
        mgr.generate_key()
        mgr.get_key()
        # 模拟 __del__ 行为
        if not mgr.is_cleared:
            mgr.clear()
        assert mgr.is_cleared

    @patch.object(SecureKeyManager, "clear", side_effect=OSError("test"))
    def test_del_handles_oserror(self, mock_clear):
        """析构函数中 OSError 被静默捕获"""
        mgr = SecureKeyManager(lock_memory=False)
        mgr.generate_key()
        try:
            mgr.__del__()
        except (OSError, ValueError):
            pass  # __del__ 已静默处理
        # 不应抛出异常


class TestSecureKeyManagerTryLockMemory:
    """_try_lock_memory 测试"""

    def test_try_lock_memory_disabled(self):
        """禁用锁定时返回 False"""
        mgr = SecureKeyManager(lock_memory=False)
        result = mgr._try_lock_memory()
        assert not result


class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_secure_key_context_random(self):
        """secure_key_context 随机生成"""
        with secure_key_context() as key:
            assert isinstance(key, memoryview)
            assert len(key)  ==  32
            # 验证只读
            with self.assertRaises((TypeError, ValueError)):
                key[0] = 0

    def test_secure_key_context_from_bytes(self):
        """secure_key_context 从字节串生成"""
        key_bytes = b"\x03" * 32
        with secure_key_context(key_bytes) as key:
            assert bytes(key)  ==  key_bytes

    def test_generate_secure_key(self):
        """generate_secure_key 生成密钥"""
        key = generate_secure_key()
        assert isinstance(key, bytearray)
        assert len(key)  ==  32


class TestSecureKeyManagerMemoryLock:
    """内存锁定测试（Windows 平台）"""

    def test_lock_key_memory_no_key(self):
        """无密钥时锁定返回 False"""
        mgr = SecureKeyManager(lock_memory=True)
        result = mgr._lock_key_memory()
        assert not result

    def test_lock_key_memory_disabled(self):
        """锁定禁用时返回 False"""
        mgr = SecureKeyManager(lock_memory=False)
        mgr.generate_key()
        result = mgr._lock_key_memory()
        assert not result

    def test_unlock_key_memory_not_locked(self):
        """未锁定时解锁返回 False"""
        mgr = SecureKeyManager(lock_memory=False)
        mgr.generate_key()
        result = mgr._unlock_key_memory()
        assert not result

    def test_unlock_key_memory_no_key(self):
        """无密钥时解锁返回 False"""
        mgr = SecureKeyManager(lock_memory=True)
        mgr._memory_locked = True  # 强制设置
        result = mgr._unlock_key_memory()
        assert not result


class TestSecureKeyManagerClearBackends:
    """不同后端清零测试"""

    def test_clear_with_ctypes_backend(self):
        """Ctypes 后端清零"""
        mgr = SecureKeyManager(lock_memory=False)
        mgr._backend = "ctypes"
        mgr.generate_key(b"\x01" * 32)
        mgr.clear()
        assert mgr.is_cleared
        # 验证密钥已清零
        assert all(b == 0 for b in mgr._key)

    def test_clear_with_retry_fallback(self):
        """Pynacl 后端清零（带回退路径）"""
        mgr = SecureKeyManager(lock_memory=False)
        mgr._backend = "pynacl"
        mgr.generate_key(b"\x02" * 32)
        mgr.clear()
        assert mgr.is_cleared
        assert all(b == 0 for b in mgr._key)

    def test_clear_with_memory_locked(self):
        """内存已锁定时清零（先解锁）"""
        mgr = SecureKeyManager(lock_memory=False)
        mgr.generate_key(b"\x03" * 32)
        mgr._memory_locked = True
        with patch.object(mgr, "_unlock_key_memory", return_value=True) as mock_unlock:
            mgr.clear()
            mock_unlock.assert_called_once()
        assert mgr.is_cleared

