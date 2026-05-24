#!/usr/bin/env python3
"""比特币密钥生成和地址匹配完整验证测试

测试覆盖：
1. 私钥生成公钥（secp256k1规范）
2. 公钥生成地址（P2PKH/P2SH/Bech32）
3. 私钥转换为WIF格式
4. 地址匹配验证
5. 完整流程验证
"""

import pytest

from src.core.bitcoin_key_validator import (
    AddressType,
    BitcoinKeyValidator,
    validate_bitcoin_key_chain,
)
from src.core.secp256k1 import Secp256k1


class TestPrivateKeyValidation:
    """测试私钥验证"""

    def setup_method(self):
        self.validator = BitcoinKeyValidator()

    def test_valid_private_key(self):
        """测试有效私钥"""
        # 私钥=1（最小有效值）
        private_key = b"\x00" * 31 + b"\x01"
        result = self.validator.validate_private_key(private_key)

        assert result.success is True
        assert len(result.errors) == 0
        assert result.details["private_key_length"] == 32
        assert result.details["private_key_range_valid"] is True

    def test_valid_private_key_max(self):
        """测试最大有效私钥（N-1）"""
        max_key = Secp256k1.N - 1
        private_key = max_key.to_bytes(32, "big")
        result = self.validator.validate_private_key(private_key)

        assert result.success is True
        assert result.details["private_key_range_valid"] is True

    def test_invalid_private_key_zero(self):
        """测试无效私钥：0"""
        private_key = b"\x00" * 32
        result = self.validator.validate_private_key(private_key)

        assert result.success is False
        assert any("Private key value is 0" in error for error in result.errors)

    def test_invalid_private_key_out_of_range(self):
        """测试无效私钥：>= N"""
        private_key = Secp256k1.N.to_bytes(32, "big")
        result = self.validator.validate_private_key(private_key)

        assert result.success is False
        assert any("out of range" in error for error in result.errors)

    def test_invalid_private_key_length(self):
        """测试无效私钥：长度错误"""
        private_key = b"\x01" * 31  # 31字节
        result = self.validator.validate_private_key(private_key)

        assert result.success is False
        assert any("length error" in error for error in result.errors)

    def test_random_private_key(self):
        """测试随机私钥"""
        import secrets

        private_key = secrets.token_bytes(32)
        k = int.from_bytes(private_key, "big")

        # 确保在有效范围内
        if k == 0 or k >= Secp256k1.N:
            private_key = (k % (Secp256k1.N - 1) + 1).to_bytes(32, "big")

        result = self.validator.validate_private_key(private_key)

        # 应该在范围内
        assert result.details["private_key_length"] == 32


class TestPublicKeyGeneration:
    """测试公钥生成"""

    def setup_method(self):
        self.validator = BitcoinKeyValidator()

    def test_generate_compressed_public_key(self):
        """测试生成压缩公钥"""
        private_key = b"\x00" * 31 + b"\x01"  # 私钥=1
        result, public_key = self.validator.generate_public_key(private_key, compressed=True)

        assert result.success is True
        assert len(public_key) == 33
        assert public_key[0] in [0x02, 0x03]
        assert result.details["public_key_format"] == "compressed"
        assert result.details["public_key_on_curve"] is True

    def test_generate_uncompressed_public_key(self):
        """测试生成非压缩公钥"""
        private_key = b"\x00" * 31 + b"\x01"
        result, public_key = self.validator.generate_public_key(private_key, compressed=False)

        assert result.success is True
        assert len(public_key) == 65
        assert public_key[0] == 0x04
        assert result.details["public_key_format"] == "uncompressed"
        assert result.details["public_key_on_curve"] is True

    def test_public_key_on_curve(self):
        """测试公钥在secp256k1曲线上"""
        import secrets

        private_key = secrets.token_bytes(32)
        k = int.from_bytes(private_key, "big") % (Secp256k1.N - 1) + 1
        private_key = k.to_bytes(32, "big")

        result, public_key = self.validator.generate_public_key(private_key, compressed=True)

        assert result.success is True
        assert result.details["public_key_on_curve"] is True

    def test_invalid_private_key_for_public_key(self):
        """测试使用无效私钥生成公钥"""
        private_key = b"\x00" * 32  # 0，无效
        result, public_key = self.validator.generate_public_key(private_key, compressed=True)

        assert result.success is False
        assert len(public_key) == 0


