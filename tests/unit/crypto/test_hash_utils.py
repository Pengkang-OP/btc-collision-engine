"""HashUtils 全面测试"""

import hashlib
import unittest

from src.core.hash_utils import HashUtils


class TestHashUtilsSha256(unittest.TestCase):
    """sha256 测试"""

    def test_sha256_known_vector(self):
        """已知向量验证"""
        result = HashUtils.sha256(b"hello")
        expected = hashlib.sha256(b"hello").digest()
        self.assertEqual(result, expected)
        self.assertEqual(len(result), 32)

    def test_sha256_empty(self):
        """空输入"""
        result = HashUtils.sha256(b"")
        self.assertEqual(len(result), 32)


class TestHashUtilsRipemd160(unittest.TestCase):
    """ripemd160 测试"""

    def test_ripemd160_known_vector(self):
        """已知向量验证"""
        result = HashUtils.ripemd160(b"test")
        expected = hashlib.new("ripemd160", b"test").digest()
        self.assertEqual(result, expected)
        self.assertEqual(len(result), 20)

    def test_ripemd160_empty(self):
        """空输入"""
        result = HashUtils.ripemd160(b"")
        self.assertEqual(len(result), 20)


class TestHashUtilsHash160(unittest.TestCase):
    """hash160 / double_sha256 测试"""

    def test_hash160_known(self):
        """hash160 = ripemd160(sha256(data))"""
        result = HashUtils.hash160(b"data")
        expected = hashlib.new("ripemd160", hashlib.sha256(b"data").digest()).digest()
        self.assertEqual(result, expected)
        self.assertEqual(len(result), 20)

    def test_double_sha256_known(self):
        """double_sha256 = sha256(sha256(data))"""
        result = HashUtils.double_sha256(b"block")
        expected = hashlib.sha256(hashlib.sha256(b"block").digest()).digest()
        self.assertEqual(result, expected)
        self.assertEqual(len(result), 32)


# AddressHashCalculator 模块已移除 — 相关测试已删除


if __name__ == "__main__":
    unittest.main()
