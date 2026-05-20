"""SIMDHash 无 pycryptodome 回退路径覆盖测试"""

import sys
import unittest
from unittest.mock import patch

from src.core.simd_hash import SIMDHashOptimizer


class TestSIMDHashNoPycryptodome(unittest.TestCase):
    """模拟 pycryptodome 不可用时, 测试 hashlib 回退路径"""

    @staticmethod
    def _selective_import_fail(name, *args, **kwargs):
        if name.startswith("Crypto"):
            raise ImportError("No module named 'Crypto'")
        return __import__(name, *args, **kwargs)

    def _create_optimizer_no_crypto(self):
        """在 pycryptodome 不可用环境中创建 SIMDHashOptimizer"""
        # 移除 Crypto 相关模块缓存
        saved_modules = {}
        for key in list(sys.modules.keys()):
            if key.startswith("Crypto"):
                saved_modules[key] = sys.modules.pop(key)

        try:
            with patch("builtins.__import__",
                       side_effect=self._selective_import_fail), patch("src.core.simd_hash.logger"):
                optimizer = SIMDHashOptimizer()
        finally:
            sys.modules.update(saved_modules)
        return optimizer

    def test_init_no_pycryptodome(self):
        """pycryptodome 不可用时初始化 (cover lines 77-78)"""
        optimizer = self._create_optimizer_no_crypto()
        self.assertFalse(optimizer.use_pycryptodome)
        self.assertIsNone(optimizer.SHA256)
        self.assertIsNone(optimizer.RIPEMD160)

    def test_batch_sha256_fallback(self):
        """无 pycryptodome 时 batch_sha256 回退到 hashlib (cover line 97)"""
        optimizer = self._create_optimizer_no_crypto()
        results = optimizer.batch_sha256([b"hello", b"world"])
        self.assertEqual(len(results), 2)
        self.assertEqual(len(results[0]), 32)  # SHA256 → 32 bytes

    def test_batch_ripemd160_fallback(self):
        """无 pycryptodome 时 batch_ripemd160 回退到 hashlib (cover line 114)"""
        optimizer = self._create_optimizer_no_crypto()
        results = optimizer.batch_ripemd160([b"hello", b"world"])
        self.assertEqual(len(results), 2)
        self.assertEqual(len(results[0]), 20)  # RIPEMD160 → 20 bytes

    def test_batch_hash160_fallback(self):
        """无 pycryptodome 时 batch_hash160 回退"""
        optimizer = self._create_optimizer_no_crypto()
        results = optimizer.batch_hash160([b"hello", b"world"])
        self.assertEqual(len(results), 2)
        self.assertEqual(len(results[0]), 20)  # Hash160 → 20 bytes

    def test_is_optimized_no_crypto(self):
        """无 pycryptodome 时 is_optimized 返回 False"""
        optimizer = self._create_optimizer_no_crypto()
        self.assertFalse(optimizer.is_optimized())

    def test_get_backend_name_no_crypto(self):
        """无 pycryptodome 时 backend name"""
        optimizer = self._create_optimizer_no_crypto()
        self.assertEqual(optimizer.get_backend_name(), "hashlib")


if __name__ == "__main__":
    unittest.main()
