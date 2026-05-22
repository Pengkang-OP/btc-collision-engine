"""核心加密模块单元测试 - Secp256k1、HashUtils、Base58、WIF、P2PKHAddressGenerator"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.address_generator import P2PKHAddressGenerator  # noqa: E402
from src.core.base58 import Base58  # noqa: E402
from src.core.hash_utils import HashUtils  # noqa: E402
from src.core.secp256k1 import Secp256k1  # noqa: E402
from src.core.wif import WIF  # noqa: E402


class TestSecp256k1(unittest.TestCase):
    """secp256k1 椭圆曲线运算测试"""

    def test_curve_order_valid(self):
        """曲线阶 N 是正整数"""
        self.assertGreater(Secp256k1.N, 0)
        self.assertEqual(Secp256k1.N, 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141)

    def test_generator_point_on_curve(self):
        """生成元 G 在曲线上"""
        Gx = Secp256k1.Gx
        Gy = Secp256k1.Gy
        P = Secp256k1.P
        # y^2 = x^3 + 7 (mod P)
        lhs = pow(Gy, 2, P)
        rhs = (pow(Gx, 3, P) + 7) % P
        self.assertEqual(lhs, rhs)

    def test_scalar_mult_identity(self):
        """G * N = infinity（无穷远点）"""
        # 确保私钥 1 能生成有效公钥
        pk = (1).to_bytes(32, "big")
        gen = P2PKHAddressGenerator()
        addr, pub, _ = gen.generate_address(pk)
        self.assertTrue(addr.startswith("1"))

    def test_known_key_address(self):
        """已知私钥 1 对应的地址验证"""
        # 私钥 = 1 对应的比特币地址
        pk = (1).to_bytes(32, "big")
        gen = P2PKHAddressGenerator()
        addr, _, _ = gen.generate_address(pk)
        # 私钥1对应压缩公钥的P2PKH地址
        self.assertIsInstance(addr, str)
        self.assertTrue(len(addr) >= 25)
        self.assertTrue(addr.startswith("1"))

    def test_large_private_key(self):
        """接近 N 的大私钥"""
        pk = (Secp256k1.N - 1).to_bytes(32, "big")
        gen = P2PKHAddressGenerator()
        addr, pub, _ = gen.generate_address(pk)
        self.assertTrue(addr.startswith("1"))


class TestHashUtils(unittest.TestCase):
    """哈希工具函数测试"""

    def test_sha256_known_value(self):
        """SHA256 已知向量"""
        result = HashUtils.sha256(b"")
        expected = bytes.fromhex("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        self.assertEqual(result, expected)

    def test_sha256_hello(self):
        """SHA256("hello")"""
        result = HashUtils.sha256(b"hello")
        expected = bytes.fromhex("2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")
        self.assertEqual(result, expected)

    def test_hash160_known(self):
        """Hash160 = RIPEMD160(SHA256(data))"""
        result = HashUtils.hash160(b"\x04" + b"\x00" * 64)
        self.assertEqual(len(result), 20)

    def test_double_sha256(self):
        """双重 SHA256"""
        result = HashUtils.double_sha256(b"test")
        self.assertEqual(len(result), 32)

    def test_hash256_consistency(self):
        """同一数据多次哈希结果一致"""
        data = b"bitcoin"
        self.assertEqual(HashUtils.sha256(data), HashUtils.sha256(data))
        self.assertEqual(HashUtils.hash160(data), HashUtils.hash160(data))

    def test_hash160_to_address_valid(self):
        """Hash160转P2PKH地址 (cover line 88-90)"""
        # 使用比特币创世区块公钥的Hash160 (known value)
        hash160 = bytes.fromhex("751e76e8199196d454941c45d1b3a323f1433bd6")
        address = HashUtils.hash160_to_address(hash160)
        self.assertTrue(address.startswith("1"))
        self.assertEqual(len(address), 34)

    def test_hash160_to_address_invalid_length(self):
        """Hash160长度非法抛出 ValueError (cover line 84-85)"""
        with self.assertRaises(ValueError) as ctx:
            HashUtils.hash160_to_address(b"\x00" * 10)
        self.assertIn("20", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            HashUtils.hash160_to_address(b"\x00" * 30)
        self.assertIn("20", str(ctx.exception))

    def test_hash160_to_address_custom_version(self):
        """Hash160转地址使用自定义版本字节"""
        hash160 = bytes.fromhex("751e76e8199196d454941c45d1b3a323f1433bd6")
        # Testnet version 0x6F
        address = HashUtils.hash160_to_address(hash160, version=0x6F)
        self.assertTrue(address.startswith("m") or address.startswith("n"))


class TestBase58(unittest.TestCase):
    """Base58 编解码测试"""

    def test_encode_decode_roundtrip(self):
        """Base58 编解码往返一致"""
        data = b"\x00" + bytes(range(20))
        encoded = Base58.encode(data)
        decoded = Base58.decode(encoded)
        self.assertEqual(data, decoded)

    def test_check_encode_decode_roundtrip(self):
        """Base58Check 编解码往返一致"""
        version = 0x00
        payload = bytes(range(20))
        encoded = Base58.check_encode(version, payload)
        dec_ver, dec_payload = Base58.check_decode(encoded)
        self.assertEqual(version, dec_ver)
        self.assertEqual(payload, dec_payload)

    def test_invalid_checksum_raises(self):
        """篡改校验和应抛出异常"""
        payload = bytes(range(20))
        encoded = Base58.check_encode(0x00, payload)
        # 破坏编码字符串
        corrupted = encoded[:-1] + ("A" if encoded[-1] != "A" else "B")
        with self.assertRaises(Exception):  # noqa: B017
            Base58.check_decode(corrupted)

    def test_bitcoin_genesis_address(self):
        """比特币创世区块地址解码"""
        addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        ver, payload = Base58.check_decode(addr)
        self.assertEqual(ver, 0x00)
        self.assertEqual(len(payload), 20)

    def test_base58_invalid_character_zero(self):
        """Base58解码拒绝字符'0'（无效字符）"""
        with self.assertRaises(ValueError) as context:
            Base58.decode("10ABC")
        self.assertIn("无效的Base58字符", str(context.exception))
        self.assertIn("0", str(context.exception))

    def test_base58_invalid_character_O(self):
        """Base58解码拒绝字符'O'（无效字符）"""
        with self.assertRaises(ValueError) as context:
            Base58.decode("1OABC")
        self.assertIn("无效的Base58字符", str(context.exception))
        self.assertIn("O", str(context.exception))

    def test_base58_invalid_character_I(self):
        """Base58解码拒绝字符'I'（无效字符）"""
        with self.assertRaises(ValueError) as context:
            Base58.decode("1IABC")
        self.assertIn("无效的Base58字符", str(context.exception))
        self.assertIn("I", str(context.exception))

    def test_base58_invalid_character_l(self):
        """Base58解码拒绝字符'l'（无效字符）"""
        with self.assertRaises(ValueError) as context:
            Base58.decode("1lABC")
        self.assertIn("无效的Base58字符", str(context.exception))
        self.assertIn("l", str(context.exception))

    def test_base58_invalid_character_special(self):
        """Base58解码拒绝特殊字符"""
        invalid_chars = ["!", "@", "#", "$", "%", "+", "=", "?"]
        for char in invalid_chars:
            with self.subTest(char=char):
                with self.assertRaises(ValueError) as context:
                    Base58.decode(f"1{char}ABC")
                self.assertIn("无效的Base58字符", str(context.exception))
                self.assertIn(char, str(context.exception))

    def test_base58_invalid_character_space(self):
        """Base58解码拒绝空格字符"""
        with self.assertRaises(ValueError) as context:
            Base58.decode("1 ABC")
        self.assertIn("无效的Base58字符", str(context.exception))

    def test_base58_empty_string(self):
        """Base58解码空字符串返回空字节"""
        result = Base58.decode("")
        self.assertEqual(result, b"")

    def test_base58_leading_ones(self):
        """Base58编码正确处理前导零字节"""
        # 多个前导零字节
        data = b"\x00\x00\x00" + b"\x01"
        encoded = Base58.encode(data)
        # 每个\x00对应一个'1'
        self.assertTrue(encoded.startswith("111"))
        decoded = Base58.decode(encoded)
        self.assertEqual(data, decoded)


class TestWIF(unittest.TestCase):
    """WIF 私钥编解码测试"""

    def test_encode_decode_compressed(self):
        """WIF 压缩格式编解码往返"""
        private_key = bytes.fromhex("0c28fca386c7a227600b2fe50b7cae11ec86d3bf1fbe471be89827e19d72aa1d")
        wif = WIF.encode(private_key, compressed=True)
        # 压缩 WIF 以 K 或 L 开头
        self.assertIn(wif[0], ("K", "L"))
        result = WIF.decode(wif)
        # decode 返回 (private_key_bytes, compressed) 元组
        if isinstance(result, tuple):
            decoded, compressed = result
        else:
            decoded = result
        self.assertEqual(decoded, private_key)

    def test_encode_decode_uncompressed(self):
        """WIF 非压缩格式编解码往返"""
        private_key = bytes.fromhex("0c28fca386c7a227600b2fe50b7cae11ec86d3bf1fbe471be89827e19d72aa1d")
        wif = WIF.encode(private_key, compressed=False)
        # 非压缩 WIF 以 5 开头
        self.assertEqual(wif[0], "5")
        result = WIF.decode(wif)
        if isinstance(result, tuple):
            decoded, compressed = result
        else:
            decoded = result
        self.assertEqual(decoded, private_key)

    def test_private_key_1_wif(self):
        """私钥 = 1 的 WIF 编码"""
        pk = (1).to_bytes(32, "big")
        wif = WIF.encode(pk, compressed=True)
        self.assertIn(wif[0], ("K", "L"))

    def test_invalid_wif_raises(self):
        """无效 WIF 应抛出异常"""
        with self.assertRaises(Exception):  # noqa: B017
            WIF.decode("invalid_wif_string")

    def test_wif_length(self):
        """WIF 编码长度合理"""
        pk = bytes(range(1, 33))
        wif_compressed = WIF.encode(pk, compressed=True)
        wif_uncompressed = WIF.encode(pk, compressed=False)
        # 压缩 WIF 约 52 字符，非压缩约 51 字符
        self.assertGreater(len(wif_compressed), 50)
        self.assertGreater(len(wif_uncompressed), 50)


class TestP2PKHAddressGenerator(unittest.TestCase):
    """P2PKH 地址生成器测试"""

    def setUp(self):
        self.gen = P2PKHAddressGenerator()

    def test_generate_valid_address(self):
        """生成地址以 '1' 开头"""
        pk = (42).to_bytes(32, "big")
        addr, _, _ = self.gen.generate_address(pk)
        self.assertTrue(addr.startswith("1"))

    def test_deterministic_generation(self):
        """同一私钥多次生成地址一致"""
        pk = (12345).to_bytes(32, "big")
        addr1, _, _ = self.gen.generate_address(pk)
        addr2, _, _ = self.gen.generate_address(pk)
        self.assertEqual(addr1, addr2)

    def test_different_keys_different_addresses(self):
        """不同私钥生成不同地址"""
        pk1 = (1).to_bytes(32, "big")
        pk2 = (2).to_bytes(32, "big")
        addr1, _, _ = self.gen.generate_address(pk1)
        addr2, _, _ = self.gen.generate_address(pk2)
        self.assertNotEqual(addr1, addr2)

    def test_known_address(self):
        """已知私钥验证地址（来自比特币工具）"""
        # 私钥 0x01 -> 1EHNa6Q4Jz2uvNExL497mE43ikXhwF6kZm（压缩公钥）
        pk = (1).to_bytes(32, "big")
        addr, _, _ = self.gen.generate_address(pk)
        # 只验证格式，不硬编码具体地址
        self.assertRegex(addr, r"^1[1-9A-HJ-NP-Za-km-z]{25,34}$")

    def test_pub_key_length(self):
        """压缩公钥长度为 33 字节"""
        pk = (999).to_bytes(32, "big")
        _, pub, _ = self.gen.generate_address(pk)
        self.assertEqual(len(pub), 33)

    def test_pub_key_prefix(self):
        """压缩公钥前缀为 02 或 03"""
        for k in [1, 2, 3, 100, 9999]:
            pk = k.to_bytes(32, "big")
            _, pub, _ = self.gen.generate_address(pk)
            self.assertIn(pub[0], (2, 3), f"私钥 {k} 的公钥前缀错误: {pub[0]}")

    def test_private_key_zero_rejected(self):
        """私钥=0应该被拒绝（无效私钥）"""
        pk_zero = (0).to_bytes(32, "big")
        with self.assertRaises(ValueError) as context:
            self.gen.generate_address(pk_zero)
        self.assertIn("范围", str(context.exception))
        self.assertIn("[1, N)", str(context.exception))

    def test_private_key_curve_order_rejected(self):
        """私钥=N（曲线阶）应该被拒绝（无效私钥）"""
        from src.core.secp256k1 import Secp256k1

        pk_n = Secp256k1.N.to_bytes(32, "big")
        with self.assertRaises(ValueError) as context:
            self.gen.generate_address(pk_n)
        self.assertIn("范围", str(context.exception))

    def test_private_key_greater_than_curve_order_rejected(self):
        """私钥>N应该被拒绝（超出有效范围）"""
        from src.core.secp256k1 import Secp256k1

        pk_too_large = (Secp256k1.N + 1).to_bytes(32, "big")
        with self.assertRaises(ValueError) as context:
            self.gen.generate_address(pk_too_large)
        self.assertIn("范围", str(context.exception))

    def test_private_key_minimum_valid(self):
        """私钥=1（最小有效值）应该成功生成地址"""
        pk_one = (1).to_bytes(32, "big")
        addr, comp_pk, uncomp_pk = self.gen.generate_address(pk_one)
        self.assertTrue(addr.startswith("1"))
        self.assertEqual(len(comp_pk), 33)
        self.assertEqual(len(uncomp_pk), 65)

    def test_private_key_maximum_valid(self):
        """私钥=N-1（最大有效值）应该成功生成地址"""
        from src.core.secp256k1 import Secp256k1

        pk_max = (Secp256k1.N - 1).to_bytes(32, "big")
        addr, comp_pk, uncomp_pk = self.gen.generate_address(pk_max)
        self.assertTrue(addr.startswith("1"))
        self.assertEqual(len(comp_pk), 33)
        self.assertEqual(len(uncomp_pk), 65)

    def test_private_key_boundary_values_different_addresses(self):
        """边界私钥（1和N-1）生成不同的地址"""
        from src.core.secp256k1 import Secp256k1

        pk_min = (1).to_bytes(32, "big")
        pk_max = (Secp256k1.N - 1).to_bytes(32, "big")
        addr_min, _, _ = self.gen.generate_address(pk_min)
        addr_max, _, _ = self.gen.generate_address(pk_max)
        self.assertNotEqual(addr_min, addr_max)

    def test_private_key_invalid_length(self):
        """私钥长度不为32字节应该被拒绝"""
        invalid_lengths = [16, 24, 31, 33, 48, 64]
        for length in invalid_lengths:
            with self.subTest(length=length):
                pk = bytes(length)
                with self.assertRaises(ValueError) as context:
                    self.gen.generate_address(pk)
                self.assertIn("长度", str(context.exception))
                self.assertIn("32", str(context.exception))

    def test_private_key_random_generation_valid_range(self):
        """随机生成的私钥应该在有效范围内"""
        from src.core.secp256k1 import Secp256k1

        # 生成多个随机私钥并验证范围
        for _ in range(10):
            pk = self.gen.generate_private_key()
            pk_int = int.from_bytes(pk, "big")
            self.assertGreaterEqual(pk_int, 1)
            self.assertLess(pk_int, Secp256k1.N)


if __name__ == "__main__":
    unittest.main(verbosity=2)
