# -*- coding: utf-8 -*-
"""address_generator.py 边界与错误路径覆盖测试

覆盖缺失行: 61-76, 165-191, 236-250, 272-275
"""

import unittest
from unittest.mock import patch, MagicMock, PropertyMock

from src.core.address_generator import (
    secure_clear_bytearray,
    P2PKHAddressGenerator,
    PerformanceWarning,
)


# ===========================================================================
# Group A: secure_clear_bytearray (lines 61-76)
# ===========================================================================


class TestSecureClearBytearray(unittest.TestCase):
    """secure_clear_bytearray 边界测试"""

    def test_non_bytearray_raises_typeerror(self):
        """传入 bytes 触发 TypeError → lines 61-65"""
        with self.assertRaises(TypeError) as ctx:
            secure_clear_bytearray(b"\x00" * 32)
        self.assertIn("bytearray", str(ctx.exception))

    def test_non_bytearray_list_raises_typeerror(self):
        """传入 list 触发 TypeError"""
        with self.assertRaises(TypeError):
            secure_clear_bytearray([0] * 32)

    def test_successful_clear(self):
        """成功清零 bytearray → lines 67-69"""
        buf = bytearray(b"\xff" * 32)
        secure_clear_bytearray(buf)
        # 所有字节应被清零
        self.assertEqual(buf, bytearray(b"\x00" * 32))

    def test_exception_handler(self):
        """ctypes.memset 异常处理 → lines 70-76"""
        buf = bytearray(b"\xff" * 32)
        with patch("ctypes.memset", side_effect=OSError("模拟异常")):
            # 不应抛出异常（静默失败）
            secure_clear_bytearray(buf)
            # buf 未被清零
            self.assertNotEqual(buf, bytearray(b"\x00" * 32))


# ===========================================================================
# Group B: generate_private_key 异常处理 (lines 165-191)
# ===========================================================================


class TestGeneratePrivateKeyEdge(unittest.TestCase):
    """generate_private_key 异常处理与重试耗尽"""

    def setUp(self):
        self.gen = P2PKHAddressGenerator()

    def test_generate_private_key_max_retries_exceeded(self):
        """重试耗尽抛出 KeyGenerationError → line 191"""
        with patch("secrets.token_bytes", return_value=b"\x00" * 32):
            # 零私钥始终无效, 耗尽 max_retries
            with self.assertRaises(Exception) as ctx:
                self.gen.generate_private_key(max_retries=3)
            self.assertIn("无法在 3 次", str(ctx.exception))

    def test_generate_private_key_valueerror_handler(self):
        """secrets.token_bytes 抛 ValueError → lines 173-179"""
        with patch("secrets.token_bytes", side_effect=ValueError("模拟")):
            with self.assertRaises(Exception):
                self.gen.generate_private_key(max_retries=2)

    def test_generate_private_key_keygenerror_handler(self):
        """secrets.token_bytes 抛 KeyGenerationError → lines 166-172"""
        from src.utils.exceptions import KeyGenerationError
        with patch(
            "secrets.token_bytes",
            side_effect=KeyGenerationError("模拟", error_code=999),
        ):
            with self.assertRaises(Exception):
                self.gen.generate_private_key(max_retries=2)

    def test_generate_private_key_other_exception_handler(self):
        """secrets.token_bytes 抛其他异常 → lines 180-188"""
        with patch("secrets.token_bytes", side_effect=RuntimeError("未知错误")):
            with self.assertRaises(Exception):
                self.gen.generate_private_key(max_retries=2)


# ===========================================================================
# Group C: _check_crypto_backend_performance (lines 236-250)
# ===========================================================================


class TestCryptoBackendPerformance(unittest.TestCase):
    """_check_crypto_backend_performance 路径"""

    def test_pure_python_backend_warns(self):
        """PURE_PYTHON 后端触发性能警告 → lines 236-246"""
        mock_manager = MagicMock()
        mock_backend = MagicMock()
        mock_backend.name = "PURE_PYTHON"
        type(mock_manager).current_backend = PropertyMock(
            return_value=mock_backend
        )
        with patch.dict(
            "sys.modules",
            {"src.core.crypto_backend": MagicMock(crypto_manager=mock_manager)},
        ):
            # 导入已存在，P2PKHAddressGenerator 会使用 crypto_manager
            with self.assertWarns(PerformanceWarning):
                P2PKHAddressGenerator()

    def test_import_error_silent(self):
        """导入 crypto_backend 失败时静默处理 → line 250"""
        # 在 crypto_backend 导入前, 让 _check_crypto_backend_performance
        # 中的 import 失败
        def mock_import(name, *args, **kwargs):
            if "crypto_backend" in name:
                raise ImportError("模拟导入失败")
            return __import__(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            # 不应抛出异常
            gen = P2PKHAddressGenerator()
            self.assertIsNotNone(gen)


# ===========================================================================
# Group D: private_key_to_public_key fallback (lines 272-275)
# ===========================================================================


class TestPubKeyFallback(unittest.TestCase):
    """private_key_to_public_key 纯 Python 回退"""

    def test_fallback_to_pure_python(self):
        """导入 crypto_manager 失败时回退到纯 Python → lines 272-275"""
        gen = P2PKHAddressGenerator()

        # Mock crypto_manager import 失败
        def mock_import(name, *args, **kwargs):
            if "crypto_backend" in name or "crypto_manager" in str(args):
                raise ImportError("模拟")
            return __import__(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            pk = gen.private_key_to_public_key(b"\x01" * 32, compressed=True)
            self.assertEqual(len(pk), 33)


if __name__ == "__main__":
    unittest.main(verbosity=2)
