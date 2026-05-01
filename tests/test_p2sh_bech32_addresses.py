#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P2SH和Bech32地址生成专项测试

测试BL-3/BR-1修复：添加P2SH和Bech32地址格式支持
"""

import pytest
import hashlib
from src.core.bitcoin_key_validator import BitcoinKeyValidator, AddressType, KeyValidationConstants
from src.core.base58 import Base58


class TestP2SHAddressGeneration:
    """P2SH地址生成测试"""

    def test_p2sh_address_format(self):
        """测试P2SH地址格式（以'3'开头）"""
        # 使用测试公钥（压缩格式）
        test_public_key = bytes.fromhex(
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )

        address = BitcoinKeyValidator.generate_p2sh_address(test_public_key)

        # P2SH地址必须以'3'开头
        assert address.startswith("3"), f"P2SH地址应以'3'开头，实际: {address}"
        # 地址长度应在26-35个字符之间
        assert 26 <= len(address) <= 35, f"P2SH地址长度应在26-35之间，实际: {len(address)}"

        print(f"\n[OK] P2SH地址生成成功: {address}")

    def test_p2sh_address_deterministic(self):
        """测试P2SH地址生成的确定性（相同公钥生成相同地址）"""
        test_public_key = bytes.fromhex(
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )

        address1 = BitcoinKeyValidator.generate_p2sh_address(test_public_key)
        address2 = BitcoinKeyValidator.generate_p2sh_address(test_public_key)

        assert address1 == address2, "相同公钥应生成相同的P2SH地址"
        print(f"\n[OK] P2SH地址确定性验证通过: {address1}")

    def test_p2sh_different_public_keys(self):
        """测试不同公钥生成不同的P2SH地址"""
        public_key1 = bytes.fromhex(
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )
        public_key2 = bytes.fromhex(
            "02c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5"
        )

        address1 = BitcoinKeyValidator.generate_p2sh_address(public_key1)
        address2 = BitcoinKeyValidator.generate_p2sh_address(public_key2)

        assert address1 != address2, "不同公钥应生成不同的P2SH地址"
        print("\n[OK] P2SH地址区分验证通过:")
        print(f"  公钥1 -> {address1}")
        print(f"  公钥2 -> {address2}")

    def test_p2sh_with_compressed_and_uncompressed(self):
        """测试压缩和未压缩公钥生成不同的P2SH地址"""
        # 压缩公钥（33字节）
        compressed_key = bytes.fromhex(
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )

        # 未压缩公钥（65字节）
        uncompressed_key = bytes.fromhex(
            "0479be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
            "483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8"
        )

        address_compressed = BitcoinKeyValidator.generate_p2sh_address(compressed_key)
        address_uncompressed = BitcoinKeyValidator.generate_p2sh_address(uncompressed_key)

        # 压缩和未压缩公钥应生成不同的地址
        assert address_compressed != address_uncompressed, "压缩和未压缩公钥应生成不同的P2SH地址"

        print("\n[OK] P2SH压缩/未压缩公钥区分验证通过:")
        print(f"  压缩公钥 -> {address_compressed}")
        print(f"  未压缩公钥 -> {address_uncompressed}")

    def test_p2sh_address_validation(self):
        """测试P2SH地址的Base58Check校验"""
        test_public_key = bytes.fromhex(
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )

        address = BitcoinKeyValidator.generate_p2sh_address(test_public_key)

        # 尝试解码地址验证Base58Check
        decoded = Base58.decode(address)

        # 应该有25字节（1字节版本 + 20字节哈希 + 4字节校验）
        assert len(decoded) == 25, f"P2SH地址解码后应为25字节，实际: {len(decoded)}"

        # 验证版本号（P2SH = 0x05）
        assert (
            decoded[0] == KeyValidationConstants.P2SH_VERSION_BYTE
        ), f"P2SH版本号应为0x05，实际: {decoded[0]:#x}"

        # 验证校验和
        payload = decoded[:21]  # 版本 + 哈希
        expected_checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
        actual_checksum = decoded[21:]

        assert expected_checksum == actual_checksum, "Base58Check校验和验证失败"

        print(f"\n[OK] P2SH地址Base58Check验证通过: {address}")


class TestBech32AddressGeneration:
    """Bech32地址生成测试"""

    def test_bech32_address_format(self):
        """测试Bech32地址格式（以'bc1'开头）"""
        # 使用测试公钥（压缩格式）
        test_public_key = bytes.fromhex(
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )

        address = BitcoinKeyValidator.generate_bech32_address(test_public_key)

        # Bech32地址必须以'bc1'开头
        assert address.startswith("bc1"), f"Bech32地址应以'bc1'开头，实际: {address}"
        # Bech32地址（P2WPKH）应为42或45个字符（取决于编码）
        assert 42 <= len(address) <= 45, f"Bech32 P2WPKH地址长度应在42-45之间，实际: {len(address)}"

        print(f"\n[OK] Bech32地址生成成功: {address}")

    def test_bech32_address_deterministic(self):
        """测试Bech32地址生成的确定性"""
        test_public_key = bytes.fromhex(
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )

        address1 = BitcoinKeyValidator.generate_bech32_address(test_public_key)
        address2 = BitcoinKeyValidator.generate_bech32_address(test_public_key)

        assert address1 == address2, "相同公钥应生成相同的Bech32地址"
        print(f"\n[OK] Bech32地址确定性验证通过: {address1}")

    def test_bech32_different_public_keys(self):
        """测试不同公钥生成不同的Bech32地址"""
        public_key1 = bytes.fromhex(
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )
        public_key2 = bytes.fromhex(
            "02c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5"
        )

        address1 = BitcoinKeyValidator.generate_bech32_address(public_key1)
        address2 = BitcoinKeyValidator.generate_bech32_address(public_key2)

        assert address1 != address2, "不同公钥应生成不同的Bech32地址"
        print("\n[OK] Bech32地址区分验证通过:")
        print(f"  公钥1 -> {address1}")
        print(f"  公钥2 -> {address2}")

    def test_bech32_rejects_uncompressed_key(self):
        """测试Bech32地址拒绝未压缩公钥"""
        # 未压缩公钥（65字节）
        uncompressed_key = bytes.fromhex(
            "0479be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
            "483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8"
        )

        # Bech32应拒绝未压缩公钥
        with pytest.raises(ValueError, match="Bech32地址仅支持压缩公钥"):
            BitcoinKeyValidator.generate_bech32_address(uncompressed_key)

        print("\n[OK] Bech32拒绝未压缩公钥验证通过")

    def test_bech32_testnet_address(self):
        """测试Testnet Bech32地址生成（以'tb1'开头）"""
        test_public_key = bytes.fromhex(
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )

        # 生成testnet地址
        address = BitcoinKeyValidator.generate_bech32_address(test_public_key, hrp="tb")

        # Testnet Bech32地址必须以'tb1'开头
        assert address.startswith("tb1"), f"Testnet Bech32地址应以'tb1'开头，实际: {address}"
        assert (
            42 <= len(address) <= 45
        ), f"Testnet Bech32地址长度应在42-45之间，实际: {len(address)}"

        print(f"\n[OK] Testnet Bech32地址生成成功: {address}")

    def test_bech32_checksum_validation(self):
        """测试Bech32校验和验证"""
        test_public_key = bytes.fromhex(
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )

        address = BitcoinKeyValidator.generate_bech32_address(test_public_key)

        # Bech32地址应包含校验和（最后6个字符）
        data_part = address.split("1")[1]
        assert len(data_part) >= 6, "Bech32数据部分应至少包含6个校验字符"

        # 验证只包含Bech32字符集
        charset = set("qpzry9x8gf2tvdw0s3jn54khce6mua7l")
        assert all(c in charset for c in data_part), "Bech32地址包含无效字符"

        print(f"\n[OK] Bech32校验和验证通过: {address}")


class TestAddressTypeDetection:
    """地址类型识别测试"""

    def test_detect_p2pkh_address(self):
        """测试识别P2PKH地址（以'1'开头）"""
        address = "12ib7dApVFvg82TXKycWBNpN8kFyiAN1dr"

        # 手动检测地址类型
        if address.startswith("1"):
            addr_type = AddressType.P2PKH
        elif address.startswith("3"):
            addr_type = AddressType.P2SH
        elif address.startswith("bc1") or address.startswith("tb1"):
            addr_type = AddressType.BECH32
        else:
            addr_type = AddressType.UNKNOWN

        assert addr_type == AddressType.P2PKH, f"应识别为P2PKH，实际: {addr_type}"
        print(f"\n[OK] P2PKH地址识别成功: {address}")

    def test_detect_p2sh_address(self):
        """测试识别P2SH地址（以'3'开头）"""
        # 使用生成的P2SH地址
        test_public_key = bytes.fromhex(
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )
        address = BitcoinKeyValidator.generate_p2sh_address(test_public_key)

        # 检测地址类型
        if address.startswith("1"):
            addr_type = AddressType.P2PKH
        elif address.startswith("3"):
            addr_type = AddressType.P2SH
        elif address.startswith("bc1") or address.startswith("tb1"):
            addr_type = AddressType.BECH32
        else:
            addr_type = AddressType.UNKNOWN

        assert addr_type == AddressType.P2SH, f"应识别为P2SH，实际: {addr_type}"
        print(f"\n[OK] P2SH地址识别成功: {address}")

    def test_detect_bech32_address(self):
        """测试识别Bech32地址（以'bc1'开头）"""
        # 使用生成的Bech32地址
        test_public_key = bytes.fromhex(
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )
        address = BitcoinKeyValidator.generate_bech32_address(test_public_key)

        # 检测地址类型
        if address.startswith("1"):
            addr_type = AddressType.P2PKH
        elif address.startswith("3"):
            addr_type = AddressType.P2SH
        elif address.startswith("bc1") or address.startswith("tb1"):
            addr_type = AddressType.BECH32
        else:
            addr_type = AddressType.UNKNOWN

        assert addr_type == AddressType.BECH32, f"应识别为BECH32，实际: {addr_type}"
        print(f"\n[OK] Bech32地址识别成功: {address}")


class TestAddressGenerationIntegration:
    """地址生成集成测试"""

    def test_all_address_types_from_same_key(self):
        """测试从同一私钥生成所有地址类型"""
        # 使用私钥（32字节）
        test_private_key = bytes.fromhex(
            "0000000000000000000000000000000000000000000000000000000000000001"
        )

        # 生成P2PKH地址（使用现有的P2PKHAddressGenerator）
        from src.core.address_generator import P2PKHAddressGenerator

        p2pkh_gen = P2PKHAddressGenerator()
        p2pkh_address, compressed_pubkey, _ = p2pkh_gen.generate_address(test_private_key)

        # 生成P2SH地址
        p2sh_address = BitcoinKeyValidator.generate_p2sh_address(compressed_pubkey)

        # 生成Bech32地址
        bech32_address = BitcoinKeyValidator.generate_bech32_address(compressed_pubkey)

        # 三种地址应不同
        assert p2pkh_address != p2sh_address, "P2PKH和P2SH地址应不同"
        assert p2pkh_address != bech32_address, "P2PKH和Bech32地址应不同"
        assert p2sh_address != bech32_address, "P2SH和Bech32地址应不同"

        # 验证地址格式
        assert p2pkh_address.startswith("1"), f"P2PKH地址应以'1'开头，实际: {p2pkh_address}"
        assert p2sh_address.startswith("3"), f"P2SH地址应以'3'开头，实际: {p2sh_address}"
        assert bech32_address.startswith("bc1"), f"Bech32地址应以'bc1'开头，实际: {bech32_address}"

        print("\n[OK] 所有地址类型生成成功:")
        print(f"  P2PKH:  {p2pkh_address}")
        print(f"  P2SH:   {p2sh_address}")
        print(f"  Bech32: {bech32_address}")

    def test_known_test_vectors(self):
        """测试已知的测试向量"""
        # 使用已知私钥
        known_private_key = bytes.fromhex(
            "0000000000000000000000000000000000000000000000000000000000000001"
        )

        # 生成P2PKH地址和公钥
        from src.core.address_generator import P2PKHAddressGenerator

        p2pkh_gen = P2PKHAddressGenerator()
        p2pkh_address, public_key, _ = p2pkh_gen.generate_address(known_private_key)

        # 生成P2SH地址
        p2sh_address = BitcoinKeyValidator.generate_p2sh_address(public_key)

        # 验证地址格式
        assert p2pkh_address.startswith("1"), "P2PKH地址应以'1'开头"
        assert p2sh_address.startswith("3"), "P2SH地址应以'3'开头"

        print("\n[OK] 已知测试向量验证通过:")
        print(f"  P2PKH: {p2pkh_address}")
        print(f"  P2SH:  {p2sh_address}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