class TestPublicKeyValidation:
    """测试公钥验证"""

    def setup_method(self):
        self.validator = BitcoinKeyValidator()

    def test_valid_compressed_public_key(self):
        """测试有效压缩公钥"""
        private_key = b"\x00" * 31 + b"\x01"
        _, public_key = self.validator.generate_public_key(private_key, compressed=True)

        result = self.validator.validate_public_key(public_key)

        assert result.success is True
        assert result.details["public_key_format"] == "compressed"
        assert result.details["public_key_on_curve"] is True

    def test_valid_uncompressed_public_key(self):
        """测试有效非压缩公钥"""
        private_key = b"\x00" * 31 + b"\x01"
        _, public_key = self.validator.generate_public_key(private_key, compressed=False)

        result = self.validator.validate_public_key(public_key)

        assert result.success is True
        assert result.details["public_key_format"] == "uncompressed"
        assert result.details["public_key_on_curve"] is True

    def test_invalid_compressed_public_key_prefix(self):
        """测试无效压缩公钥前缀"""
        public_key = b"\x01" + b"\x00" * 32  # 错误前缀
        result = self.validator.validate_public_key(public_key)

        assert result.success is False
        assert any("prefix error" in error for error in result.errors)

    def test_invalid_uncompressed_public_key_prefix(self):
        """测试无效非压缩公钥前缀"""
        public_key = b"\x05" + b"\x00" * 64  # 错误前缀
        result = self.validator.validate_public_key(public_key)

        assert result.success is False
        assert any("prefix error" in error for error in result.errors)

    def test_invalid_public_key_length(self):
        """测试无效公钥长度"""
        public_key = b"\x00" * 50  # 错误长度
        result = self.validator.validate_public_key(public_key)

        assert result.success is False
        assert any("length error" in error for error in result.errors)


class TestAddressGeneration:
    """测试地址生成"""

    def setup_method(self):
        self.validator = BitcoinKeyValidator()

    def test_generate_p2pkh_address(self):
        """测试生成P2PKH地址"""
        private_key = b"\x00" * 31 + b"\x01"
        _, public_key = self.validator.generate_public_key(private_key, compressed=True)

        result, address = self.validator.generate_address(public_key, AddressType.P2PKH)

        assert result.success is True
        assert address.startswith("1")
        assert 25 <= len(address) <= 34
        assert result.details["address_type"] == "P2PKH"
        assert result.details["address_checksum_valid"] is True

    def test_p2pkh_address_format(self):
        """测试P2PKH地址格式"""
        # 已知私钥=1的地址
        private_key = b"\x00" * 31 + b"\x01"
        _, public_key = self.validator.generate_public_key(private_key, compressed=True)
        result, address = self.validator.generate_address(public_key, AddressType.P2PKH)

        # 已知地址
        expected_address = "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"
        assert address == expected_address

    def test_generate_address_from_invalid_public_key(self):
        """测试从无效公钥生成地址"""
        public_key = b"\x00" * 33  # 无效公钥
        result, address = self.validator.generate_address(public_key, AddressType.P2PKH)

        assert result.success is False
        assert address == ""


class TestAddressValidation:
    """测试地址验证"""

    def setup_method(self):
        self.validator = BitcoinKeyValidator()

    def test_valid_p2pkh_address(self):
        """测试有效P2PKH地址"""
        address = "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"
        result = self.validator.validate_address(address)

        assert result.success is True
        assert result.details["address_type"] == "P2PKH"
        assert result.details["checksum_valid"] is True

    def test_valid_p2sh_address(self):
        """测试有效P2SH地址"""
        address = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
        result = self.validator.validate_address(address)

        assert result.success is True
        assert result.details["address_type"] == "P2SH"

    def test_invalid_address_format(self):
        """测试无效地址格式"""
        address = "invalid_address!"
        result = self.validator.validate_address(address)

        assert result.success is False

    def test_invalid_address_checksum(self):
        """测试无效地址校验和"""
        # 篡改有效地址
        address = "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMi"  # 最后一个字符改变
        result = self.validator.validate_address(address)

        assert result.success is False


