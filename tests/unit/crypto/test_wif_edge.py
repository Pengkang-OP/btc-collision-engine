"""WIF (Wallet Import Format) 边界与错误路径覆盖测试"""

import pytest
from unittest.mock import patch

from src.core.wif import WIF


class TestWIFEncodeEdge:
    """WIF.encode 边界路径"""

    def test_encode_non_bytes_input(self):
        """Encode 非 bytes 输入"""
        with self.assertRaises(ValueError) as ctx:
            WIF.encode("not_bytes", compressed=True)
        assert str(ctx.exception)  in  "bytes"

    def test_encode_invalid_key_length(self):
        """Encode 私钥长度不是 32"""
        with self.assertRaises(ValueError) as ctx:
            WIF.encode(b"\x01" * 31, compressed=True)
        assert str(ctx.exception)  in  "32 bytes"

    def test_encode_uncompressed(self):
        """Encode compressed=False"""
        wif = WIF.encode(b"\x01" * 32, compressed=False)
        assert isinstance(wif, str)
        assert wif.startswith("5")

    def test_encode_non_valueerror_exception_handler(self):
        """Encode 非 ValueError 异常直接传播 — Base58.encode raises TypeError"""
        with patch("src.core.wif.Base58.encode", side_effect=TypeError("模拟Base58内部错误")):
            with self.assertRaises(TypeError) as ctx:
                WIF.encode(b"\x01" * 32, compressed=True)
            assert str(ctx.exception)  in  "模拟Base58内部错误"


class TestWIFDecodeEdge:
    """WIF.decode 边界路径"""

    def test_decode_non_string_input(self):
        """Decode 非 str 输入"""
        with self.assertRaises(ValueError) as ctx:
            WIF.decode(12345)
        assert str(ctx.exception)  in  "string"

    @patch("src.core.wif.Base58.decode")
    def test_decode_invalid_version_byte(self, mock_decode):
        """Decode 版本字节不是 0x80"""
        mock_decode.return_value = b"\x55" + b"\x01" * 32 + b"\x01\x02\x03\x04"
        with self.assertRaises(ValueError) as ctx:
            WIF.decode("5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ")
        assert str(ctx.exception)  in  "version"

    @patch("src.core.wif.Base58.decode")
    def test_decode_compressed(self, mock_decode):
        """Decode 压缩格式 (33字节key, 末尾0x01)"""
        # payload: version(0x80) + key(32) + 0x01 = 34 bytes + checksum(4) = 38
        payload = bytes([0x80]) + b"\x01" * 32 + bytes([0x01])
        from src.core.hash_utils import HashUtils

        checksum = HashUtils.double_sha256(payload)[:4]
        mock_decode.return_value = payload + checksum
        pk, compressed = WIF.decode("fake_wif")
        assert pk  ==  b"\x01" * 32
        assert compressed

    @patch("src.core.wif.Base58.decode")
    def test_decode_uncompressed(self, mock_decode):
        """Decode 非压缩格式 (32字节key)"""
        # payload: version(0x80) + key(32) = 33 bytes + checksum(4) = 37
        payload = bytes([0x80]) + b"\x01" * 32
        from src.core.hash_utils import HashUtils

        checksum = HashUtils.double_sha256(payload)[:4]
        mock_decode.return_value = payload + checksum
        pk, compressed = WIF.decode("fake_wif")
        assert pk  ==  b"\x01" * 32
        assert not compressed

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
        assert str(ctx.exception)  in  "Invalid WIF payload length"

    @patch("src.core.wif.Base58.decode")
    def test_decode_non_valueerror_exception_handler(self, mock_decode):
        """Decode 非 ValueError 异常直接传播"""
        mock_decode.side_effect = TypeError("模拟Base58内部错误")
        with self.assertRaises(TypeError) as ctx:
            WIF.decode("5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ")
        assert str(ctx.exception)  in  "模拟Base58内部错误"


if __name__ == "__main__":
    unittest.main(verbosity=2)
