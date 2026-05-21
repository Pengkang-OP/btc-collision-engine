"""BitcoinKeyValidator 边界与错误路径覆盖测试

覆盖缺失行: 88, 98, 108, 283, 293-294, 399-400, 404-405, 439-441,
           480, 486-489, 508, 555, 561, 569-571, 584-589, 644,
           651, 678-679, 685, 693, 700, 705-706, 712-713, 752,
           756, 759, 763, 771-772, 776-778, 809-810, 815, 819,
           822, 826, 905-907, 915-917, 923-925, 931-933, 939-941, 949
"""

import unittest
from unittest.mock import patch

from src.core.bitcoin_key_validator import (
    AddressType,
    BitcoinKeyValidator,
    WIFEncoder,
)
from src.core.secp256k1 import Secp256k1
from src.utils.bech32_codec import convertbits

# BIP-173 已知测试向量 (G点公钥 → P2WPKH bech32地址)
_BIP173_G_PUBKEY = bytes.fromhex(
    "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
)
_BIP173_EXPECTED_ADDRESS = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"


# ===========================================================================
# Group 1: WIFEncoder.decode 边界
# ===========================================================================


class TestWIFEncoderDecodeEdge(unittest.TestCase):
    """WIFEncoder.decode 错误路径"""

    def setUp(self):
        # 构造一个合法的 WIF 以便做修改测试
        pk = (12345).to_bytes(32, "big")
        self.valid_wif = WIFEncoder.encode(pk, compressed=True)

    def test_decode_too_short_raw(self):
        """Base58 解码后数据过短触发出错 (line 88)"""
        # 使用极短的 Base58 字符串，解码后少于5字节
        with self.assertRaises(ValueError) as ctx:
            WIFEncoder.decode("A")  # 单字符解码后仅1字节
        self.assertIn("过短", str(ctx.exception))

    def test_decode_invalid_version_byte(self):
        """版本字节不在有效范围 (line 98)"""
        # 构造一个版本字节错误的 payload — 使用 check_encode 但版本号为 0x00
        # 然后修改 WIF 中版本对应的部分... 需要巧妙的构造
        # 直接使用一个 Base58 字符串，其解码后的首字节不是 0x80 或 0xEF
        import hashlib

        from src.core.base58 import Base58

        # 构造：版本0x55 + 32字节数据 + 4字节校验和
        payload = bytes([0x55]) + b"\x01" * 32
        raw = payload + hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
        fake_wif = Base58.encode(raw)
        with self.assertRaises(ValueError) as ctx:
            WIFEncoder.decode(fake_wif)
        self.assertIn("版本", str(ctx.exception))

    def test_decode_invalid_payload_length(self):
        """载荷长度不是 32 或 33 字节 (line 108)"""
        import hashlib

        from src.core.base58 import Base58

        # 构造：版本0x80 + 34字节数据 + 4字节校验和（不是32/33）
        payload = bytes([0x80]) + b"\x01" * 34
        raw = payload + hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
        fake_wif = Base58.encode(raw)
        with self.assertRaises(ValueError) as ctx:
            WIFEncoder.decode(fake_wif)
        self.assertIn("载荷", str(ctx.exception))

    def test_decode_checksum_mismatch(self):
        """WIF 校验和不匹配 → line 94"""
        # 破坏合法 WIF 的最后一个字符来触发校验和失败
        corrupted = self.valid_wif[:-1] + ("A" if self.valid_wif[-1] != "A" else "B")
        with self.assertRaises(ValueError) as ctx:
            WIFEncoder.decode(corrupted)
        self.assertIn("校验", str(ctx.exception))


# ===========================================================================
# Group 2: convertbits 错误路径 (bech32_codec)
# ===========================================================================


class TestConvertBitsEdge(unittest.TestCase):
    """convertbits 函数边界路径 (返回 None 表示错误)"""

    def test_invalid_value_returns_none(self):
        """无效值（超出 from_bits 范围）返回 None"""
        # from_bits=4 时, 值 >= 16 会触发 value >> from_bits 检查
        result = convertbits(b"\x10", 4, 5, pad=True)
        self.assertIsNone(result, "超范围值应返回 None")

    def test_no_pad_conversion_fails(self):
        """pad=False 且无法转换 返回 None"""
        # 输入 1 个字节 (8 bits) 转为 5-bit 且不填充
        # 8 bits 转为 5-bit: 剩余 bits=3, 3 >= 8? No. (acc << (5-3)) & 31
        # acc=0x55, 剩余 bits=3, (0x55 << 2) & 31 = (0x154) & 31 = 8, non-zero
        result = convertbits(b"\x55", 8, 5, pad=False)
        self.assertIsNone(result, "无法转换应返回 None")


