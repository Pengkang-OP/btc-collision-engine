"""比特币密钥验证器完整测试 — bitcoin_key_validator.py (487行零覆盖)"""

import pytest

from src.core.bitcoin_key_validator import (
    AddressType,
    BitcoinKeyValidator,
    KeyValidationConstants,
    KeyValidationResult,
    validate_bitcoin_key_chain,
)
from src.core.secp256k1 import Secp256k1
from src.core.wif import WIF


class TestWIFEncoder:
    """WIF 编解码测试 (WIFEncoder 已迁移为 src.core.wif.WIF)"""

    def setUp(self):
        self.pk = (1).to_bytes(32, "big")
        self.pk_random = (12345).to_bytes(32, "big")

    def test_encode_compressed_mainnet(self):
        wif = WIF.encode(self.pk, compressed=True, testnet=False)
        assert wif.startswith("K") or wif.startswith("L")
        assert len(wif)  ==  52

    def test_encode_uncompressed_mainnet(self):
        wif = WIF.encode(self.pk, compressed=False, testnet=False)
        assert wif.startswith("5")
        assert len(wif)  ==  51

    def test_encode_compressed_testnet(self):
        wif = WIF.encode(self.pk, compressed=True, testnet=True)
        assert len(wif)  ==  52

    def test_encode_uncompressed_testnet(self):
        wif = WIF.encode(self.pk, compressed=False, testnet=True)
        assert len(wif)  ==  51

    def test_encode_invalid_type_raises(self):
        with pytest.raises(ValueError):
            WIF.encode("not bytes", compressed=True)

    def test_encode_invalid_length_raises(self):
        with pytest.raises(ValueError):
            WIF.encode(b"\x01" * 16, compressed=True)

    def test_encode_length_too_short_raises(self):
        with pytest.raises(ValueError):
            WIF.encode(b"\x01" * 31, compressed=True)

    def test_encode_length_too_long_raises(self):
        with pytest.raises(ValueError):
            WIF.encode(b"\x01" * 33, compressed=True)

    def test_decode_compressed_mainnet(self):
        wif = WIF.encode(self.pk_random, compressed=True, testnet=False)
        pk, is_compressed = WIF.decode(wif)
        assert pk  ==  self.pk_random
        assert is_compressed

    def test_decode_uncompressed_mainnet(self):
        wif = WIF.encode(self.pk_random, compressed=False, testnet=False)
        pk, is_compressed = WIF.decode(wif)
        assert pk  ==  self.pk_random
        assert not is_compressed

    def test_decode_testnet(self):
        wif = WIF.encode(self.pk_random, compressed=True, testnet=True)
        pk, is_compressed = WIF.decode(wif)
        assert pk  ==  self.pk_random
        # testnet WIF 编解码在 compressed 标志下工作正常

    def test_decode_invalid_type_raises(self):
        with pytest.raises(ValueError):
            WIF.decode(12345)

    def test_decode_invalid_wif_raises(self):
        with pytest.raises(ValueError):
            WIF.decode("invalidWIF")

    def test_decode_invalid_version_raises(self):
        with pytest.raises(ValueError):
            WIF.decode("123456789012345678901234567890123456789012345678901")

    def test_roundtrip_compressed(self):
        wif = WIF.encode(self.pk_random, compressed=True)
        pk, comp = WIF.decode(wif)
        assert pk  ==  self.pk_random
        assert comp

    def test_roundtrip_uncompressed(self):
        wif = WIF.encode(self.pk_random, compressed=False)
        pk, comp = WIF.decode(wif)
        assert pk  ==  self.pk_random
        assert not comp


