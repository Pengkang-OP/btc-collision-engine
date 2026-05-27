"""Base58 单元测试 - 覆盖剩余边界路径"""

from src.core.base58 import Base58


class TestBase58Encode:
    """编码测试"""

    def test_encode_empty_bytes(self):
        """空字节串返回空字符串（line 44）"""
        result = Base58.encode(b"")
        assert result == ""

    def test_encode_leading_zeros(self):
        """前导零字节编码为前导'1'"""
        result = Base58.encode(b"\x00\x00\x01")
        assert result.startswith("11")

    def test_encode_roundtrip(self):
        """编码后解码一致性"""
        data = b"\x00\x01\x02\x03"
        encoded = Base58.encode(data)
        decoded = Base58.decode(encoded)
        assert decoded == data


class TestBase58Decode:
    """解码测试"""

    def test_decode_empty_string(self):
        """空字符串返回空字节（line 81）"""
        result = Base58.decode("")
        assert result == b""

    def test_decode_single_one(self):
        """解码 "1" → num=0 分支（line 96）"""
        result = Base58.decode("1")
        assert result == b"\x00"

    def test_decode_invalid_character_0(self):
        """非法字符 '0' 抛出 ValueError（line 90）"""
        with pytest.raises(ValueError) as ctx:
            Base58.decode("0")
        assert "Invalid" in str(ctx.value)

    def test_decode_invalid_character_O(self):
        """非法字符 'O' 抛出 ValueError"""
        with pytest.raises(ValueError) as ctx:
            Base58.decode("O")
        assert "Invalid" in str(ctx.value)

    def test_decode_invalid_character_I(self):
        """非法字符 'I' 抛出 ValueError"""
        with pytest.raises(ValueError) as ctx:
            Base58.decode("I")
        assert "Invalid" in str(ctx.value)

    def test_decode_invalid_character_l(self):
        """非法字符 'l' 抛出 ValueError"""
        with pytest.raises(ValueError) as ctx:
            Base58.decode("l")
        assert "Invalid" in str(ctx.value)


class TestBase58CheckDecode:
    """Base58Check 解码测试"""

    def test_check_decode_success(self):
        """正常校验和解码成功（line 172）"""
        # 编码一个已知有效条目
        encoded = Base58.check_encode(0x00, b"\x00" * 20)
        version, payload = Base58.check_decode(encoded)
        assert version == 0x00
        assert payload == b"\x00" * 20

    def test_check_decode_empty_string(self):
        """空字符串抛出 ValueError（line 151）"""
        with pytest.raises(ValueError) as ctx:
            Base58.check_decode("")
        assert "Empty" in str(ctx.value)

    def test_check_decode_too_short(self):
        """数据过短抛出 ValueError（line 157-160）"""
        # "1" → decode = b"\x00" (1 byte < 5)
        with pytest.raises(ValueError) as ctx:
            Base58.check_decode("1")
        assert "too short" in str(ctx.value)

    def test_check_decode_checksum_failure(self):
        """校验和验证失败（line 169-170）"""
        # 构造一个校验和错误的数据: 修改最后一个字符
        valid = Base58.check_encode(0x00, b"\x00" * 20)
        alphabet = Base58.ALPHABET
        last_char = valid[-1]
        next_char = alphabet[(alphabet.index(last_char) + 1) % len(alphabet)]
        invalid = valid[:-1] + next_char

        with pytest.raises(ValueError) as ctx:
            Base58.check_decode(invalid)
        assert "checksum" in str(ctx.value)