# ===========================================================================
# Group 3: generate_public_key / generate_address 异常处理
# ===========================================================================


class TestGenerateKeyExceptionHandlers(unittest.TestCase):
    """公钥生成/地址生成 异常处理路径"""

    def setUp(self):
        self.validator = BitcoinKeyValidator(secure_mode=False)
        self.pk = (42).to_bytes(32, "big")

    def test_generate_pubkey_exception_handler(self):
        """generate_public_key 抛出异常时捕获 (lines 439-441)"""
        with patch.object(
            self.validator.curve,
            "scalar_multiply_const_time",
            side_effect=RuntimeError("模拟标量乘法错误"),
        ):
            result, pub_key = self.validator.generate_public_key(self.pk)
            self.assertFalse(result.success)
            self.assertEqual(pub_key, b"")
            self.assertTrue(any("公钥生成失败" in e for e in result.errors))

    @patch("src.core.bitcoin_key_validator.Base58.check_encode")
    def test_generate_address_exception_handler(self, mock_check_encode):
        """generate_address 异常捕获 (lines 584-589)"""
        # 让 Base58.check_encode 抛出 ValueError，触发异常处理路径
        mock_check_encode.side_effect = ValueError("模拟编码错误")
        result, address = self.validator.generate_address(
            self.validator.generate_public_key(self.pk)[1], AddressType.P2PKH
        )
        self.assertFalse(result.success)
        self.assertEqual(address, "")
        self.assertTrue(any("地址生成失败" in e for e in result.errors))

    def test_generate_address_invalid_pubkey_fails(self):
        """generate_address 公钥验证失败 (lines 529-532)"""
        result, address = self.validator.generate_address(b"\x00" * 10)
        self.assertFalse(result.success)
        self.assertEqual(address, "")

    def test_generate_pubkey_infinity_point(self):
        """公钥为无穷远点 → lines 399-400"""
        from src.core.secp256k1 import ECPoint

        inf_point = ECPoint(None, None)  # is_infinity = True
        with patch.object(
            self.validator.curve, "scalar_multiply_const_time", return_value=inf_point
        ):
            result, pub_key = self.validator.generate_public_key(self.pk)
            self.assertFalse(result.success)
            self.assertEqual(pub_key, b"")
            self.assertTrue(any("无穷远点" in e for e in result.errors))

    def test_generate_pubkey_not_on_curve(self):
        """公钥不在曲线上 → lines 404-405"""
        from src.core.secp256k1 import ECPoint

        off_curve = ECPoint(1, 1)  # (1,1) 不在 secp256k1 上
        with patch.object(
            self.validator.curve, "scalar_multiply_const_time", return_value=off_curve
        ):
            result, pub_key = self.validator.generate_public_key(self.pk)
            self.assertFalse(result.success)
            self.assertEqual(pub_key, b"")
            self.assertTrue(any("不在" in e for e in result.errors))


# ===========================================================================
# Group 4: validate_public_key 压缩公钥 y 调整与错误
# ===========================================================================


class TestValidatePubKeyEdge(unittest.TestCase):
    """公钥验证边界路径"""

    def setUp(self):
        self.validator = BitcoinKeyValidator(secure_mode=False)

    def test_compressed_03_y_even_adjustment(self):
        """0x03 前缀且 pow 返回偶 y 需调整 (line 479-480)"""
        # G 点: Gy 是偶数, P-Gy 是奇数
        # 0x03 前缀表示奇数 y → 对应点 (Gx, P-Gy)
        # 验证时 pow 返回 Gy (偶数) → 触发 y = P - y 调整
        Gx = Secp256k1.Gx
        pk = b"\x03" + Gx.to_bytes(32, "big")
        result = self.validator.validate_public_key(pk)
        self.assertTrue(result.success)

    def test_compressed_not_on_curve(self):
        """压缩公钥不在曲线上 → line 486"""
        # 构造一个 x 坐标不在曲线上的点
        bad_pk = b"\x02" + b"\xff" * 31 + b"\xfe"
        result = self.validator.validate_public_key(bad_pk)
        # 可能触发 ValueError（y_squared 不对应任何 y）或明确报错
        self.assertFalse(result.success)

    def test_uncompressed_not_on_curve(self):
        """非压缩公钥不在曲线上 → line 508"""
        bad_pk = b"\x04" + b"\xff" * 32 + b"\xff" * 32
        result = self.validator.validate_public_key(bad_pk)
        self.assertFalse(result.success)

    def test_compressed_validation_exception(self):
        """压缩公钥验证中异常 → lines 488-489"""
        # 使用一个会导致 pow 异常的 x 值… 直接 mock pow 来触发
        pk = b"\x02" + (Secp256k1.Gx).to_bytes(32, "big")
        with patch("builtins.pow", side_effect=ValueError("模拟异常")):
            result = self.validator.validate_public_key(pk)
            self.assertFalse(result.success)
            self.assertTrue(any("验证失败" in e for e in result.errors))


