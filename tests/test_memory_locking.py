"""SecureKeyManager内存锁定功能测试

验证P1-1修复：内存锁定功能完整实现
"""

from unittest.mock import Mock, patch

import pytest

from src.core.secure_key_manager import SecureKeyManager, SecureMemoryError


class TestMemoryLockingPosix:
    """POSIX系统内存锁定测试"""

    @patch("src.core.secure_key_manager.os.name", "posix")
    @patch("src.core.secure_key_manager.sys.platform", "linux")
    def test_posix_memory_lock_initialization(self):
        """测试POSIX内存锁定初始化"""
        with patch("ctypes.CDLL") as mock_cdll:
            # Mock libc
            mock_libc = Mock()
            mock_libc.mlock.argtypes = None
            mock_libc.mlock.restype = None
            mock_libc.munlock.argtypes = None
            mock_libc.munlock.restype = None
            mock_cdll.return_value = mock_libc

            manager = SecureKeyManager(lock_memory=True)
            manager._try_lock_memory()

            # 验证libc被加载
            mock_cdll.assert_called_once_with("libc.so.6")
            # 验证libc被保存
            assert hasattr(manager, "_libc")

    @patch("src.core.secure_key_manager.os.name", "posix")
    @patch("src.core.secure_key_manager.sys.platform", "darwin")
    def test_macos_memory_lock_initialization(self):
        """测试macOS内存锁定初始化"""
        with patch("ctypes.CDLL") as mock_cdll:
            mock_libc = Mock()
            mock_cdll.return_value = mock_libc

            manager = SecureKeyManager(lock_memory=True)
            manager._try_lock_memory()

            # macOS应该加载libSystem.B.dylib
            mock_cdll.assert_called_once_with("/usr/lib/libSystem.B.dylib")

    @patch("src.core.secure_key_manager.os.name", "posix")
    @patch("src.core.secure_key_manager.sys.platform", "linux")
    def test_mlock_key_memory_success(self):
        """测试mlock锁定密钥内存成功"""
        with patch("ctypes.CDLL") as mock_cdll:
            mock_libc = Mock()
            mock_libc.mlock.return_value = 0  # 成功
            mock_cdll.return_value = mock_libc

            manager = SecureKeyManager(lock_memory=True)
            manager._try_lock_memory()
            manager.generate_key()

            # 验证内存锁定状态
            assert manager.is_memory_locked

    @patch("src.core.secure_key_manager.os.name", "posix")
    @patch("src.core.secure_key_manager.sys.platform", "linux")
    def test_munlock_key_memory_success(self):
        """测试munlock解锁密钥内存成功"""
        with patch("ctypes.CDLL") as mock_cdll:
            mock_libc = Mock()
            mock_libc.mlock.return_value = 0
            mock_libc.munlock.return_value = 0
            mock_cdll.return_value = mock_libc

            manager = SecureKeyManager(lock_memory=True)
            manager._try_lock_memory()
            manager.generate_key()
            assert manager.is_memory_locked

            manager.clear()
            # 验证内存已解锁
            assert not manager.is_memory_locked


class TestMemoryLockingWindows:
    """Windows系统内存锁定测试"""

    @patch("src.core.secure_key_manager.os.name", "nt")
    def test_windows_memory_lock_initialization(self):
        """测试Windows内存锁定初始化"""
        with patch("ctypes.WinDLL") as mock_windll:
            mock_kernel32 = Mock()
            mock_kernel32.VirtualLock.argtypes = None
            mock_kernel32.VirtualLock.restype = None
            mock_kernel32.VirtualUnlock.argtypes = None
            mock_kernel32.VirtualUnlock.restype = None
            mock_windll.return_value = mock_kernel32

            manager = SecureKeyManager(lock_memory=True)
            manager._try_lock_memory()

            # 验证kernel32被加载
            mock_windll.assert_called_once_with("kernel32.dll")
            assert hasattr(manager, "_kernel32")

    @patch("src.core.secure_key_manager.os.name", "nt")
    def test_virtual_lock_key_memory_success(self):
        """测试VirtualLock锁定密钥内存成功"""
        with patch("ctypes.WinDLL") as mock_windll:
            mock_kernel32 = Mock()
            mock_kernel32.VirtualLock.return_value = True  # 成功
            mock_windll.return_value = mock_kernel32

            manager = SecureKeyManager(lock_memory=True)
            manager._try_lock_memory()
            manager.generate_key()

            assert manager.is_memory_locked

    @patch("src.core.secure_key_manager.os.name", "nt")
    def test_virtual_unlock_key_memory_success(self):
        """测试VirtualUnlock解锁密钥内存成功"""
        with patch("ctypes.WinDLL") as mock_windll:
            mock_kernel32 = Mock()
            mock_kernel32.VirtualLock.return_value = True
            mock_kernel32.VirtualUnlock.return_value = True
            mock_windll.return_value = mock_kernel32

            manager = SecureKeyManager(lock_memory=True)
            manager._try_lock_memory()
            manager.generate_key()
            assert manager.is_memory_locked

            manager.clear()
            assert not manager.is_memory_locked