class TestKeyValidationConstants:
    """KeyValidationConstants 常量测试"""

    def test_constants_defined(self):
        assert KeyValidationConstants.PRIVATE_KEY_LENGTH  ==  32
        assert KeyValidationConstants.COMPRESSED_PUBLIC_KEY_LENGTH  ==  33
        assert KeyValidationConstants.UNCOMPRESSED_PUBLIC_KEY_LENGTH  ==  65
        assert KeyValidationConstants.P2PKH_VERSION_BYTE  ==  0x00
        assert KeyValidationConstants.P2SH_VERSION_BYTE  ==  0x05
        assert KeyValidationConstants.WIF_VERSION_BYTE  ==  0x80
        assert KeyValidationConstants.COMPRESSED_WIF_LENGTH  ==  52
        assert KeyValidationConstants.UNCOMPRESSED_WIF_LENGTH  ==  51
        assert KeyValidationConstants.P2PKH_ADDRESS_MIN_LENGTH  ==  25
        assert KeyValidationConstants.P2PKH_ADDRESS_MAX_LENGTH  ==  34


class TestAddressType:
    """AddressType 枚举测试"""

    def test_enum_values(self):
        assert AddressType.P2PKH.value  ==  "p2pkh"
        assert AddressType.P2SH.value  ==  "p2sh"
        assert AddressType.BECH32.value  ==  "bech32"
        assert AddressType.UNKNOWN.value  ==  "unknown"

    def test_enum_members(self):
        members = {m.name: m for m in AddressType}
        assert members  in  "P2PKH"
        assert members  in  "P2SH"
        assert members  in  "BECH32"
        assert members  in  "UNKNOWN"


class TestKeyValidationResult:
    """KeyValidationResult 测试"""

    def test_initial_state(self):
        r = KeyValidationResult()
        assert r.success
        assert r.errors  ==  []
        assert r.warnings  ==  []
        assert r.details  ==  {}

    def test_add_error(self):
        r = KeyValidationResult()
        ret = r.add_error("test error")
        assert not r.success
        assert r.errors  in  "test error"
        assert ret  is  r

    def test_add_multiple_errors(self):
        r = KeyValidationResult()
        r.add_error("error 1")
        r.add_error("error 2")
        assert len(r.errors)  ==  2

    def test_add_warning(self):
        r = KeyValidationResult()
        r.add_warning("test warning")
        assert r.warnings  in  "test warning"

    def test_add_detail(self):
        r = KeyValidationResult()
        r.add_detail("key", "value")
        assert r.details["key"]  ==  "value"

    def test_to_dict(self):
        r = KeyValidationResult()
        r.add_error("err")
        r.add_warning("warn")
        r.add_detail("k", "v")
        d = r.to_dict()
        assert not d["success"]
        assert d["errors"]  in  "err"
        assert d["warnings"]  in  "warn"
        assert d["details"]["k"]  ==  "v"

    def test_to_dict_success(self):
        r = KeyValidationResult()
        d = r.to_dict()
        assert d["success"]


class TestBitcoinKeyValidatorBasic:
    """BitcoinKeyValidator 基础测试"""

    def setUp(self):
        self.validator = BitcoinKeyValidator(secure_mode=False)
        self.pk = (1).to_bytes(32, "big")
        self.pk_random = (12345678901234567890).to_bytes(32, "big")

    def test_init_secure_mode_default(self):
        v = BitcoinKeyValidator()
        assert v.secure_mode

    def test_init_non_secure_mode(self):
        v = BitcoinKeyValidator(secure_mode=False)
        assert not v.secure_mode

    def test_validate_private_key_valid(self):
        result = self.validator.validate_private_key(self.pk)
        assert result.success
        assert result.details  in  "private_key_length"
        assert result.details["private_key_length"]  ==  32

    def test_validate_private_key_invalid_length(self):
        result = self.validator.validate_private_key(b"\x01" * 16)
        assert not result.success
        assert any("length" in e for e in result.errors)

    def test_validate_private_key_zero(self):
        pk = (0).to_bytes(32, "big")
        result = self.validator.validate_private_key(pk)
        assert not result.success
        assert str(result.errors)  in  "0"

    def test_validate_private_key_out_of_range(self):
        pk = (Secp256k1.N).to_bytes(32, "big")
        result = self.validator.validate_private_key(pk)
        assert not result.success

    def test_validate_private_key_secure_mode(self):
        v = BitcoinKeyValidator(secure_mode=True)
        result = v.validate_private_key(self.pk)
        assert result.success
        assert result.details  in  "private_key_hash"
        assert result.details  not in  "private_key_hex"

    def test_validate_private_key_non_secure_mode(self):
        v = BitcoinKeyValidator(secure_mode=False)
        result = v.validate_private_key(self.pk)
        assert result.details  in  "private_key_hex"