# ===========================================================================
# Group 5: generate_address / validate_address 警告与错误
# ===========================================================================


class TestAddressWarnings(unittest.TestCase):
    """generate_address / validate_address 边界"""

    def setUp(self):
        self.validator = BitcoinKeyValidator(secure_mode=False)
        self.pk = (42).to_bytes(32, "big")
        _, self.pub_key = self.validator.generate_public_key(self.pk)

    @patch("src.core.bitcoin_key_validator.Base58.check_encode")
    @patch.object(BitcoinKeyValidator, "validate_public_key")
    def test_address_not_start_with_1(self, mock_vpk, mock_enc):
        """生成地址不以 '1' 开头 (line 555)"""
        mock_vpk.return_value = _make_success_result()
        mock_enc.return_value = "3NotP2PKHxxxxxxxxxxxxxxxxxxxx"
        result, addr = self.validator.generate_address(self.pub_key, AddressType.P2PKH)
        self.assertTrue(any("'1'" in w for w in result.warnings))

    @patch("src.core.bitcoin_key_validator.Base58.check_encode")
    @patch.object(BitcoinKeyValidator, "validate_public_key")
    def test_address_length_anomaly(self, mock_vpk, mock_enc):
        """P2PKH 地址长度异常 (line 561)"""
        mock_vpk.return_value = _make_success_result()
        mock_enc.return_value = "1Short"
        result, addr = self.validator.generate_address(self.pub_key, AddressType.P2PKH)
        self.assertTrue(any("长度" in w for w in result.warnings))

    @patch("src.core.bitcoin_key_validator.Base58.check_decode")
    @patch("src.core.bitcoin_key_validator.Base58.check_encode")
    @patch.object(BitcoinKeyValidator, "validate_public_key")
    def test_address_base58check_failure(self, mock_vpk, mock_enc, mock_dec):
        """Base58Check 校验失败 (lines 569-571)"""
        mock_vpk.return_value = _make_success_result()
        mock_enc.return_value = "1" + "A" * 33
        mock_dec.side_effect = ValueError("checksum error")
        result, addr = self.validator.generate_address(self.pub_key, AddressType.P2PKH)
        self.assertTrue(any("Base58Check" in e for e in result.errors))

    @patch("src.core.bitcoin_key_validator.Base58.check_decode")
    @patch("src.core.bitcoin_key_validator.Base58.check_encode")
    @patch.object(BitcoinKeyValidator, "validate_public_key")
    def test_address_version_byte_warning_p2pkh(self, mock_vpk, mock_enc, mock_dec):
        """P2PKH 版本字节异常 (line 644)"""
        mock_vpk.return_value = _make_success_result()
        mock_enc.return_value = "1" + "A" * 33
        mock_dec.return_value = (0x01, b"\x00" * 20)  # 非 0x00
        result, addr = self.validator.generate_address(self.pub_key, AddressType.P2PKH)
        warnings = result.warnings
        self.assertTrue(any("版本" in w for w in warnings))

    @patch("src.core.bitcoin_key_validator.Base58.check_decode")
    def test_validate_address_p2sh_version_warning(self, mock_dec):
        """P2SH 版本字节异常 → line 651"""
        mock_dec.return_value = (0x04, b"\x00" * 20)  # 不是 0x05
        result = self.validator.validate_address("3" + "A" * 33)
        self.assertTrue(any("版本" in w for w in result.warnings))

    @patch("src.core.bitcoin_key_validator.Base58.check_decode")
    def test_validate_address_p2pkh_version_warning(self, mock_dec):
        """P2PKH validate 版本字节异常 → line 644"""
        mock_dec.return_value = (0x01, b"\x00" * 20)  # 不是 0x00
        result = self.validator.validate_address("1" + "A" * 33)
        self.assertTrue(any("版本" in w for w in result.warnings))

    def test_validate_address_bech32_bad_char(self):
        """Bech32 包含无效字符 → line 670-671"""
        result = self.validator.validate_address("bc1qw$08d6qejxtdg4")  # $ 是无效的
        self.assertFalse(result.success)

    @patch("src.core.bitcoin_key_validator.bech32_decode")
    def test_validate_address_bech32_decode_fail(self, mock_b32):
        """Bech32 解码失败 → lines 678-679"""
        mock_b32.return_value = (None, None, None)
        result = self.validator.validate_address("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")
        self.assertFalse(result.success)
        self.assertTrue(any("解码失败" in e for e in result.errors))

    @patch("src.core.bitcoin_key_validator.bech32_decode")
    def test_validate_address_bech32_hrp_error(self, mock_b32):
        """Bech32 HRP 错误 → line 685"""
        # 地址必须以 "bc1" 开头才能进入 Bech32 验证分支
        # mock 返回 HRP="xx" (不是 bc/tb), data 长度 33 以通过长度检查
        mock_b32.return_value = ("xx", [0] * 33, 1)
        result = self.validator.validate_address("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")
        self.assertTrue(any("HRP" in e for e in result.errors))

    @patch("src.core.bitcoin_key_validator.bech32_decode")
    def test_validate_address_bech32_bad_data_length(self, mock_b32):
        """Bech32 数据长度错误 → line 693"""
        mock_b32.return_value = ("bc", [0] * 10, 1)  # 10 elements, not 33/53
        result = self.validator.validate_address("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")
        self.assertTrue(any("数据长度" in e for e in result.errors))

    @patch("src.core.bitcoin_key_validator.bech32_decode")
    def test_validate_address_bech32_bad_witness_version(self, mock_b32):
        """Bech32 不支持的 witness 版本 → line 700"""
        data = [1] + [0] * 32  # version=1, not 0
        mock_b32.return_value = ("bc", data, 1)
        result = self.validator.validate_address("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")
        self.assertTrue(any("witness" in e.lower() for e in result.errors))

    @patch("src.core.bitcoin_key_validator.bech32_decode")
    def test_validate_address_bech32_p2wsh(self, mock_b32):
        """Bech32 P2WSH 子类型 → line 705-706"""
        data = [0] + [0] * 52  # 53 elements → P2WSH
        mock_b32.return_value = ("bc", data, 1)
        result = self.validator.validate_address("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")
        self.assertEqual(result.details.get("bech32_address_subtype"), "P2WSH")

    @patch("src.core.bitcoin_key_validator.bech32_decode")
    def test_validate_address_bech32_exception(self, mock_b32):
        """Bech32 验证异常 → lines 712-713"""
        mock_b32.side_effect = RuntimeError("bech32 internal error")
        result = self.validator.validate_address("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")
        self.assertTrue(any("Bech32地址验证失败" in e for e in result.errors))