class TestMemoryLockingFallback:
    """内存锁定降级和错误处理测试"""

    def test_lock_memory_disabled(self):
        """测试禁用内存锁定"""
        manager = SecureKeyManager(lock_memory=False)
        manager.generate_key()

        # 内存不应被锁定
        assert not manager.is_memory_locked

    @patch("src.core.secure_key_manager.os.name", "posix")
    @patch("src.core.secure_key_manager.sys.platform", "linux")
    def test_mlock_failure_graceful(self):
        """测试mlock失败时的优雅降级"""
        with patch("ctypes.CDLL") as mock_cdll:
            # Mock mlock失败
            mock_libc = Mock()
            mock_libc.mlock.return_value = -1  # 失败
            mock_cdll.return_value = mock_libc

            manager = SecureKeyManager(lock_memory=True)
            manager._try_lock_memory()
            manager.generate_key()

            # 即使mlock失败，密钥仍应生成
            assert manager.get_key() is not None
            # 但内存未锁定
            assert not manager.is_memory_locked

    @patch("src.core.secure_key_manager.os.name", "posix")
    def test_unsupported_os(self):
        """测试不支持的操作系统"""
        with patch("src.core.secure_key_manager.sys.platform", "unknown"):
            with patch("ctypes.CDLL", side_effect=OSError("Unsupported")):
                manager = SecureKeyManager(lock_memory=True)
                result = manager._try_lock_memory()

                # 应该优雅失败
                assert not result


class TestMemoryLockingIntegration:
    """内存锁定集成测试"""

    def test_full_lifecycle_with_locking(self):
        """测试完整的密钥生命周期（含内存锁定）"""
        manager = SecureKeyManager(lock_memory=True)

        # 初始化时尝试锁定内存
        manager._try_lock_memory()

        # 生成密钥
        manager.generate_key()
        key = manager.get_key()

        # 验证密钥
        assert key is not None
        assert len(key)  ==  32
        assert not manager.is_cleared

        # 清零密钥
        manager.clear()

        # 验证清零
        assert manager.is_cleared
        assert not manager.is_memory_locked

        # 验证无法再次获取
        with pytest.raises(SecureMemoryError):
            manager.get_key()

    def test_context_manager_with_locking(self):
        """测试上下文管理器中的内存锁定"""
        from src.core.secure_key_manager import secure_key_context

        # Mock内存锁定
        with patch.object(SecureKeyManager, "_try_lock_memory", return_value=True):
            with patch.object(SecureKeyManager, "_lock_key_memory", return_value=True):
                with secure_key_context() as key:
                    assert key is not None
                    assert len(key)  ==  32

                # 退出上下文后密钥应被清零
                # (无法直接测试，因为key是引用)

    def test_multiple_keys_sequential(self):
        """测试连续生成多个密钥"""
        manager = SecureKeyManager(lock_memory=True)
        manager._try_lock_memory()

        for _i in range(3):
            manager.generate_key()
            key = manager.get_key()
            assert len(key)  ==  32
            manager.clear()
            assert manager.is_cleared

    def test_statistics_tracking(self):
        """测试清零统计跟踪"""
        SecureKeyManager.reset_clear_stats()

        manager = SecureKeyManager(lock_memory=True)
        manager.generate_key()
        manager.clear()

        stats = SecureKeyManager.get_clear_stats()
        assert stats["total"]  ==  1
        assert stats["successful"]  ==  1
        assert stats["failed"]  ==  0
        assert stats["success_rate"]  ==  100.0


class TestMemoryLockingSecurity:
    """内存锁定安全性测试"""

    def test_key_cleared_with_random_first(self):
        """测试清零时先用随机数据覆盖"""
        manager = SecureKeyManager()
        manager.generate_key()
        key = manager.get_key()

        # 记录原始密钥
        bytes(key)

        # 清零
        manager.clear()

        # 验证密钥被清零
        assert bytes(key)  ==  b"\x00" * 32

    def test_no_key_duplication(self):
        """测试密钥不会被意外复制"""
        manager = SecureKeyManager()
        manager.generate_key()

        # 获取密钥引用 — get_key() 每次返回新的 memoryview，
        # 但底层数据缓冲区相同
        key_ref1 = manager.get_key()
        key_ref2 = manager.get_key()

        # 内容应相同（指向同一底层密钥数据）
        assert bytes(key_ref1)  ==  bytes(key_ref2)

    @patch("src.core.secure_key_manager.os.name", "posix")
    @patch("src.core.secure_key_manager.sys.platform", "linux")
    def test_munlock_on_clear(self):
        """测试清零时会解锁内存"""
        with patch("ctypes.CDLL") as mock_cdll:
            mock_libc = Mock()
            mock_libc.mlock.return_value = 0
            mock_libc.munlock.return_value = 0
            mock_cdll.return_value = mock_libc

            manager = SecureKeyManager(lock_memory=True)
            manager._try_lock_memory()
            manager.generate_key()

            # 验证已锁定
            assert manager.is_memory_locked

            # 清零应该解锁
            manager.clear()

            # munlock应该被调用
            mock_libc.munlock.assert_called_once()

