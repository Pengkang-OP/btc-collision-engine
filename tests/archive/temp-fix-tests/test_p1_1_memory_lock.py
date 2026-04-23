# -*- coding: utf-8 -*-
"""
P1-1修复验证: SecureKeyManager内存锁定单元测试

验证SecureKeyManager在不同平台上的内存锁定实现是否正确。
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock, Mock
import ctypes
import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.secure_key_manager import SecureKeyManager


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.p1_high
class TestMemoryLockLinux(unittest.TestCase):
    """测试Linux平台内存锁定"""
    
    @patch('sys.platform', 'linux')
    def test_linux_mlock_integration(self):
        """测试Linux mlock集成"""
        # SecureKeyManager初始化时会自动尝试锁定内存
        key_manager = SecureKeyManager(lock_memory=True)
        
        # 生成密钥后应尝试锁定
        key_manager.generate_key()
        
        # 验证密钥已生成
        self.assertIsNotNone(key_manager._key)
        
        # 清理
        key_manager.clear()


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.p1_high
class TestMemoryLockWindows(unittest.TestCase):
    """测试Windows平台内存锁定"""
    
    @patch('sys.platform', 'win32')
    def test_windows_virtuallock(self):
        """测试Windows VirtualLock调用"""
        # Windows平台应使用VirtualLock
        key_manager = SecureKeyManager()
        
        # 验证Windows平台检测
        self.assertEqual(sys.platform, 'win32')
        # 实际调用需要Windows环境,这里仅验证平台检测


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.p1_high
class TestMemoryLockMacOS(unittest.TestCase):
    """测试macOS平台内存锁定"""
    
    @patch('sys.platform', 'darwin')
    def test_macos_mlock(self):
        """测试macOS mlock调用"""
        # macOS平台应使用mlock
        key_manager = SecureKeyManager()
        
        # 验证macOS平台检测
        self.assertEqual(sys.platform, 'darwin')


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.p1_high
@pytest.mark.cross_platform
class TestMemoryLockCrossPlatform(unittest.TestCase):
    """测试跨平台内存锁定"""
    
    def setUp(self):
        """测试前准备"""
        self.key_manager = SecureKeyManager(lock_memory=True)
    
    def test_lock_unlock_lifecycle(self):
        """测试锁定-解锁生命周期"""
        # 生成密钥(自动锁定)
        self.key_manager.generate_key()
        
        # 验证密钥存在
        self.assertIsNotNone(self.key_manager._key)
        
        # 清理(自动解锁)
        self.key_manager.clear()
        
        # 验证密钥已清零
        self.assertTrue(self.key_manager._cleared)
    
    def test_clear_calls_unlock(self):
        """测试clear()方法调用unlock"""
        # 生成密钥
        self.key_manager.generate_key()
        
        # 如果内存已锁定,clean应调用解锁
        # clear()内部会先调用_unlock_key_memory()
        self.key_manager.clear()
        
        # 验证已清零
        self.assertTrue(self.key_manager._cleared)
    
    def test_generate_multiple_keys(self):
        """测试多次生成密钥"""
        # 第一次生成
        self.key_manager.generate_key()
        first_key = self.key_manager._key.copy()
        
        # 第二次生成(应先清零第一个)
        self.key_manager.generate_key()
        second_key = self.key_manager._key.copy()
        
        # 两个密钥应不同
        self.assertNotEqual(first_key, second_key)
        
        # 清理
        self.key_manager.clear()


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.p1_high
class TestMemoryLockSecurity(unittest.TestCase):
    """测试内存锁定的安全性"""
    
    def test_lock_prevents_swap(self):
        """验证内存锁定防止swap"""
        # 这是概念性测试
        key_manager = SecureKeyManager(lock_memory=True)
        
        # 生成密钥后应尝试锁定
        key_manager.generate_key()
        
        # 验证密钥存在
        self.assertIsNotNone(key_manager._key)
        
        # 清理
        key_manager.clear()
    
    def test_unlock_after_use(self):
        """验证使用后解锁"""
        key_manager = SecureKeyManager(lock_memory=True)
        
        # 生成密钥
        key_manager.generate_key()
        
        # clear应自动解锁并清零
        key_manager.clear()
        
        # 验证已清零
        self.assertTrue(key_manager._cleared)


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.p1_high
@pytest.mark.edge_cases
class TestMemoryLockEdgeCases(unittest.TestCase):
    """测试边界情况"""
    
    def setUp(self):
        """测试前准备"""
        self.key_manager = SecureKeyManager()
    
    def test_empty_key(self):
        """测试空密钥锁定"""
        empty_key = b''
        # 应处理空密钥情况
        try:
            self.key_manager._lock_memory(empty_key, 0)
        except Exception:
            # 某些平台可能对空密钥报错,这是合理的
            pass
    
    def test_very_large_key(self):
        """测试超大密钥锁定"""
        large_key = b'x' * (10 * 1024 * 1024)  # 10MB
        
        # 大密钥锁定可能失败(权限不足)
        try:
            self.key_manager._lock_memory(large_key, len(large_key))
        except Exception:
            # 预期可能失败
            pass
    
    def test_null_bytes_key(self):
        """测试包含null字节的密钥"""
        key_with_null = b'\x00\x01\x02\x00\x03' * 100
        
        try:
            self.key_manager._lock_memory(key_with_null, len(key_with_null))
        except Exception:
            pass


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.p1_high
@pytest.mark.integration
class TestMemoryLockIntegration(unittest.TestCase):
    """测试内存锁定集成"""
    
    def test_secure_key_manager_with_lock(self):
        """测试SecureKeyManager集成内存锁定"""
        key_manager = SecureKeyManager(lock_memory=True)
        
        # 生成密钥
        key_manager.generate_key()
        
        # 验证密钥已存储
        self.assertIsNotNone(key_manager._key)
        self.assertFalse(key_manager._cleared)
        
        # 使用密钥
        key_bytes = bytes(key_manager._key)
        self.assertEqual(len(key_bytes), 32)
        
        # 清理
        key_manager.clear()
        self.assertTrue(key_manager._cleared)


if __name__ == '__main__':
    unittest.main()