# ===========================================================================
# Group 6: private_key_to_wif / wif_to_private_key 警告路径
# ===========================================================================


class TestWIFEdgeWarnings(unittest.TestCase):
    """WIF 编解码警告路径"""

    def setUp(self):
        self.validator = BitcoinKeyValidator(secure_mode=False)
        self.pk = (42).to_bytes(32, "big")

    def test_wif_encoding_exception_handler(self):
        """private_key_to_wif 异常捕获 → lines 776-778"""
        # 只能捕获 ValueError/TypeError (line 776)
        with patch("src.core.bitcoin_key_validator.WIF.encode", side_effect=ValueError("编码错误")):
            result, wif = self.validator.private_key_to_wif(self.pk)
            self.assertFalse(result.success)
            self.assertEqual(wif, "")
            self.assertTrue(any("WIF编码失败" in e for e in result.errors))

    @patch("src.core.bitcoin_key_validator.WIF.encode")
    def test_compressed_wif_wrong_length(self, mock_enc):
        """压缩 WIF 长度警告 → line 752"""
        mock_enc.return_value = "K" + "x" * 50  # 51 chars, 压缩应是52
        result, _ = self.validator.private_key_to_wif(self.pk, compressed=True)
        self.assertTrue(any("长度" in w for w in result.warnings))

    @patch("src.core.bitcoin_key_validator.WIF.encode")
    def test_compressed_wif_wrong_prefix(self, mock_enc):
        """压缩 WIF 前缀警告 → line 756"""
        mock_enc.return_value = "5" + "x" * 51  # 以5开头, not K/L
        result, _ = self.validator.private_key_to_wif(self.pk, compressed=True)
        self.assertTrue(any("'K'" in w or "'L'" in w for w in result.warnings))

    @patch("src.core.bitcoin_key_validator.WIF.encode")
    def test_uncompressed_wif_wrong_length(self, mock_enc):
        """非压缩 WIF 长度警告 → line 759"""
        mock_enc.return_value = "5" + "x" * 51  # 52 chars, 非压缩应为51
        result, _ = self.validator.private_key_to_wif(self.pk, compressed=False)
        self.assertTrue(any("长度" in w for w in result.warnings))

    @patch("src.core.bitcoin_key_validator.WIF.encode")
    def test_uncompressed_wif_wrong_prefix(self, mock_enc):
        """非压缩 WIF 前缀警告 → line 763"""
        mock_enc.return_value = "K" + "x" * 51
        result, _ = self.validator.private_key_to_wif(self.pk, compressed=False)
        self.assertTrue(any("'5'" in w for w in result.warnings))

    @patch("src.core.bitcoin_key_validator.Base58.check_decode")
    @patch("src.core.bitcoin_key_validator.WIF.encode")
    def test_wif_base58check_failure(self, mock_enc, mock_dec):
        """WIF Base58Check 校验失败 → lines 771-772"""
        mock_enc.return_value = "K" + "x" * 51
        mock_dec.side_effect = ValueError("校验和错误")
        result, _ = self.validator.private_key_to_wif(self.pk, compressed=True)
        self.assertTrue(any("Base58Check" in e for e in result.errors))

    @patch("src.core.bitcoin_key_validator.WIF.decode")
    def test_wif_to_key_decoded_key_invalid(self, mock_dec):
        """解码后私钥验证失败 → lines 809-810"""
        mock_dec.return_value = (b"\x00" * 32, True)  # 零私钥
        result, pk, comp = self.validator.wif_to_private_key("K" + "x" * 51)
        self.assertFalse(result.success)

    @patch("src.core.bitcoin_key_validator.WIF.decode")
    def test_wif_to_key_compressed_wrong_length(self, mock_dec):
        """压缩 WIF 长度警告 wif_to_private_key → line 815"""
        mock_dec.return_value = (self.pk, True)
        result, _, _ = self.validator.wif_to_private_key("Kx" * 1)  # 短WIF
        self.assertTrue(any("长度" in w for w in result.warnings))

    @patch("src.core.bitcoin_key_validator.WIF.decode")
    def test_wif_to_key_compressed_wrong_prefix(self, mock_dec):
        """压缩 WIF 前缀警告 → line 819"""
        mock_dec.return_value = (self.pk, True)
        result, _, _ = self.validator.wif_to_private_key("5" + "x" * 51)
        self.assertTrue(any("'K'" in w or "'L'" in w for w in result.warnings))

    @patch("src.core.bitcoin_key_validator.WIF.decode")
    def test_wif_to_key_uncompressed_wrong_length(self, mock_dec):
        """非压缩 WIF 长度警告 → line 822"""
        mock_dec.return_value = (self.pk, False)
        result, _, _ = self.validator.wif_to_private_key("K" + "x" * 51)
        self.assertTrue(any("长度" in w for w in result.warnings))

    @patch("src.core.bitcoin_key_validator.WIF.decode")
    def test_wif_to_key_uncompressed_wrong_prefix(self, mock_dec):
        """非压缩 WIF 前缀警告 → line 826"""
        mock_dec.return_value = (self.pk, False)
        result, _, _ = self.validator.wif_to_private_key("K" + "x" * 51)
        self.assertTrue(any("'5'" in w for w in result.warnings))


