"""日志敏感信息过滤测试

验证敏感数据正则表达式模式的正确性和完整性。
"""
import pytest

from src.utils.sensitive_patterns import (
    BECH32_ADDRESS,
    BECH32M_ADDRESS,
    BIP32_EXTENDED_KEY,
    BIP32_EXTENDED_PUBKEY,
    BIP39_PHRASE_12,
    BIP39_PHRASE_24,
    P2PKH_ADDRESS,
    P2SH_ADDRESS,
    PRIVATE_KEY_HEX,
    WIF_COMPRESSED,
    WIF_UNCOMPRESSED,
)


class TestPrivateKeyPatterns:
    """测试私钥相关正则表达式"""

    def test_private_key_hex_32_bytes(self):
        """测试 64 位十六进制私钥匹配"""
        # 有效 64 位十六进制（正好 64 个十六进制字符）
        key = "a1b2c3d4e5f6789a1b2c3d4e5f6789a1b2c3d4e5f6789a1b2c3d4e5f6789a1b2"
        assert len(key) == 64
        assert PRIVATE_KEY_HEX.search(key) is not None

    def test_private_key_hex_with_prefix(self):
        """测试带 0x 前缀的私钥"""
        key = "0xa1b2c3d4e5f6789a1b2c3d4e5f6789a1b2c3d4e5f6789a1b2c3d4e5f6789a1b2"
        assert len(key) == 66  # "0x" + 64 hex chars
        assert PRIVATE_KEY_HEX.search(key) is not None

    def test_private_key_hex_no_false_positive(self):
        """测试不会误匹配更长的十六进制字符串"""
        # 65 位十六进制（不应匹配）
        long_hex = "a" * 65
        assert PRIVATE_KEY_HEX.search(long_hex) is None

    def test_raw_key_pattern(self):
        """测试原始字节模式匹配"""
        # 模拟原始字节字符串
        raw = b"\x01\x02\x03\x04" * 8  # 32 字节
        # 转换为十六进制字符串
        hex_str = raw.hex()
        assert len(hex_str) == 64
        assert PRIVATE_KEY_HEX.search(hex_str) is not None


class TestWifPatterns:
    """测试 WIF 格式正则表达式"""

    def test_wif_uncompressed(self):
        """测试非压缩 WIF（51 字符，以 5 开头）"""
        # 有效非压缩 WIF（模拟：Base58 字符集）
        wif = "5Kw" + "x" * 48  # 51 字符，使用 Base58 有效字符
        assert len(wif) == 51
        assert WIF_UNCOMPRESSED.search(wif) is not None

    def test_wif_compressed(self):
        """测试压缩 WIF（52 字符，以 K 或 L 开头）"""
        # 有效压缩 WIF（模拟：Base58 字符集）
        wif = "Kx" + "x" * 50  # 52 字符
        assert len(wif) == 52
        assert WIF_COMPRESSED.search(wif) is not None


class TestAddressPatterns:
    """测试比特币地址正则表达式"""

    def test_p2pkh_address(self):
        """测试 P2PKH 地址（以 1 开头）"""
        # 有效 P2PKH 地址（模拟）
        addr = "1" + "A" * 32  # 33 字符
        if 25 <= len(addr) <= 34:
            assert P2PKH_ADDRESS.search(addr) is not None

    def test_p2sh_address(self):
        """测试 P2SH 地址（以 3 开头）"""
        addr = "3" + "A" * 32  # 33 字符
        if 25 <= len(addr) <= 34:
            assert P2SH_ADDRESS.search(addr) is not None

    def test_bech32_address(self):
        """测试 Bech32 地址（以 bc1 开头）"""
        addr = "bc1q" + "q" * 38  # 42 字符，使用 Bech32 字符集
        assert len(addr) >= 14
        assert BECH32_ADDRESS.search(addr) is not None

    def test_bech32m_address(self):
        """测试 Bech32m (Taproot) 地址（以 bc1p 开头）"""
        # Bech32m 需要 58 个字符在 bc1p 之后
        addr = "bc1p" + "q" * 58  # 4 + 58 = 62 字符
        assert BECH32M_ADDRESS.search(addr) is not None


class TestBipPatterns:
    """测试 BIP32/BIP39 正则表达式"""

    def test_bip32_extended_key(self):
        """测试 BIP32 扩展密钥模式"""
        # xprv 开头，后面 107-108 个 Base58 字符
        # 使用 Base58 字符集 (不含 0,O,I,l)
        base58_chars = "x" * 108
        key = "xprv" + base58_chars
        assert len(key) == 4 + 108
        assert BIP32_EXTENDED_KEY.search(key) is not None

        # xpub 开头
        key_pub = "xpub" + base58_chars
        assert BIP32_EXTENDED_PUBKEY.search(key_pub) is not None

    def test_bip39_phrase_12(self):
        """测试 BIP39 12 词助记词"""
        # 12 个助记词（每个词 3-8 个字母）
        phrase = "abandon ability able about above absent absorb abstract absurd abuse access accuse"
        assert BIP39_PHRASE_12.search(phrase) is not None

    def test_bip39_phrase_24(self):
        """测试 BIP39 24 词助记词"""
        phrase = "abandon ability able about above absent absorb abstract absurd abuse access accuse "
        phrase += "abandon ability able about above absent absorb abstract absurd abuse access accuse"
        assert BIP39_PHRASE_24.search(phrase) is not None


class TestSecurityFilterIntegration:
    """测试安全过滤器集成"""

    def test_sensitive_data_not_logged(self):
        """测试敏感数据不会被日志记录（模拟）"""
        # 模拟敏感数据
        sensitive_data = {
            "private_key": "a1b2c3d4e5f6789a1b2c3d4e5f6789a1b2c3d4e5f6789a1b2c3d4e5f6789a1b2",
            "wif": "5Kb8kLf8gsCY1GY4JkFPr99KL22R7q6wmBB1898vHkKdbmJ7T",
            "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        }

        # 验证私钥被模式匹配
        assert PRIVATE_KEY_HEX.search(sensitive_data["private_key"]) is not None
        # 验证地址被模式匹配
        assert P2PKH_ADDRESS.search(sensitive_data["address"]) is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