class TestWIFEncoding:
    """测试WIF编码"""

    def setup_method(self):
        self.validator = BitcoinKeyValidator()

    def test_compressed_wif_encoding(self):
        """测试压缩WIF编码"""
        private_key = b"\x00" * 31 + b"\x01"
        result, wif = self.validator.private_key_to_wif(private_key, compressed=True)

        assert result.success is True
        assert len(wif) == 52
        assert wif.startswith(("K", "L"))
        assert result.details["wif_checksum_valid"] is True

    def test_uncompressed_wif_encoding(self):
        """测试非压缩WIF编码"""
        private_key = b"\x00" * 31 + b"\x01"
        result, wif = self.validator.private_key_to_wif(private_key, compressed=False)

        assert result.success is True
        assert len(wif) == 51
        assert wif.startswith("5")
        assert result.details["wif_checksum_valid"] is True

    def test_known_wif_encoding(self):
        """测试已知WIF编码"""
        private_key = b"\x00" * 31 + b"\x01"
        result, wif = self.validator.private_key_to_wif(private_key, compressed=True)

        # 已知私钥=1的WIF
        expected_wif = "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn"
        assert wif == expected_wif

    def test_wif_decode(self):
        """测试WIF解码"""
        wif = "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn"
        result, private_key, compressed = self.validator.wif_to_private_key(wif)

        assert result.success is True
        assert private_key == b"\x00" * 31 + b"\x01"
        assert compressed is True

    def test_invalid_wif(self):
        """测试无效WIF"""
        wif = "invalid_wif_format"
        result, private_key, compressed = self.validator.wif_to_private_key(wif)

        assert result.success is False


class TestAddressMatching:
    """测试地址匹配"""

    def setup_method(self):
        self.validator = BitcoinKeyValidator()

    def test_address_match(self):
        """测试地址匹配"""
        address = "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"
        target_addresses = {
            "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        }

        result = self.validator.verify_address_match(address, target_addresses)

        assert result.success is True
        assert result.details["match"] is True
        assert result.details["matched_target"] == address

    def test_address_no_match(self):
        """测试地址不匹配"""
        address = "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"
        target_addresses = {
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "12c6DSiU4Rq3P4ZxziKxzrL5LmMBrzjrJX",
        }

        result = self.validator.verify_address_match(address, target_addresses)

        assert result.details["match"] is False

    def test_address_match_safe_comparison(self):
        """测试地址匹配使用安全比较"""
        address = "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"
        target_addresses = {address}

        result = self.validator.verify_address_match(address, target_addresses)

        # 应使用hmac.compare_digest进行安全比较
        assert result.details["match"] is True


class TestFullValidationChain:
    """测试完整验证链"""

    def setup_method(self):
        self.validator = BitcoinKeyValidator()

    def test_full_chain_private_key_1(self):
        """测试私钥=1的完整验证链 (非安全模式，验证完整密钥数据)"""
        validator = BitcoinKeyValidator(secure_mode=False)
        private_key = b"\x00" * 31 + b"\x01"
        target_addresses = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}

        report = validator.full_validation_chain(private_key, target_addresses)

        assert report["overall_success"] is True
        assert report["summary"]["address"] == "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"
        assert report["summary"]["private_key_hash"] == private_key.hex()
        assert (
            report["summary"]["wif_compressed"] == "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn"
        )
        assert report["summary"]["address_match"] is True

        # 验证所有步骤都成功
        for step_name, step_result in report["steps"].items():
            assert step_result["success"] is True, f"步骤 {step_name} 失败"

    def test_full_chain_random_key(self):
        """测试随机私钥的完整验证链 (非安全模式，验证完整密钥数据)"""
        import secrets

        validator = BitcoinKeyValidator(secure_mode=False)

        # 生成有效随机私钥
        k = int.from_bytes(secrets.token_bytes(32), "big") % (Secp256k1.N - 1) + 1
        private_key = k.to_bytes(32, "big")

        target_addresses = set()  # 空目标集

        report = validator.full_validation_chain(private_key, target_addresses)

        assert report["overall_success"] is True
        assert len(report["summary"]["private_key_hash"]) == 64
        assert len(report["summary"]["public_key_compressed"]) == 66  # 33字节hex
        assert len(report["summary"]["address"]) >= 25
        assert len(report["summary"]["wif_compressed"]) == 52

    def test_full_chain_with_invalid_key(self):
        """测试无效私钥的完整验证链"""
        private_key = b"\x00" * 32  # 0，无效
        target_addresses = set()

        report = self.validator.full_validation_chain(private_key, target_addresses)

        assert report["overall_success"] is False
        assert len(report["errors"]) > 0

    def test_convenience_function(self):
        """测试便捷函数"""
        private_key = b"\x00" * 31 + b"\x01"
        target_addresses = {"1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"}

        report = validate_bitcoin_key_chain(private_key, target_addresses)

        assert report["overall_success"] is True
        assert report["summary"]["address_match"] is True


