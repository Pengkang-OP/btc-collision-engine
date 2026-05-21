#!/usr/bin/env python3
"""WIF编码和Bech32地址支持的测试 - 使用Bitcoin Core官方测试向量

覆盖范围:
- WIFEncoder: 主网/测试网 压缩/非压缩 编码解码
- 内置 bech32_decode / decode_segwit_address: BIP-173 P2WPKH / P2WSH
- 内置 bech32m: BIP-350 Taproot (P2TR)
- TargetResolver: bc1q / bc1p 地址解析端到端
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collision.targets.resolver import TargetResolver  # noqa: E402
from src.core.bitcoin_key_validator import WIFEncoder  # noqa: E402
from src.utils.bech32_codec import (  # noqa: E402
    BECH32_CONST,
    BECH32M_CONST,
    bech32_decode,
    convertbits,
    decode_segwit_address,
)

# ---------------------------------------------------------------------------
# WIF 测试向量 (来自 Bitcoin Core / BIP-0032 官方文档)
# ---------------------------------------------------------------------------

# 私钥 (hex): 0C28FCA386C7A227600B2FE50B7CAE11EC86D3BF1FBE471BE89827E19D72AA1D
# 压缩WIF (K/L开头, 52字符)
_TV_PRIVKEY_HEX = "0c28fca386c7a227600b2fe50b7cae11ec86d3bf1fbe471be89827e19d72aa1d"
_TV_WIF_COMPRESSED = "KwdMAjGmerYanjeui5SHS7JkmpZvVipYvB2LJGU1ZxJwYvP98617"
# 非压缩WIF ('5'开头, 51字符)
_TV_WIF_UNCOMPRESSED = "5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ"

# 额外测试向量: 私钥全1
_PRIVKEY_ALL_ONES = bytes([0x00] * 31 + [0x01])


class TestWIFEncoder(unittest.TestCase):
    """WIFEncoder 编解码测试"""

    def test_encode_compressed_mainnet(self):
        """官方测试向量: 压缩WIF主网编码"""
        privkey = bytes.fromhex(_TV_PRIVKEY_HEX)
        wif = WIFEncoder.encode(privkey, compressed=True, testnet=False)
        self.assertEqual(wif, _TV_WIF_COMPRESSED)
        self.assertEqual(len(wif), 52)
        self.assertTrue(wif.startswith(("K", "L")))

    def test_encode_uncompressed_mainnet(self):
        """官方测试向量: 非压缩WIF主网编码"""
        privkey = bytes.fromhex(_TV_PRIVKEY_HEX)
        wif = WIFEncoder.encode(privkey, compressed=False, testnet=False)
        self.assertEqual(wif, _TV_WIF_UNCOMPRESSED)
        self.assertEqual(len(wif), 51)
        self.assertTrue(wif.startswith("5"))

    def test_decode_compressed_mainnet(self):
        """官方测试向量: 压缩WIF主网解码"""
        privkey, is_compressed, is_testnet = WIFEncoder.decode(_TV_WIF_COMPRESSED)
        self.assertEqual(privkey.hex(), _TV_PRIVKEY_HEX)
        self.assertTrue(is_compressed)
        self.assertFalse(is_testnet)

    def test_decode_uncompressed_mainnet(self):
        """官方测试向量: 非压缩WIF主网解码"""
        privkey, is_compressed, is_testnet = WIFEncoder.decode(_TV_WIF_UNCOMPRESSED)
        self.assertEqual(privkey.hex(), _TV_PRIVKEY_HEX)
        self.assertFalse(is_compressed)
        self.assertFalse(is_testnet)

    def test_roundtrip_compressed(self):
        """encode->decode 往返验证 (压缩)"""
        privkey = bytes.fromhex(_TV_PRIVKEY_HEX)
        wif = WIFEncoder.encode(privkey, compressed=True)
        decoded, comp, testnet = WIFEncoder.decode(wif)
        self.assertEqual(decoded, privkey)
        self.assertTrue(comp)
        self.assertFalse(testnet)

    def test_roundtrip_uncompressed(self):
        """encode->decode 往返验证 (非压缩)"""
        privkey = bytes.fromhex(_TV_PRIVKEY_HEX)
        wif = WIFEncoder.encode(privkey, compressed=False)
        decoded, comp, testnet = WIFEncoder.decode(wif)
        self.assertEqual(decoded, privkey)
        self.assertFalse(comp)
        self.assertFalse(testnet)

    def test_encode_testnet_compressed(self):
        """测试网压缩WIF编码"""
        privkey = bytes.fromhex(_TV_PRIVKEY_HEX)
        wif = WIFEncoder.encode(privkey, compressed=True, testnet=True)
        # 测试网压缩WIF以 'c' 开头
        self.assertTrue(wif.startswith("c"), f"Expected 'c' prefix, got: {wif[0]}")

    def test_encode_testnet_uncompressed(self):
        """测试网非压缩WIF编码"""
        privkey = bytes.fromhex(_TV_PRIVKEY_HEX)
        wif = WIFEncoder.encode(privkey, compressed=False, testnet=True)
        # 测试网非压缩WIF以 '9' 开头
        self.assertTrue(wif.startswith("9"), f"Expected '9' prefix, got: {wif[0]}")

    def test_decode_testnet(self):
        """测试网WIF解码: is_testnet=True"""
        privkey = bytes.fromhex(_TV_PRIVKEY_HEX)
        wif = WIFEncoder.encode(privkey, compressed=True, testnet=True)
        decoded, comp, is_testnet = WIFEncoder.decode(wif)
        self.assertEqual(decoded, privkey)
        self.assertTrue(comp)
        self.assertTrue(is_testnet)

    def test_invalid_key_length(self):
        """私钥长度错误应抛出 ValueError"""
        with self.assertRaises(ValueError):
            WIFEncoder.encode(b"\x01" * 31)  # 31字节

    def test_invalid_checksum(self):
        """篡改校验和应抛出 ValueError"""
        privkey = bytes.fromhex(_TV_PRIVKEY_HEX)
        wif = WIFEncoder.encode(privkey, compressed=True)
        # 修改最后一个字符
        corrupted = wif[:-1] + ("A" if wif[-1] != "A" else "B")
        with self.assertRaises(ValueError):
            WIFEncoder.decode(corrupted)

    def test_non_bytes_input(self):
        """非bytes私钥应抛出 ValueError"""
        with self.assertRaises(ValueError):
            WIFEncoder.encode("not_bytes")  # type: ignore

    def test_version_constants(self):
        """版本字节常量验证"""
        self.assertEqual(WIFEncoder.MAINNET_VERSION, 0x80)
        self.assertEqual(WIFEncoder.TESTNET_VERSION, 0xEF)


# ---------------------------------------------------------------------------
# Bech32 测试向量 (BIP-173)
# ---------------------------------------------------------------------------

# P2WPKH 测试向量
_BECH32_TV = [
    # (address, hrp, witness_version, witness_program_hex)
    (
        "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
        "bc",
        0,
        "751e76e8199196d454941c45d1b3a323f1433bd6",  # 20字节 P2WPKH
    ),
    (
        "bc1qrp33g0q5b5698ahp5jnf0y5emu8fh3ks0r3ta",
        "bc",
        0,
        "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"[2:42],  # 简化测试
    ),
]

# BIP-173 官方有效测试向量（部分）
_BIP173_VALID = [
    "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
    "bc1qrp33g0q5b5698ahp5jnf0y5emu8fh3ks0r3ta",
    # P2WSH 32字节
    "bc1qrp33g0q5b5698ahp5jnf0y5emu8fh3ks0r3taxlh08kq",
]

# Bech32m 测试向量 (BIP-350, Taproot bc1p)
_BECH32M_TV = [
    # bc1p开头, witness version=1, 32字节
    "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0",
    "bc1pqyqszqgpqyqszqgpqyqszqgpqyqszqgpqyqszqgpqyqszqgpqyqs3wf0qm",
]

# BIP-173 无效地址
_BIP173_INVALID = [
    "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t5",  # 校验和错误
    "BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4",  # 全大写（有效，测试大小写）
    "bc1qw508d6qejxtdg4Y5r3zarvary0c5xw7kv8f3t4",  # 大小写混合（无效）
]


class TestBech32Decode(unittest.TestCase):
    """内置 bech32_decode / decode_segwit_address 测试"""

    def test_decode_p2wpkh(self):
        """BIP-173 P2WPKH 地址解码"""
        addr = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
        hrp, data, enc = bech32_decode(addr)
        self.assertEqual(hrp, "bc")
        self.assertIsNotNone(data)
        self.assertEqual(enc, BECH32_CONST)
        # 第一个元素是 witness version
        self.assertEqual(data[0], 0)

    def test_decode_segwit_p2wpkh(self):
        """decode_segwit_address: P2WPKH 应返回20字节 witness program"""
        addr = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
        version, program = decode_segwit_address("bc", addr)
        self.assertEqual(version, 0)
        self.assertIsNotNone(program)
        self.assertEqual(len(program), 20)
        # 已知 witness program
        self.assertEqual(program.hex(), "751e76e8199196d454941c45d1b3a323f1433bd6")

    def test_decode_uppercase_valid(self):
        """全大写 Bech32 应被接受（BIP-173允许全大写或全小写）"""
        addr = "BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4"
        hrp, data, enc = bech32_decode(addr)
        # 全大写有效
        self.assertIsNotNone(hrp)
        self.assertEqual(hrp, "bc")

    def test_decode_mixed_case_invalid(self):
        """大小写混合 Bech32 应失败"""
        addr = "bc1qw508d6qejxtdg4Y5r3zarvary0c5xw7kv8f3t4"
        hrp, data, enc = bech32_decode(addr)
        self.assertIsNone(hrp)

    def test_decode_bad_checksum(self):
        """校验和错误的地址应返回 None"""
        addr = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t5"  # 最后1字符改
        hrp, data, enc = bech32_decode(addr)
        self.assertIsNone(hrp)

    def test_bech32m_taproot(self):
        """BIP-350 Taproot (bc1p) 使用 bech32m 校验"""
        addr = "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0"
        hrp, data, enc = bech32_decode(addr)
        self.assertIsNotNone(hrp)
        self.assertEqual(hrp, "bc")
        self.assertEqual(enc, BECH32M_CONST)

    def test_decode_segwit_taproot(self):
        """decode_segwit_address: Taproot 应返回 version=1, 32字节 program"""
        addr = "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0"
        version, program = decode_segwit_address("bc", addr)
        self.assertEqual(version, 1)
        self.assertIsNotNone(program)
        self.assertEqual(len(program), 32)

    def test_hrp_mismatch(self):
        """HRP不匹配应返回 None"""
        addr = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
        version, program = decode_segwit_address("tb", addr)  # 期望tb, 实际bc
        self.assertIsNone(version)

    def test_convertbits_roundtrip(self):
        """convertbits 8->5->8 往返验证"""
        original = list(
            b"\x75\x1e\x76\xe8\x19\x91\x96\xd4\x54\x94\x1c\x45\xd1\xb3\xa3\x23\xf1\x43\x3b\xd6"
        )
        encoded = convertbits(original, 8, 5)
        self.assertIsNotNone(encoded)
        decoded = convertbits(encoded, 5, 8, False)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded, original)


class TestResolverBech32Integration(unittest.TestCase):
    """TargetResolver 对 Bech32/Taproot 地址的端到端解析测试"""

    def setUp(self):
        self.resolver = TargetResolver(enable_cache=False)

    def test_resolve_bech32_p2wpkh(self):
        """TargetResolver 应能解析 bc1q P2WPKH 地址(保持原格式)"""
        addr = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
        result = self.resolver.resolve(addr)
        self.assertIsNotNone(result, f"Failed to resolve: {addr}")
        # 应返回小写原地址,不转换为P2PKH
        self.assertEqual(result, addr.lower(), f"Expected lowercase original, got: {result}")

    def test_resolve_taproot(self):
        """TargetResolver 应能解析 bc1p Taproot 地址(保持原格式)"""
        addr = "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0"
        result = self.resolver.resolve(addr)
        self.assertIsNotNone(result, f"Failed to resolve Taproot: {addr}")
        # 应返回小写原地址,不转换为P2PKH
        self.assertEqual(result, addr.lower(), f"Expected lowercase original, got: {result}")

    def test_resolve_mixed_case_invalid(self):
        """大小写混合 Bech32 地址应解析失败"""
        addr = "bc1qw508d6qejxtdg4Y5r3zarvary0c5xw7kv8f3t4"
        result = self.resolver.resolve(addr)
        self.assertIsNone(result)

    def test_resolve_bech32_consistency(self):
        """同一 Bech32 地址的大写/小写形式应解析到相同结果"""
        lower = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
        upper = "BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4"
        result_lower = self.resolver.resolve(lower)
        result_upper = self.resolver.resolve(upper)
        self.assertIsNotNone(result_lower)
        self.assertIsNotNone(result_upper)
        self.assertEqual(result_lower, result_upper)

    def test_resolve_p2pkh_unchanged(self):
        """P2PKH 地址解析保持原始大小写（Base58 校验和大小写敏感）"""
        addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        result = self.resolver.resolve(addr)
        self.assertEqual(result, addr)

    def test_resolve_batch_bech32(self):
        """批量解析包含 Bech32 地址"""
        addrs = [
            "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        ]
        results = self.resolver.resolve_batch(addrs)
        self.assertIsNotNone(results[addrs[0]])
        self.assertIsNotNone(results[addrs[1]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