# ===========================================================================
# Group 7: full_validation_chain 各步骤失败分支
# ===========================================================================


class TestFullChainErrorBranches(unittest.TestCase):
    """full_validation_chain 错误分支"""

    def setUp(self):
        self.pk = (42).to_bytes(32, "big")

    def test_chain_invalid_private_key(self):
        """私钥验证失败 → 早期退出 (已有覆盖, 确认)"""
        v = BitcoinKeyValidator(secure_mode=False)
        report = v.full_validation_chain(b"\x00" * 32, set())
        self.assertFalse(report["overall_success"])

    @patch("src.core.bitcoin_key_validator.BitcoinKeyValidator.generate_public_key")
    def test_chain_compressed_pubkey_failure(self, mock_gen):
        """步骤2 压缩公钥生成失败 → lines 905-907"""
        # mock: 第一次调用 (compressed=True) 返回失败
        fail_result = _make_fail_result("公钥失败")
        success_tuple = _make_pubkey_result()

        def side_effect(pk, compressed=True):
            if compressed:
                return fail_result, b""
            return success_tuple

        mock_gen.side_effect = side_effect
        v = BitcoinKeyValidator(secure_mode=False)
        report = v.full_validation_chain(self.pk, {"1Address"})
        self.assertFalse(report["overall_success"])

    @patch("src.core.bitcoin_key_validator.BitcoinKeyValidator.generate_public_key")
    def test_chain_uncompressed_pubkey_failure(self, mock_gen):
        """步骤3 非压缩公钥生成失败 → lines 915-917"""
        fail_result = _make_fail_result("非压缩失败")
        success_tuple = _make_pubkey_result()

        def side_effect(pk, compressed=True):
            if not compressed:
                return fail_result, b""
            return success_tuple  # 返回完整 tuple，不要解构

        mock_gen.side_effect = side_effect
        v = BitcoinKeyValidator(secure_mode=False)
        report = v.full_validation_chain(self.pk, {"1Address"})
        self.assertFalse(report["overall_success"])

    @patch("src.core.bitcoin_key_validator.BitcoinKeyValidator.generate_address")
    @patch("src.core.bitcoin_key_validator.BitcoinKeyValidator.generate_public_key")
    def test_chain_address_failure(self, mock_pubkey, mock_addr):
        """步骤4 地址生成失败 → lines 923-925"""
        pubkey_tuple = _make_pubkey_result()
        mock_pubkey.return_value = pubkey_tuple
        fail_addr = _make_fail_result("地址失败")
        mock_addr.return_value = (fail_addr, "")
        v = BitcoinKeyValidator(secure_mode=False)
        report = v.full_validation_chain(self.pk, {"1Address"})
        self.assertFalse(report["overall_success"])

    @patch("src.core.bitcoin_key_validator.BitcoinKeyValidator.private_key_to_wif")
    @patch("src.core.bitcoin_key_validator.BitcoinKeyValidator.generate_address")
    @patch("src.core.bitcoin_key_validator.BitcoinKeyValidator.generate_public_key")
    def test_chain_compressed_wif_failure(self, mock_pubkey, mock_addr, mock_wif):
        """步骤5 压缩WIF失败 → lines 931-933"""
        pubkey_tuple = _make_pubkey_result()
        mock_pubkey.return_value = pubkey_tuple
        mock_addr.return_value = (_make_success_result(), "1Addr")
        fail_wif = _make_fail_result("WIF失败")
        mock_wif.side_effect = lambda pk, compressed=True: (
            (fail_wif, "") if compressed else (_make_success_result(), "5wif")
        )
        v = BitcoinKeyValidator(secure_mode=False)
        report = v.full_validation_chain(self.pk, {"1Addr"})
        self.assertFalse(report["overall_success"])

    @patch("src.core.bitcoin_key_validator.BitcoinKeyValidator.private_key_to_wif")
    @patch("src.core.bitcoin_key_validator.BitcoinKeyValidator.generate_address")
    @patch("src.core.bitcoin_key_validator.BitcoinKeyValidator.generate_public_key")
    def test_chain_uncompressed_wif_failure(self, mock_pubkey, mock_addr, mock_wif):
        """步骤6 非压缩WIF失败 → lines 939-941"""
        pubkey_tuple = _make_pubkey_result()
        mock_pubkey.return_value = pubkey_tuple
        mock_addr.return_value = (_make_success_result(), "1Addr")
        fail_wif = _make_fail_result("非压缩WIF失败")

        def wif_side(pk, compressed=True):
            if compressed:
                return _make_success_result(), "KwiF"
            return fail_wif, ""

        mock_wif.side_effect = wif_side
        v = BitcoinKeyValidator(secure_mode=False)
        report = v.full_validation_chain(self.pk, {"1Addr"})
        self.assertFalse(report["overall_success"])

    @patch("src.core.bitcoin_key_validator.BitcoinKeyValidator.verify_address_match")
    @patch("src.core.bitcoin_key_validator.BitcoinKeyValidator.private_key_to_wif")
    @patch("src.core.bitcoin_key_validator.BitcoinKeyValidator.generate_address")
    @patch("src.core.bitcoin_key_validator.BitcoinKeyValidator.generate_public_key")
    def test_chain_match_failure_adds_errors(self, mock_pubkey, mock_addr, mock_wif, mock_match):
        """地址匹配失败时收集错误 → line 949"""
        pubkey_tuple = _make_pubkey_result()
        mock_pubkey.return_value = pubkey_tuple
        mock_addr.return_value = (_make_success_result(), "1Addr")
        mock_wif.return_value = (_make_success_result(), "KwiF")

        fail_match = _make_fail_result("无匹配")
        mock_match.return_value = fail_match
        v = BitcoinKeyValidator(secure_mode=False)
        report = v.full_validation_chain(self.pk, {"1Addr"})
        # overall_success 保持 True (match failure doesn't set overall_success = False)
        # 但 match 的错误被收集到 errors
        self.assertTrue(any("无匹配" in e for e in report.get("errors", [])))