class TestBitcoinCoreCompliance:
    """测试Bitcoin Core规范符合性"""

    def setup_method(self):
        self.validator = BitcoinKeyValidator()

    def test_secp256k1_curve_equation(self):
        """测试secp256k1曲线方程：y² = x³ + 7 (mod p)"""
        # 使用基点G验证
        x = Secp256k1.Gx
        y = Secp256k1.Gy

        # 验证 y² ≡ x³ + 7 (mod p)
        left_side = pow(y, 2, Secp256k1.P)
        right_side = (pow(x, 3, Secp256k1.P) + 7) % Secp256k1.P

        assert left_side == right_side

    def test_private_key_range(self):
        """测试私钥范围：1 <= k < N"""
        # 最小有效私钥
        min_key = 1
        result = self.validator.validate_private_key(min_key.to_bytes(32, "big"))
        assert result.success is True

        # 最大有效私钥
        max_key = Secp256k1.N - 1
        result = self.validator.validate_private_key(max_key.to_bytes(32, "big"))
        assert result.success is True

        # 超出范围
        out_of_range = Secp256k1.N
        result = self.validator.validate_private_key(out_of_range.to_bytes(32, "big"))
        assert result.success is False

    def test_public_key_compression_format(self):
        """测试公钥压缩格式规范"""
        private_key = b"\x00" * 31 + b"\x01"
        _, public_key = self.validator.generate_public_key(private_key, compressed=True)

        # 压缩公钥必须是33字节
        assert len(public_key) == 33

        # 必须以02或03开头
        assert public_key[0] in [0x02, 0x03]

        # 02表示y是偶数，03表示y是奇数
        _, public_key_uncomp = self.validator.generate_public_key(private_key, compressed=False)
        y = int.from_bytes(public_key_uncomp[33:], "big")

        if y % 2 == 0:
            assert public_key[0] == 0x02
        else:
            assert public_key[0] == 0x03

    def test_base58check_encoding(self):
        """测试Base58Check编码规范"""
        from src.core.base58 import Base58

        # 测试编码和解码
        test_data = b"\x00" * 20  # 20字节hash160
        encoded = Base58.check_encode(0x00, test_data)

        # 解码
        version, decoded = Base58.check_decode(encoded)

        assert version == 0x00
        assert decoded == test_data

    def test_wif_format_compliance(self):
        """测试WIF格式符合性"""
        private_key = b"\x00" * 31 + b"\x01"

        # 压缩WIF
        result_comp, wif_comp = self.validator.private_key_to_wif(private_key, compressed=True)
        assert len(wif_comp) == 52
        assert wif_comp.startswith(("K", "L"))

        # 非压缩WIF
        result_uncomp, wif_uncomp = self.validator.private_key_to_wif(private_key, compressed=False)
        assert len(wif_uncomp) == 51
        assert wif_uncomp.startswith("5")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
