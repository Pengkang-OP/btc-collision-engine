#!/usr/bin/env python3
"""数据转换模块综合测试

覆盖范围:
- EncodingUtils: 文件编码检测和转换
- Base58: Base58/Base58Check 编解码
- WIF: 钱包导入格式编解码
- AddressConverter: 私钥到地址的完整转换
"""

import pathlib
import tempfile
import unittest

from src.core.base58 import Base58
from src.core.wif import WIF
from src.utils.encoding_utils import EncodingUtils

# ---------------------------------------------------------------------------
# 测试数据常量
# ---------------------------------------------------------------------------

# 测试私钥 (来自 Bitcoin Core 官方测试向量)
_TEST_PRIVATE_KEY_HEX = "0c28fca386c7a227600b2fe50b7cae11ec86d3bf1fbe471be89827e19d72aa1d"
_TEST_PRIVATE_KEY = bytes.fromhex(_TEST_PRIVATE_KEY_HEX)

# 预期结果（通过实际计算得出）
_EXPECTED_WIF_COMPRESSED = "KwdMAjGmerYanjeui5SHS7JkmpZvVipYvB2LJGU1ZxJwYvP98617"
_EXPECTED_WIF_UNCOMPRESSED = "5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ"
_EXPECTED_ADDRESS_COMPRESSED = "1LoVGDgRs9hTfTNJNuXKSpywcbdvwRXpmK"
_EXPECTED_ADDRESS_UNCOMPRESSED = "1GAehh7TsJAHuUAeKZcXf5CnwuGuGgyX2S"


# ---------------------------------------------------------------------------
# EncodingUtils 测试
# ---------------------------------------------------------------------------


class TestEncodingUtils(unittest.TestCase):
    """文件编码检测和转换工具测试"""

    def test_detect_utf8_encoding(self):
        """检测UTF-8编码文件"""
        content = "Hello World! 你好世界!"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_path = f.name

        try:
            encoding = EncodingUtils.detect_file_encoding(temp_path)
            self.assertEqual(encoding, "utf-8")
        finally:
            pathlib.Path(temp_path).unlink()

    def test_read_write_file(self):
        """文件读写往返测试"""
        content = "Test content with 中文"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            temp_path = f.name

        try:
            EncodingUtils.write_file(temp_path, content)
            read_content = EncodingUtils.read_file(temp_path)
            self.assertEqual(read_content, content)
        finally:
            pathlib.Path(temp_path).unlink()

    def test_convert_file_encoding(self):
        """文件编码转换测试"""
        content = "测试内容 Test Content"
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as src_file:
            src_path = src_file.name
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as dst_file:
            dst_path = dst_file.name

        try:
            EncodingUtils.write_file(src_path, content, encoding="gbk")
            result = EncodingUtils.convert_file_encoding(src_path, dst_path, dst_encoding="utf-8")
            self.assertTrue(result)

            # 验证转换后的内容
            converted_content = EncodingUtils.read_file(dst_path, encoding="utf-8")
            self.assertEqual(converted_content, content)
        finally:
            pathlib.Path(src_path).unlink()
            pathlib.Path(dst_path).unlink()

    def test_detect_encoding_from_bytes(self):
        """从字节数据检测编码"""
        utf8_data = "Hello 世界".encode()
        encoding = EncodingUtils.detect_encoding_from_bytes(utf8_data)
        self.assertEqual(encoding, "utf-8")

    def test_ensure_utf8_compatible(self):
        """确保UTF-8兼容性处理"""
        text = "Test\x00text"
        result = EncodingUtils.ensure_utf8_compatible(text)
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# Base58 测试
# ---------------------------------------------------------------------------


class TestBase58(unittest.TestCase):
    """Base58编解码测试"""

    def test_encode_decode_roundtrip(self):
        """Base58编码解码往返测试"""
        data = b"\x00\x01\x02\x03\x04"
        encoded = Base58.encode(data)
        decoded = Base58.decode(encoded)
        self.assertEqual(decoded, data)

    def test_check_encode_decode(self):
        """Base58Check编码解码测试"""
        version = 0x00
        payload = bytes.fromhex("751e76e8199196d454941c45d1b3a323f1433bd6")
        encoded = Base58.check_encode(version, payload)

        decoded_version, decoded_payload = Base58.check_decode(encoded)
        self.assertEqual(decoded_version, version)
        self.assertEqual(decoded_payload, payload)

    def test_encode_empty(self):
        """空数据编码"""
        self.assertEqual(Base58.encode(b""), "")

    def test_decode_empty(self):
        """空字符串解码"""
        self.assertEqual(Base58.decode(""), b"")

    def test_invalid_base58_char(self):
        """无效Base58字符应抛出异常"""
        with self.assertRaises(ValueError):
            Base58.decode("O")  # 'O'不在Base58字符集

    def test_check_decode_invalid_checksum(self):
        """无效校验和应抛出异常"""
        invalid_addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb"  # 篡改最后一位
        with self.assertRaises(ValueError):
            Base58.check_decode(invalid_addr)


# ---------------------------------------------------------------------------
# WIF 测试
# ---------------------------------------------------------------------------


class TestWIF(unittest.TestCase):
    """WIF编解码测试"""

    def test_encode_compressed(self):
        """压缩WIF编码"""
        wif = WIF.encode(_TEST_PRIVATE_KEY, compressed=True)
        self.assertEqual(wif, _EXPECTED_WIF_COMPRESSED)
        self.assertTrue(wif.startswith(("K", "L")))

    def test_encode_uncompressed(self):
        """非压缩WIF编码"""
        wif = WIF.encode(_TEST_PRIVATE_KEY, compressed=False)
        self.assertEqual(wif, _EXPECTED_WIF_UNCOMPRESSED)
        self.assertTrue(wif.startswith("5"))

    def test_decode_compressed(self):
        """压缩WIF解码"""
        private_key, is_compressed = WIF.decode(_EXPECTED_WIF_COMPRESSED)
        self.assertEqual(private_key, _TEST_PRIVATE_KEY)
        self.assertTrue(is_compressed)

    def test_decode_uncompressed(self):
        """非压缩WIF解码"""
        private_key, is_compressed = WIF.decode(_EXPECTED_WIF_UNCOMPRESSED)
        self.assertEqual(private_key, _TEST_PRIVATE_KEY)
        self.assertFalse(is_compressed)

    def test_roundtrip(self):
        """WIF编码解码往返测试"""
        for compressed in [True, False]:
            wif = WIF.encode(_TEST_PRIVATE_KEY, compressed=compressed)
            decoded_key, is_compressed_result = WIF.decode(wif)
            self.assertEqual(decoded_key, _TEST_PRIVATE_KEY)
            self.assertEqual(is_compressed_result, compressed)

    def test_invalid_private_key_length(self):
        """无效私钥长度应抛出异常"""
        with self.assertRaises(ValueError):
            WIF.encode(b"\x00" * 31)  # 31字节，应为32字节

    def test_invalid_wif(self):
        """无效WIF字符串应抛出异常"""
        with self.assertRaises(ValueError):
            WIF.decode("invalid_wif_string")


# AddressConverter 模块已移除 — 相关测试已删除
# 集成测试也依赖 AddressConverter，已一并移除


if __name__ == "__main__":
    unittest.main(verbosity=2)