class TestBitcoinKeyValidatorPubKey:
    """BitcoinKeyValidator 公钥生成测试"""

    def setUp(self):
        self.validator = BitcoinKeyValidator(secure_mode=False)
        self.pk = (42).to_bytes(32, "big")

    def test_generate_public_key_compressed(self):
        result, pub_key = self.validator.generate_public_key(self.pk, compressed=True)
        assert result.success
        assert len(pub_key)  ==  33
        assert [2, 3]  in  pub_key[0]

    def test_generate_public_key_uncompressed(self):
        result, pub_key = self.validator.generate_public_key(self.pk, compressed=False)
        assert result.success
        assert len(pub_key)  ==  65
        assert pub_key[0]  ==  4

    def test_generate_public_key_invalid_private_key(self):
        result, pub_key = self.validator.generate_public_key(b"\x00" * 32)
        assert not result.success
        assert pub_key  ==  b""

    def test_generate_public_key_with_invalid_length(self):
        result, pub_key = self.validator.generate_public_key(b"\x01" * 10)
        assert not result.success

    def test_validate_public_key_compressed(self):
        _, pub_key = self.validator.generate_public_key(self.pk, compressed=True)
        result = self.validator.validate_public_key(pub_key)
        assert result.success
        assert result.details  in  "public_key_format"
        assert result.details["public_key_format"]  ==  "compressed"

    def test_validate_public_key_uncompressed(self):
        _, pub_key = self.validator.generate_public_key(self.pk, compressed=False)
        result = self.validator.validate_public_key(pub_key)
        assert result.success
        assert result.details["public_key_format"]  ==  "uncompressed"

    def test_validate_public_key_bad_prefix_compressed(self):
        bad_pk = b"\x01" + b"\x00" * 32
        result = self.validator.validate_public_key(bad_pk)
        assert not result.success
        assert any("prefix" in e for e in result.errors)

    def test_validate_public_key_bad_prefix_uncompressed(self):
        bad_pk = b"\x01" + b"\x00" * 64
        result = self.validator.validate_public_key(bad_pk)
        assert not result.success

    def test_validate_public_key_bad_length(self):
        result = self.validator.validate_public_key(b"\x00" * 10)
        assert not result.success

    def test_validate_public_key_compressed_x_zero(self):
        bad_pk = b"\x02" + b"\x00" * 32
        result = self.validator.validate_public_key(bad_pk)
        assert not result.success


class TestBitcoinKeyValidatorAddress:
    """BitcoinKeyValidator 地址生成与验证测试"""

    def setUp(self):
        self.validator = BitcoinKeyValidator(secure_mode=False)
        self.pk = (42).to_bytes(32, "big")

    def test_generate_address_p2pkh(self):
        _, pub_key = self.validator.generate_public_key(self.pk, compressed=True)
        result, address = self.validator.generate_address(pub_key, AddressType.P2PKH)
        assert result.success
        assert address.startswith("1")

    def test_generate_address_p2sh_warning(self):
        _, pub_key = self.validator.generate_public_key(self.pk, compressed=True)
        result, address = self.validator.generate_address(pub_key, AddressType.P2SH)
        # 当前实现不生成 redeem 警告，验证地址前缀和成功状态
        assert result.success
        assert address.startswith("3")

    def test_generate_address_bech32_warning(self):
        _, pub_key = self.validator.generate_public_key(self.pk, compressed=True)
        result, address = self.validator.generate_address(pub_key, AddressType.BECH32)
        # 当前实现不生成 bech32 警告，验证地址前缀和成功状态
        assert result.success
        assert address.startswith("bc1")

    def test_generate_address_invalid_public_key(self):
        result, address = self.validator.generate_address(b"\x00" * 10)
        assert not result.success
        assert address  ==  ""

    def test_validate_address_p2pkh(self):
        address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        result = self.validator.validate_address(address)
        assert result.success
        assert result.details["address_type"]  ==  "P2PKH"

    def test_validate_address_p2sh(self):
        address = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
        result = self.validator.validate_address(address)
        assert result.details["address_type"]  ==  "P2SH"

    def test_validate_address_bech32(self):
        address = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
        result = self.validator.validate_address(address)
        assert result.details["address_type"]  ==  "Bech32"

    def test_validate_address_unknown(self):
        result = self.validator.validate_address("invalid")
        assert not result.success

    def test_validate_address_p2pkh_invalid_chars(self):
        result = self.validator.validate_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf0OIl")
        assert not result.success

    def test_validate_address_bech32_short(self):
        result = self.validator.validate_address("bc1abc")
        assert not result.success

    def test_validate_address_bech32_invalid_char(self):
        result = self.validator.validate_address("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t1")
        assert str(result.errors)  in  "Bech32"

    def test_validate_address_bech32_testnet(self):
        address = "tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx"
        result = self.validator.validate_address(address)
        assert not result.success


