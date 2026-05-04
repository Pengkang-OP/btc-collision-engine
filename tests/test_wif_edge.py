# -*- coding: utf-8 -*-
"""WIF (Wallet Import Format) 边界与错误路径覆盖测试

覆盖缺失行: 42, 59-63, 81, 88, 96, 100-104
"""

import unittest
from unittest.mock import patch

from src.core.wif import WIF


class TestWIFEncodeEdge(unittest.TestCase):
    """WIF.encode 边界路径"""

    def test_encode_non_bytes_input(self):
        """encode 非 bytes 输入 → line 42"""
        with self.assertRaises(ValueError) as ctx:
            WIF.encode("not_bytes", compressed=True)
        self.assertIn("字节串", str(ctx.exception))

    def test_encode_invalid_key_length(self):
        """encode 私钥长度不是 32 → line 44"""
        with self.assertRaises(ValueError) as ctx:
            WIF.encode(b"\x01" * 31, compressed=True)
        self.assertIn("32字节", str(ctx.exception))

    def test_encode_uncompressed(self):
        """encode compressed=False → line 51"""
        wif = WIF.encode(b"\x01" * 32, compressed=False)
        self.assertIsInstance(wif, str)
        self.assertTrue(wif.startswith("5"))

    def test_encode_non_valueerror_exception_handler(self):
        """encode 非 ValueError 异常捕获 → lines 59-63"""
        with patch("src.core.wif.Base58.check_encode",
                   side_effect=TypeError("模拟Base58内部错误")):
            with self.assertRaises(ValueError) as ctx:
                WIF.encode(b"\x01" * 32, compressed=True)
            self.assertIn("WIF编码失败", str(ctx.exception))


class TestWIFDecodeEdge(unittest.TestCase):
    """WIF.decode 边界路径"""

    def test_decode_non_string_input(self):
        """decode 非 str 输入 → line 81"""
        with self.assertRaises(ValueError) as ctx:
            WIF.decode(12345)
        self.assertIn("字符串", str(ctx.exception))

    @patch("src.core.wif.Base58.check_decode")
    def test_decode_invalid_version_byte(self, mock_check_decode):
        """decode 版本字节不是 0x80 → line 88"""
        mock_check_decode.return_value = (0x55, b"\x01" * 32)
        with self.assertRaises(ValueError) as ctx:
            WIF.decode("5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ")
        self.assertIn("版本", str(ctx.exception))

    @patch("src.core.wif.Base58.check_decode")
    def test_decode_compressed(self, mock_check_decode):
        """decode 压缩格式 (33字节, 末尾0x01) → line 92"""
        mock_check_decode.return_value = (0x80, b"\x01" * 32 + b"\x01")
        pk, compressed = WIF.decode("fake_wif")
        self.assertEqual(pk, b"\x01" * 32)
        self.assertTrue(compressed)

    @patch("src.core.wif.Base58.check_decode")
    def test_decode_uncompressed(self, mock_check_decode):
        """decode 非压缩格式 (32字节) → line 94"""
        mock_check_decode.return_value = (0x80, b"\x01" * 32)
        pk, compressed = WIF.decode("fake_wif")
        self.assertEqual(pk, b"\x01" * 32)
        self.assertFalse(compressed)

    @patch("src.core.wif.Base58.check_decode")
    def test_decode_invalid_payload_length(self, mock_check_decode):
        """decode 载荷长度不是 32/33 → line 96"""
        # 版本正确但数据长度异常 (不是32也不是33)
        mock_check_decode.return_value = (0x80, b"\x01" * 31)
        with self.assertRaises(ValueError) as ctx:
            WIF.decode("5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ")
        self.assertIn("长度", str(ctx.exception))

    @patch("src.core.wif.Base58.check_decode")
    def test_decode_non_valueerror_exception_handler(self, mock_check_decode):
        """decode 非 ValueError 异常捕获 → lines 100-104"""
        mock_check_decode.side_effect = TypeError("模拟Base58内部错误")
        with self.assertRaises(ValueError) as ctx:
            WIF.decode("5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ")
        self.assertIn("WIF格式无效", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
