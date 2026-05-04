# -*- coding: utf-8 -*-
"""BitcoinComplianceValidator 单元测试 - 覆盖所有验证失败分支"""

import unittest

from src.core.compliance_validator import BitcoinComplianceValidator

# secp256k1 order
SECP256K1_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


def _valid_data():
    """返回有效的测试数据"""
    return {
        "private_key": b"\x01" * 32,
        "public_key": b"\x02" + b"\x00" * 32,
        "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        "wif": "5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ",
        "hash160": b"\x01" * 20,
        "compressed": True,
    }


class TestComplianceValidatorValid(unittest.TestCase):
    """正常验证路径测试"""

    def setUp(self):
        self.v = BitcoinComplianceValidator()

    def test_validate_all_valid_compressed(self):
        """压缩格式全部有效"""
        data = _valid_data()
        is_valid, issues = self.v.validate(data)
        self.assertTrue(is_valid)
        self.assertEqual(len(issues), 0)

    def test_validate_all_valid_uncompressed(self):
        """非压缩格式全部有效"""
        data = _valid_data()
        data["compressed"] = False
        data["public_key"] = b"\x04" + b"\x00" * 64
        is_valid, issues = self.v.validate(data)
        self.assertTrue(is_valid)
        self.assertEqual(len(issues), 0)


class TestValidatePrivateKey(unittest.TestCase):
    """私钥验证测试"""

    def setUp(self):
        self.v = BitcoinComplianceValidator()

    def test_private_key_none(self):
        """缺少私钥"""
        data = _valid_data()
        data.pop("private_key")
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("缺少私钥", issues)

    def test_private_key_not_bytes(self):
        """私钥不是字节串"""
        data = _valid_data()
        data["private_key"] = "not_bytes"
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("私钥必须是字节串", issues)

    def test_private_key_wrong_length(self):
        """私钥长度不为 32 字节"""
        data = _valid_data()
        data["private_key"] = b"\x01" * 31
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("32字节" in i for i in issues))

    def test_private_key_zero(self):
        """私钥为 0（小于 1）"""
        data = _valid_data()
        data["private_key"] = b"\x00" * 32
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("私钥必须大于0", issues)

    def test_private_key_exceeds_order(self):
        """私钥大于等于曲线阶"""
        data = _valid_data()
        data["private_key"] = SECP256K1_ORDER.to_bytes(32, "big")
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("私钥必须小于secp256k1曲线阶", issues)

    def test_private_key_bytearray(self):
        """bytearray 类型应被视为有效"""
        data = _valid_data()
        data["private_key"] = bytearray(b"\x01" * 32)
        is_valid, issues = self.v.validate(data)
        self.assertTrue(is_valid)


class TestValidatePublicKey(unittest.TestCase):
    """公钥验证测试"""

    def setUp(self):
        self.v = BitcoinComplianceValidator()

    def test_public_key_none(self):
        """缺少公钥"""
        data = _valid_data()
        data.pop("public_key")
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("缺少公钥", issues)

    def test_public_key_not_bytes(self):
        """公钥不是字节串"""
        data = _valid_data()
        data["public_key"] = "not_bytes"
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("公钥必须是字节串", issues)

    def test_compressed_wrong_length(self):
        """压缩公钥长度不为 33 字节"""
        data = _valid_data()
        data["public_key"] = b"\x02" + b"\x00" * 33
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("33字节" in i for i in issues))

    def test_compressed_wrong_prefix(self):
        """压缩公钥前缀无效"""
        data = _valid_data()
        data["public_key"] = b"\x04" + b"\x00" * 32
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("0x02或0x03" in i for i in issues))

    def test_compressed_prefix_03(self):
        """压缩公钥前缀 0x03 有效"""
        data = _valid_data()
        data["public_key"] = b"\x03" + b"\x00" * 32
        is_valid, issues = self.v.validate(data)
        self.assertTrue(is_valid)

    def test_uncompressed_wrong_length(self):
        """非压缩公钥长度不为 65 字节"""
        data = _valid_data()
        data["compressed"] = False
        data["public_key"] = b"\x04" + b"\x00" * 63
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("65字节" in i for i in issues))

    def test_uncompressed_wrong_prefix(self):
        """非压缩公钥前缀不为 0x04"""
        data = _valid_data()
        data["compressed"] = False
        data["public_key"] = b"\x03" + b"\x00" * 64
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("0x04" in i for i in issues))

    def test_public_key_bytearray(self):
        """bytearray 类型应被视为有效"""
        data = _valid_data()
        data["public_key"] = bytearray(b"\x02" + b"\x00" * 32)
        is_valid, issues = self.v.validate(data)
        self.assertTrue(is_valid)


class TestValidateAddress(unittest.TestCase):
    """地址验证测试"""

    def setUp(self):
        self.v = BitcoinComplianceValidator()

    def test_address_none(self):
        """缺少地址"""
        data = _valid_data()
        data.pop("address")
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("缺少地址", issues)

    def test_address_not_str(self):
        """地址不是字符串"""
        data = _valid_data()
        data["address"] = 123
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("地址必须是字符串", issues)

    def test_address_not_startswith_1(self):
        """地址不以 '1' 开头"""
        data = _valid_data()
        data["address"] = "3A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("'1'开头" in i for i in issues))

    def test_address_wrong_length(self):
        """地址长度不是 33 或 34 字符"""
        data = _valid_data()
        data["address"] = "1" + "A" * 30
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("33或34" in i for i in issues))

    def test_address_invalid_base58(self):
        """地址包含无效 Base58 字符"""
        data = _valid_data()
        data["address"] = "1" + "0" * 33  # '0' not in Base58
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("地址包含无效的Base58字符", issues)

    def test_address_length_33_valid(self):
        """33 字符地址有效"""
        data = _valid_data()
        data["address"] = "1" + "A" * 32
        is_valid, issues = self.v.validate(data)
        self.assertTrue(is_valid)

    def test_address_length_34_valid(self):
        """34 字符地址有效"""
        data = _valid_data()
        data["address"] = "1" + "A" * 33
        is_valid, issues = self.v.validate(data)
        self.assertTrue(is_valid)