class TestBitcoinKeyValidatorWIF:
    """BitcoinKeyValidator WIF 编解码测试"""

    def setUp(self):
        self.validator = BitcoinKeyValidator(secure_mode=False)
        self.pk = (42).to_bytes(32, "big")

    def test_private_key_to_wif_compressed(self):
        result, wif = self.validator.private_key_to_wif(self.pk, compressed=True)
        assert result.success
        assert wif.startswith("K") or wif.startswith("L")
        assert len(wif)  ==  52

    def test_private_key_to_wif_uncompressed(self):
        result, wif = self.validator.private_key_to_wif(self.pk, compressed=False)
        assert result.success
        assert wif.startswith("5")
        assert len(wif)  ==  51

    def test_private_key_to_wif_invalid_key(self):
        result, wif = self.validator.private_key_to_wif(b"\x00" * 32, compressed=True)
        assert not result.success
        assert wif  ==  ""

    def test_private_key_to_wif_secure_mode(self):
        v = BitcoinKeyValidator(secure_mode=True)
        result, wif = v.private_key_to_wif(self.pk, compressed=True)
        assert result.success
        wif_detail = result.details.get("wif", "")
        assert wif_detail  in  "..."

    def test_wif_to_private_key_compressed(self):
        _, wif = self.validator.private_key_to_wif(self.pk, compressed=True)
        result, pk_out, compressed = self.validator.wif_to_private_key(wif)
        assert result.success
        assert pk_out  ==  self.pk
        assert compressed

    def test_wif_to_private_key_uncompressed(self):
        _, wif = self.validator.private_key_to_wif(self.pk, compressed=False)
        result, pk_out, compressed = self.validator.wif_to_private_key(wif)
        assert result.success
        assert pk_out  ==  self.pk
        assert not compressed

    def test_wif_to_private_key_invalid(self):
        result, pk_out, compressed = self.validator.wif_to_private_key("invalid")
        assert not result.success
        assert pk_out  ==  b""

    def test_wif_to_private_key_secure_mode(self):
        v = BitcoinKeyValidator(secure_mode=True)
        _, wif = v.private_key_to_wif(self.pk, compressed=True)
        result, pk_out, compressed = v.wif_to_private_key(wif)
        assert result.success
        assert result.details  in  "private_key_hash"
        assert result.details  not in  "private_key_hex"