# ===========================================================================
# 辅助函数
# ===========================================================================


def _make_success_result():
    """创建成功 KeyValidationResult"""
    from src.core.bitcoin_key_validator import KeyValidationResult

    r = KeyValidationResult()
    r.add_detail("test", True)
    return r


def _make_fail_result(msg):
    """创建失败 KeyValidationResult"""
    from src.core.bitcoin_key_validator import KeyValidationResult

    r = KeyValidationResult()
    r.add_error(msg)
    return r


def _make_pubkey_result():
    """创建公钥生成结果"""
    r = _make_success_result()
    return r, b"\x02" + b"\x01" * 32


# ===========================================================================
# Group 10: BIP-173 回归测试 (v4.2.3: 旧实现bug修复验证)
# ===========================================================================


class TestBIP173Regression(unittest.TestCase):
    """BIP-173 P2WPKH Bech32地址生成回归测试

    旧实现 (bitcoin_key_validator ~v4.2.2) 存在 BIP-173 协议bug:
    在 8→5 bit 转换时错误地将 version+length 字节混入, 导致生成
    45-char 无效地址而非正确的 42-char。v4.2.3 迁移到统一 bech32_codec 后已修复。
    """

    def test_bech32_address_length(self):
        """Bech32 P2WPKH地址长度 = 42 (非45) — 回归测试"""
        from src.core.bitcoin_key_validator import BitcoinKeyValidator

        address = BitcoinKeyValidator.generate_bech32_address(_BIP173_G_PUBKEY, hrp="bc")
        self.assertEqual(
            len(address), 42, f"Bech32 P2WPKH地址应为42字符, 实际{len(address)} (旧bug会生成45)"
        )
        self.assertTrue(address.startswith("bc1q"), f"P2WPKH地址应以bc1q开头: {address}")

    def test_bech32_address_matches_bip173_vector(self):
        """Bech32地址与 BIP-173 已知向量匹配"""
        from src.core.bitcoin_key_validator import BitcoinKeyValidator

        address = BitcoinKeyValidator.generate_bech32_address(_BIP173_G_PUBKEY, hrp="bc")
        self.assertEqual(
            address,
            _BIP173_EXPECTED_ADDRESS,
            f"Bech32地址应与BIP-173测试向量一致\n  实际: {address}\n  期望: {_BIP173_EXPECTED_ADDRESS}",
        )

    def test_bech32_address_validates_roundtrip(self):
        """生成的Bech32地址可通过 bech32_decode 往返验证"""
        from src.core.bitcoin_key_validator import BitcoinKeyValidator
        from src.utils.bech32_codec import bech32_decode

        address = BitcoinKeyValidator.generate_bech32_address(_BIP173_G_PUBKEY, hrp="bc")
        hrp, data, enc = bech32_decode(address)
        self.assertEqual(hrp, "bc")
        self.assertIsNotNone(data, "Bech32数据不应为空")
        self.assertEqual(enc, 1)  # BECH32_CONST
        self.assertEqual(data[0], 0)  # witness version 0


if __name__ == "__main__":
    unittest.main(verbosity=2)
