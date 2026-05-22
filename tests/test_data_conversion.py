#!/usr/bin/env python3
"""数据转换模块综合测试

覆盖范围:
- EncodingUtils: 文件编码检测和转换
- Base58: Base58/Base58Check 编解码
- WIF: 钱包导入格式编解码
- AddressConverter: 私钥到地址的完整转换
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.address_converter import AddressConverter  # noqa: E402
from src.core.base58 import Base58  # noqa: E402
from src.core.wif import WIF  # noqa: E402
from src.utils.encoding_utils import EncodingUtils  # noqa: E402

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
            os.unlink(temp_path)

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
            os.unlink(temp_path)

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
            os.unlink(src_path)
            os.unlink(dst_path)

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


# ---------------------------------------------------------------------------
# AddressConverter 测试
# ---------------------------------------------------------------------------


class TestAddressConverter(unittest.TestCase):
    """地址转换工具测试"""

    def setUp(self):
        self.converter = AddressConverter()

    def test_private_key_to_address_compressed(self):
        """私钥转压缩格式地址"""
        result = self.converter.private_key_to_address(_TEST_PRIVATE_KEY, compressed=True)
        self.assertEqual(result["address"], _EXPECTED_ADDRESS_COMPRESSED)
        self.assertTrue(result["compressed"])

    def test_private_key_to_address_uncompressed(self):
        """私钥转非压缩格式地址"""
        result = self.converter.private_key_to_address(_TEST_PRIVATE_KEY, compressed=False)
        self.assertEqual(result["address"], _EXPECTED_ADDRESS_UNCOMPRESSED)
        self.assertFalse(result["compressed"])

    def test_private_key_to_all(self):
        """私钥转所有格式"""
        result = self.converter.private_key_to_all(_TEST_PRIVATE_KEY)

        self.assertEqual(result["private_key"], _TEST_PRIVATE_KEY)
        self.assertEqual(result["address_compressed"], _EXPECTED_ADDRESS_COMPRESSED)
        self.assertEqual(result["address_uncompressed"], _EXPECTED_ADDRESS_UNCOMPRESSED)
        self.assertEqual(result["wif_compressed"], _EXPECTED_WIF_COMPRESSED)
        self.assertEqual(result["wif_uncompressed"], _EXPECTED_WIF_UNCOMPRESSED)

    def test_wif_to_address(self):
        """WIF转地址"""
        result = self.converter.wif_to_address(_EXPECTED_WIF_COMPRESSED)
        self.assertEqual(result["address"], _EXPECTED_ADDRESS_COMPRESSED)

    def test_validate_conversion(self):
        """验证转换正确性"""
        valid, message = self.converter.validate_conversion(_TEST_PRIVATE_KEY)
        self.assertTrue(valid)
        self.assertEqual(message, "验证通过")

    def test_validate_with_expected_address(self):
        """使用期望地址验证转换"""
        valid, message = self.converter.validate_conversion(
            _TEST_PRIVATE_KEY, expected_address=_EXPECTED_ADDRESS_COMPRESSED
        )
        self.assertTrue(valid)

    def test_invalid_private_key_length(self):
        """无效私钥长度应抛出异常"""
        with self.assertRaises(ValueError):
            self.converter.private_key_to_address(b"\x00" * 31)

    def test_private_key_to_all_invalid_length(self):
        """private_key_to_all 无效长度 (cover line 104)"""
        with self.assertRaises(ValueError) as ctx:
            self.converter.private_key_to_all(b"\x00" * 31)
        self.assertIn("32", str(ctx.exception))

    def test_validate_conversion_wif_mismatch(self):
        """validate_conversion WIF 解码后私钥不匹配 (cover line 166)"""
        from unittest.mock import patch

        with patch("src.core.address_converter.WIF.decode") as mock_decode:
            mock_decode.return_value = (b"\xff" * 32, True)
            valid, message = self.converter.validate_conversion(_TEST_PRIVATE_KEY)
            self.assertFalse(valid)
            self.assertIn("WIF解码", message)

    def test_validate_conversion_invalid_address_format(self):
        """validate_conversion 地址格式无效 (cover line 170)"""
        from unittest.mock import patch

        with patch("src.core.address_converter.WIF.decode") as mock_decode:
            mock_decode.return_value = (_TEST_PRIVATE_KEY, True)
            with patch.object(
                self.converter,
                "private_key_to_all",
                return_value={
                    "address_compressed": "3xxx",  # 不以'1'开头
                    "wif_compressed": "5valid",
                },
            ):
                valid, message = self.converter.validate_conversion(_TEST_PRIVATE_KEY)
                self.assertFalse(valid)
                self.assertIn("地址格式", message)

    def test_validate_conversion_address_mismatch(self):
        """validate_conversion 期望地址不匹配 (cover line 175)"""
        valid, message = self.converter.validate_conversion(
            _TEST_PRIVATE_KEY, expected_address="1DifferentAddress1234567890"
        )
        self.assertFalse(valid)
        self.assertIn("地址不匹配", message)

    def test_validate_conversion_exception(self):
        """validate_conversion 异常处理 (cover lines 179-180)"""
        from unittest.mock import patch

        with patch.object(self.converter, "private_key_to_all", side_effect=RuntimeError("模拟错误")):
            valid, message = self.converter.validate_conversion(_TEST_PRIVATE_KEY)
            self.assertFalse(valid)
            self.assertEqual(message, "模拟错误")


# ---------------------------------------------------------------------------
# 集成测试
# ---------------------------------------------------------------------------


class TestDataConversionIntegration(unittest.TestCase):
    """数据转换集成测试"""

    def test_full_conversion_chain(self):
        """完整转换链: 私钥 -> WIF -> 地址"""
        converter = AddressConverter()

        # 私钥 -> 所有格式
        result = converter.private_key_to_all(_TEST_PRIVATE_KEY)

        # WIF -> 地址
        wif_result = converter.wif_to_address(result["wif_compressed"])

        # 验证一致性
        self.assertEqual(result["address_compressed"], wif_result["address"])

    def test_encoding_and_wif_combined(self):
        """编码工具与WIF的组合测试"""
        wif = _EXPECTED_WIF_COMPRESSED

        # 将WIF写入文件再读取
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(wif)
            temp_path = f.name

        try:
            read_wif = EncodingUtils.read_file(temp_path)
            converter = AddressConverter()
            result = converter.wif_to_address(read_wif.strip())

            self.assertEqual(result["address"], _EXPECTED_ADDRESS_COMPRESSED)
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