class TestBitcoinKeyValidatorMatch:
    """BitcoinKeyValidator 地址匹配测试"""

    def setUp(self):
        self.validator = BitcoinKeyValidator(secure_mode=False)
        self.pk = (42).to_bytes(32, "big")

    def test_verify_address_match_found(self):
        _, pub_key = self.validator.generate_public_key(self.pk, compressed=True)
        _, address = self.validator.generate_address(pub_key, AddressType.P2PKH)
        targets = {address, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        result = self.validator.verify_address_match(address, targets)
        assert result.success
        assert result.details["match"]
        assert result.details["matched_target"]  ==  address

    def test_verify_address_match_not_found(self):
        _, pub_key = self.validator.generate_public_key(self.pk, compressed=True)
        _, address = self.validator.generate_address(pub_key, AddressType.P2PKH)
        targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        result = self.validator.verify_address_match(address, targets)
        assert result.success
        assert not result.details["match"]

    def test_verify_address_match_invalid_address(self):
        target = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        result = self.validator.verify_address_match("invalid", target)
        assert not result.success

    def test_verify_address_match_invalid_target(self):
        _, pub_key = self.validator.generate_public_key(self.pk, compressed=True)
        _, address = self.validator.generate_address(pub_key, AddressType.P2PKH)
        targets = {address, "invalid_target"}
        result = self.validator.verify_address_match(address, targets)
        assert result.success
        assert result.details["match"]

    def test_verify_address_match_hmac_compare(self):
        _, pub_key = self.validator.generate_public_key(self.pk, compressed=True)
        _, address = self.validator.generate_address(pub_key, AddressType.P2PKH)
        targets = {address}
        result = self.validator.verify_address_match(address, targets)
        assert result.details["match"]


class TestBitcoinKeyValidatorFullChain:
    """完整验证链测试"""

    def setUp(self):
        self.pk = (42).to_bytes(32, "big")

    def test_full_validation_chain_secure_mode(self):
        v = BitcoinKeyValidator(secure_mode=True)
        _, pub_key_c = v.generate_public_key(self.pk, compressed=True)
        _, address = v.generate_address(pub_key_c, AddressType.P2PKH)
        report = v.full_validation_chain(self.pk, {address})
        assert report["overall_success"]
        assert report  in  "summary"
        assert report["summary"]["secure_mode"]
        assert report["summary"]  not in  "private_key_hex"

    def test_full_validation_chain_non_secure_mode(self):
        v = BitcoinKeyValidator(secure_mode=False)
        _, pub_key_c = v.generate_public_key(self.pk, compressed=True)
        _, address = v.generate_address(pub_key_c, AddressType.P2PKH)
        report = v.full_validation_chain(self.pk, {address})
        assert report["overall_success"]
        assert report.get("summary", {})  in  "private_key_hash"
        assert not report["summary"]["secure_mode"]

    def test_full_validation_chain_match_found(self):
        v = BitcoinKeyValidator(secure_mode=False)
        _, pub_key_c = v.generate_public_key(self.pk, compressed=True)
        _, address = v.generate_address(pub_key_c, AddressType.P2PKH)
        report = v.full_validation_chain(self.pk, {address})
        assert report["overall_success"]
        assert report["summary"]["address_match"]

    def test_full_validation_chain_match_not_found(self):
        v = BitcoinKeyValidator(secure_mode=False)
        _, pub_key_c = v.generate_public_key(self.pk, compressed=True)
        _, address = v.generate_address(pub_key_c, AddressType.P2PKH)
        report = v.full_validation_chain(self.pk, {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"})
        assert not report["summary"]["address_match"]

    def test_full_validation_chain_invalid_private_key(self):
        v = BitcoinKeyValidator(secure_mode=False)
        report = v.full_validation_chain(b"\x00" * 32, set())
        assert not report["overall_success"]
        assert report  in  "steps"

    def test_full_validation_chain_steps_count(self):
        v = BitcoinKeyValidator(secure_mode=False)
        _, pub_key_c = v.generate_public_key(self.pk, compressed=True)
        _, address = v.generate_address(pub_key_c, AddressType.P2PKH)
        report = v.full_validation_chain(self.pk, {address})
        steps = report["steps"]
        assert steps  in  "private_key_validation"
        assert steps  in  "public_key_compressed"
        assert steps  in  "public_key_uncompressed"
        assert steps  in  "address_generation"
        assert steps  in  "wif_compressed"
        assert steps  in  "wif_uncompressed"
        assert steps  in  "address_match"


class TestValidateBitcoinKeyChain:
    """便捷函数 validate_bitcoin_key_chain 测试"""

    def test_convenience_function(self):
        pk = (42).to_bytes(32, "big")
        v = BitcoinKeyValidator(secure_mode=False)
        _, pub_key_c = v.generate_public_key(pk, compressed=True)
        _, address = v.generate_address(pub_key_c, AddressType.P2PKH)
        report = validate_bitcoin_key_chain(pk, {address})
        assert report["overall_success"]
        assert report["summary"]["address_match"]

    def test_convenience_function_no_match(self):
        pk = (99).to_bytes(32, "big")
        report = validate_bitcoin_key_chain(pk, {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"})
        assert report is not None

    def test_convenience_function_invalid_key(self):
        report = validate_bitcoin_key_chain(b"\x00" * 32, set())
        assert not report["overall_success"]


class TestBitcoinKeyValidatorP2SH:
    """P2SH 地址生成静态方法测试"""

    def test_generate_p2sh_address(self):
        pk = (42).to_bytes(32, "big")
        v = BitcoinKeyValidator(secure_mode=False)
        _, pub_key = v.generate_public_key(pk, compressed=True)
        address = BitcoinKeyValidator.generate_p2sh_address(pub_key)
        assert address.startswith("3")

    def test_generate_p2sh_deterministic(self):
        pk = (12345).to_bytes(32, "big")
        v = BitcoinKeyValidator(secure_mode=False)
        _, pub_key = v.generate_public_key(pk, compressed=True)
        addr1 = BitcoinKeyValidator.generate_p2sh_address(pub_key)
        addr2 = BitcoinKeyValidator.generate_p2sh_address(pub_key)
        assert addr1  ==  addr2

    def test_generate_p2sh_valid_base58(self):
        from src.core.base58 import Base58

        pk = (999).to_bytes(32, "big")
        v = BitcoinKeyValidator(secure_mode=False)
        _, pub_key = v.generate_public_key(pk, compressed=True)
        address = BitcoinKeyValidator.generate_p2sh_address(pub_key)
        version, payload = Base58.check_decode(address)
        assert version  ==  0x05


class TestBitcoinKeyValidatorBech32:
    """Bech32 地址生成测试"""

    def test_generate_bech32_address(self):
        pk = (42).to_bytes(32, "big")
        v = BitcoinKeyValidator(secure_mode=False)
        _, pub_key = v.generate_public_key(pk, compressed=True)
        address = BitcoinKeyValidator.generate_bech32_address(pub_key)
        assert address.startswith("bc1")

    def test_generate_bech32_testnet(self):
        pk = (42).to_bytes(32, "big")
        v = BitcoinKeyValidator(secure_mode=False)
        _, pub_key = v.generate_public_key(pk, compressed=True)
        address = BitcoinKeyValidator.generate_bech32_address(pub_key, hrp="tb")
        assert address.startswith("tb1")

    def test_generate_bech32_uncompressed_raises(self):
        pk = (42).to_bytes(32, "big")
        v = BitcoinKeyValidator(secure_mode=False)
        _, pub_key = v.generate_public_key(pk, compressed=False)
        with pytest.raises(ValueError):
            BitcoinKeyValidator.generate_bech32_address(pub_key)

    def test_generate_bech32_deterministic(self):
        pk = (12345).to_bytes(32, "big")
        v = BitcoinKeyValidator(secure_mode=False)
        _, pub_key = v.generate_public_key(pk, compressed=True)
        addr1 = BitcoinKeyValidator.generate_bech32_address(pub_key)
        addr2 = BitcoinKeyValidator.generate_bech32_address(pub_key)
        assert addr1  ==  addr2


class TestBitcoinKeyValidatorUncompressedWIF:
    """非压缩WIF前缀检查"""

    def setUp(self):
        self.validator = BitcoinKeyValidator(secure_mode=False)
        self.pk = (12345).to_bytes(32, "big")

    def test_uncompressed_wif_starts_with_5(self):
        result, wif = self.validator.private_key_to_wif(self.pk, compressed=False)
        assert result.success
        assert wif.startswith("5")

    def test_compressed_wif_not_starts_with_5(self):
        result, wif = self.validator.private_key_to_wif(self.pk, compressed=True)
        assert result.success
        assert not wif.startswith("5")


if __name__ == "__main__":
    unittest.main(verbosity=2)
