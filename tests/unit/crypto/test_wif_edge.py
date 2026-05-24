"""WIF (Wallet Import Format) 边界与错误路径覆盖测试"""
import unittest
from unittest.mock import patch
import pytest

from src.core.wif import WIF


class TestWIFEncodeEdge(unittest.TestCase):
    """WIF.encode 边界路径"""

    def test_encode_non_bytes_input(self):
        """Encode 非 bytes 输入"""
        with self.assertRaises(ValueError) as ctx:
            WIF.encode("not_bytes", compressed=True)
        self.assertIn("bytes", str(ctx.exception))

    def test_encode_invalid_key_length(self):
        """Encode 私钥长度不是 32"""
        with self.assertRaises(ValueError) as ctx:
            WIF.encode(b"\x01" * 31, compressed=True)
        self.assertIn("32 bytes", str(ctx.exception))

    def test_encode_uncompressed(self):
        """Encode compressed=False"""
        wif = WIF.encode(b"\x01" * 32, compressed=False)
        self.assertIsInstance(wif, str)
        self.assertTrue(wif.startswith("5"))

    def test_encode_non_valueerror_exception_handler(self):
        """Encode 非 ValueError 异常直接传播 — Base58.encode raises TypeError"""
        with patch("src.core.wif.Base58.encode", side_effect=TypeError("模拟Base58内部错误")):
            with self.assertRaises(TypeError) as ctx:
                WIF.encode(b"\x01" * 32, compressed=True)
            self.assertIn("模拟Base58内部错误", str(ctx.exception))


class TestWIFDecodeEdge(unittest.TestCase):
    """WIF.decode 边界路径"""

    def test_decode_non_string_input(self):
        """Decode 非 str 输入"""
        with self.assertRaises(ValueError) as ctx:
            WIF.decode(12345)
        self.assertIn("string", str(ctx.exception))

    @patch("src.core.wif.Base58.decode")
    def test_decode_invalid_version_byte(self, mock_decode):
        """Decode 版本字节不是 0x80"""
        mock_decode.return_value = b"\x55" + b"\x01" * 32 + b"\x01\x02\x03\x04"
        with self.assertRaises(ValueError) as ctx:
            WIF.decode("5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ")
        self.assertIn("version", str(ctx.exception))

    @patch("src.core.wif.Base58.decode")
    def test_decode_compressed(self, mock_decode):
        """Decode 压缩格式 (33字节key, 末尾0x01)"""
        # payload: version(0x80) + key(32) + 0x01 = 34 bytes + checksum(4) = 38
        payload = bytes([0x80]) + b"\x01" * 32 + bytes([0x01])
        from src.core.hash_utils import HashUtils
        checksum = HashUtils.double_sha256(payload)[:4]
        mock_decode.return_value = payload + checksum
        pk, compressed = WIF.decode("fake_wif")
        self.assertEqual(pk, b"\x01" * 32)
        self.assertTrue(compressed)

    @patch("src.core.wif.Base58.decode")
    def test_decode_uncompressed(self, mock_decode):
        """Decode 非压缩格式 (32字节key)"""
        # payload: version(0x80) + key(32) = 33 bytes + checksum(4) = 37
        payload = bytes([0x80]) + b"\x01" * 32
        from src.core.hash_utils import HashUtils
        checksum = HashUtils.double_sha256(payload)[:4]
        mock_decode.return_value = payload + checksum
        pk, compressed = WIF.decode("fake_wif")
        self.assertEqual(pk, b"\x01" * 32)
        self.assertFalse(compressed)

    @patch("src.core.wif.Base58.decode")
    def test_decode_invalid_payload_length(self, mock_decode):
        """Decode 载荷长度不是 32/33"""
        # payload with 34 bytes of key (not 32/33); total >= 37 to pass min-length check
        payload = bytes([0x80]) + b"\x01" * 34
        from src.core.hash_utils import HashUtils
        checksum = HashUtils.double_sha256(payload)[:4]
        mock_decode.return_value = payload + checksum
        with self.assertRaises(ValueError) as ctx:
            WIF.decode("5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ")
        self.assertIn("Invalid WIF payload length", str(ctx.exception))

    @patch("src.core.wif.Base58.decode")
    def test_decode_non_valueerror_exception_handler(self, mock_decode):
        """Decode 非 ValueError 异常直接传播"""
        mock_decode.side_effect = TypeError("模拟Base58内部错误")
        with self.assertRaises(TypeError) as ctx:
            WIF.decode("5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ")
        self.assertIn("模拟Base58内部错误", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