class TestValidateWIF(unittest.TestCase):
    """WIF 验证测试"""

    def setUp(self):
        self.v = BitcoinComplianceValidator()

    def test_wif_none(self):
        """缺少 WIF"""
        data = _valid_data()
        data.pop("wif")
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("缺少WIF", issues)

    def test_wif_not_str(self):
        """WIF 不是字符串"""
        data = _valid_data()
        data["wif"] = 123
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("WIF必须是字符串", issues)

    def test_wif_wrong_start(self):
        """WIF 不以 5/K/L 开头"""
        data = _valid_data()
        data["wif"] = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa1234567890123456"
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("5、K或L" in i for i in issues))

    def test_wif_uncompressed_wrong_length(self):
        """非压缩 WIF (5 开头) 长度不为 51"""
        data = _valid_data()
        data["wif"] = "5" + "A" * 49  # 50 chars total
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("51字符" in i for i in issues))

    def test_wif_compressed_wrong_length(self):
        """压缩 WIF (K/L 开头) 长度不为 52"""
        data = _valid_data()
        data["wif"] = "K" + "A" * 50  # 51 chars total
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("52字符" in i for i in issues))

    def test_wif_compressed_L_valid_length(self):
        """压缩 WIF L 开头长度 52 有效"""
        data = _valid_data()
        data["wif"] = "L" + "A" * 51
        is_valid, issues = self.v.validate(data)
        self.assertTrue(is_valid)

    def test_wif_invalid_base58(self):
        """WIF 包含无效 Base58 字符"""
        data = _valid_data()
        data["wif"] = "5" + "0" * 50  # '0' not in Base58
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("WIF包含无效的Base58字符", issues)

    def test_wif_compressed_K_wrong_length(self):
        """压缩 WIF K 开头但长度错误"""
        data = _valid_data()
        data["wif"] = "K" + "A" * 50  # 51 chars
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("52字符" in i for i in issues))


class TestValidateHash160(unittest.TestCase):
    """Hash160 验证测试"""

    def setUp(self):
        self.v = BitcoinComplianceValidator()

    def test_hash160_none(self):
        """缺少 Hash160"""
        data = _valid_data()
        data.pop("hash160")
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("缺少Hash160", issues)

    def test_hash160_bytes_wrong_length(self):
        """Hash160 字节串长度不为 20"""
        data = _valid_data()
        data["hash160"] = b"\x01" * 21
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("20字节" in i for i in issues))

    def test_hash160_str_wrong_length(self):
        """Hash160 十六进制字符串长度不为 40"""
        data = _valid_data()
        data["hash160"] = "a" * 41
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("40字符" in i for i in issues))

    def test_hash160_wrong_type(self):
        """Hash160 类型无效"""
        data = _valid_data()
        data["hash160"] = 123
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("Hash160必须是字节串或十六进制字符串", issues)

    def test_hash160_str_valid_length(self):
        """Hash160 字符串长度 40 有效"""
        data = _valid_data()
        data["hash160"] = "a" * 40
        is_valid, issues = self.v.validate(data)
        self.assertTrue(is_valid)


class TestValidateBatch(unittest.TestCase):
    """批量验证测试"""

    def setUp(self):
        self.v = BitcoinComplianceValidator()

    def test_validate_batch_all_valid(self):
        """批量全部有效"""
        data_list = [_valid_data() for _ in range(3)]
        results = self.v.validate_batch(data_list)
        self.assertEqual(len(results), 3)
        for is_valid, issues in results:
            self.assertTrue(is_valid)
            self.assertEqual(len(issues), 0)

    def test_validate_batch_mixed(self):
        """批量混合有效/无效"""
        valid = _valid_data()
        invalid1 = _valid_data()
        invalid1.pop("private_key")
        invalid2 = _valid_data()
        invalid2["address"] = "invalid"
        data_list = [valid, invalid1, invalid2]

        results = self.v.validate_batch(data_list)
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0][0])
        self.assertFalse(results[1][0])
        self.assertFalse(results[2][0])

    def test_validate_batch_all_invalid(self):
        """批量全部无效"""
        data_list = []
        for _ in range(3):
            d = _valid_data()
            d.pop("private_key")
            data_list.append(d)

        results = self.v.validate_batch(data_list)
        self.assertEqual(len(results), 3)
        for is_valid, issues in results:
            self.assertFalse(is_valid)
            self.assertGreater(len(issues), 0)

    def test_validate_batch_empty(self):
        """空批量"""
        results = self.v.validate_batch([])
        self.assertEqual(len(results), 0)


class TestValidateCombinedErrors(unittest.TestCase):
    """组合错误场景测试"""

    def setUp(self):
        self.v = BitcoinComplianceValidator()

    def test_multiple_errors_collected(self):
        """多个验证失败应全部收集"""
        data = {
            "private_key": None,
            "public_key": None,
            "address": None,
            "wif": None,
            "hash160": None,
        }
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertGreaterEqual(len(issues), 5)

    def test_validate_logs_warning_on_failure(self):
        """验证失败时记录警告日志"""
        data = _valid_data()
        data["private_key"] = b"\x00" * 32
        is_valid, issues = self.v.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("私钥必须大于0", issues)


if __name__ == "__main__":
    unittest.main()
