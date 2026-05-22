#!/usr/bin/env python3
"""比特币多格式地址转换验证测试 - 简化版"""

import secrets

import pytest

from src.core.address_generator import P2PKHAddressGenerator
from src.core.bitcoin_key_validator import AddressType, BitcoinKeyValidator
from src.core.hash_utils import HashUtils
from src.utils.bech32_codec import bech32_encode, decode_segwit_address


class TestMultiFormatAddressGeneration:
    """多格式地址生成与验证测试"""

    @classmethod
    def setup_class(cls):
        cls.addr_gen = P2PKHAddressGenerator()
        cls.validator = BitcoinKeyValidator()
        cls.test_private_key = secrets.token_bytes(32)
        cls.compressed_pk = cls.addr_gen.private_key_to_public_key(cls.test_private_key, compressed=True)

    # ---- 第1组：P2PKH 地址生成 ----

    def test_p2pkh_generation_starts_with_1(self):
        """P2PKH 地址应以 '1' 开头"""
        result, address = self.validator.generate_address(self.compressed_pk, AddressType.P2PKH)
        assert result.success, f"P2PKH 生成失败: {result.errors}"
        assert address.startswith("1"), f"P2PKH 地址不以 '1' 开头: {address}"
        assert 25 <= len(address) <= 35, f"P2PKH 地址长度异常: {len(address)}"

    def test_p2pkh_self_validation(self):
        """生成的 P2PKH 地址能通过验证"""
        result, address = self.validator.generate_address(self.compressed_pk, AddressType.P2PKH)
        validation = self.validator.validate_address(address)
        assert validation.success, f"P2PKH 自验证失败: {validation.errors}"
        assert validation.details.get("address_type") == "P2PKH"

    # ---- 第2组：P2SH 地址生成 ----

    def test_p2sh_generation_starts_with_3(self):
        """P2SH 地址应以 '3' 开头"""
        result, address = self.validator.generate_address(self.compressed_pk, AddressType.P2SH)
        assert result.success, f"P2SH 生成失败: {result.errors}"
        assert address.startswith("3"), f"P2SH 地址不以 '3' 开头: '{address}'"
        assert 25 <= len(address) <= 35, f"P2SH 地址长度异常: {len(address)}"

    def test_p2sh_self_validation(self):
        """生成的 P2SH 地址能通过验证"""
        result, address = self.validator.generate_address(self.compressed_pk, AddressType.P2SH)
        validation = self.validator.validate_address(address)
        assert validation.success, f"P2SH 自验证失败: {validation.errors}"
        assert validation.details.get("address_type") == "P2SH"

    # ---- 第3组：Bech32 地址生成 ----

    def test_bech32_generation_starts_with_bc1(self):
        """Bech32 地址应以 'bc1' 开头"""
        result, address = self.validator.generate_address(self.compressed_pk, AddressType.BECH32)
        assert result.success, f"Bech32 生成失败: {result.errors}"
        assert address.startswith("bc1"), f"Bech32 地址不以 'bc1' 开头: '{address}'"
        assert len(address) >= 10, f"Bech32 地址过短: {len(address)}"

    def test_bech32_self_validation(self):
        """生成的 Bech32 地址能通过验证"""
        result, address = self.validator.generate_address(self.compressed_pk, AddressType.BECH32)
        validation = self.validator.validate_address(address)
        assert validation.success, f"Bech32 自验证失败: {validation.errors}"
        assert validation.details.get("address_type") == "Bech32"

    # ---- 第4组：手动 Bech32 编码一致性 ----

    def test_manual_bech32_matches_validator(self):
        """手动 Bech32 编码与验证器生成的地址一致"""
        result, bech32_address = self.validator.generate_address(self.compressed_pk, AddressType.BECH32)
        hash160 = HashUtils.hash160(self.compressed_pk)
        manual_bech32 = bech32_encode("bc", 0, hash160, "bech32")
        assert manual_bech32 == bech32_address, (
            f"手动编码 {manual_bech32} 与验证器 {bech32_address} 不一致"
        )

    def test_bech32_decode_roundtrip(self):
        """Bech32 编解码往返一致"""
        hash160 = HashUtils.hash160(self.compressed_pk)
        manual_bech32 = bech32_encode("bc", 0, hash160, "bech32")
        witver, prog = decode_segwit_address("bc", manual_bech32)
        assert witver == 0, f"witness version 应为 0，实际: {witver}"
        assert prog == hash160, "解码后的 witness program 与原始 hash160 不一致"

    # ---- 第5组：已知地址验证 ----

    KNOWN_ADDRESSES = [
        ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "P2PKH"),
        ("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", "P2SH"),
        ("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", "Bech32"),
    ]

    @pytest.mark.parametrize("address,expected_type", KNOWN_ADDRESSES)
    def test_known_address_validation(self, address, expected_type):
        """已知地址应通过验证且类型匹配"""
        result = self.validator.validate_address(address)
        assert result.success, f"已知 {expected_type} 地址验证失败: {result.errors}"
        detected = result.details.get("address_type", "")
        assert detected == expected_type, f"地址类型不匹配: 期望 {expected_type}, 实际 {detected}"

    # ---- 第6组：格式支持综合验证 ----

    def test_format_support_verification(self):
        """综合验证三种格式生成和验证能力"""
        compressed_pk = self.compressed_pk
        validator = self.validator

        # P2PKH 生成
        _, p2pkh = validator.generate_address(compressed_pk, AddressType.P2PKH)
        assert p2pkh[0] == "1", "P2PKH 生成失败"
        assert validator.validate_address(p2pkh).success, "P2PKH 验证失败"

        # P2SH 生成
        _, p2sh = validator.generate_address(compressed_pk, AddressType.P2SH)
        assert p2sh[0] == "3", "P2SH 生成失败"
        assert validator.validate_address(p2sh).success, "P2SH 验证失败"

        # Bech32 生成
        _, bech32 = validator.generate_address(compressed_pk, AddressType.BECH32)
        assert bech32.startswith("bc1"), "Bech32 生成失败"
        assert validator.validate_address(bech32).success, "Bech32 验证失败"

        # 已知地址
        assert validator.validate_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa").success
        assert validator.validate_address("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy").success
        assert validator.validate_address("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4").success
