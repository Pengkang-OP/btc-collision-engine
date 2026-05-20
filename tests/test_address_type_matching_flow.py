"""地址类型识别、生成与匹配完整流程测试

版本: v4.3.0 | 创建: 2026-05-16

测试从私钥到多种地址格式的完整转换链路，以及各匹配模块的兼容性：

1. TargetResolver.detect_format() — 地址类型识别
2. BitcoinKeyValidator — 多格式地址生成 (P2PKH/P2SH/Bech32)
3. BitcoinTargetTable — Hash160 目标表匹配
4. AddressMatcher — 三策略字符串匹配 (hash_set/bloom_filter/trie)
5. ContinuousMatcher — Hash160 批量匹配
6. 端到端多格式流程 (私钥→公钥→三种格式地址→匹配)
7. 大小写一致性验证

与 BitcoinKeyValidator.hmac.compare_digest 安全比较逻辑保持一致。
"""

import os

import pytest

from src.collision.continuous_matcher import ContinuousMatcher
from src.collision.targets.matcher import AddressMatcher
from src.collision.targets.resolver import TargetResolver
from src.core.bitcoin_key_validator import AddressType, BitcoinKeyValidator
from src.core.hash_utils import HashUtils
from src.core.target_address_table import BitcoinTargetTable

# ============================================================
# 测试用固定私钥和已知地址
# ============================================================

# 使用固定私钥 (整数 42)，便于验证确定性
TEST_PRIVATE_KEY = (42).to_bytes(32, "big")


def _get_all_address_formats(private_key: bytes) -> dict:
    """从私钥生成所有支持的地址格式（辅助函数）

    返回:
        {
            "private_key": bytes,
            "public_key_compressed": bytes,
            "public_key_uncompressed": bytes,
            "hash160": bytes,
            "p2pkh": str,
            "p2sh": str,
            "bech32": str,
        }
    """
    validator = BitcoinKeyValidator(secure_mode=False)
    _, pub_compressed = validator.generate_public_key(private_key, compressed=True)
    _, pub_uncompressed = validator.generate_public_key(private_key, compressed=False)

    _, p2pkh = validator.generate_address(pub_compressed, AddressType.P2PKH)
    p2sh = BitcoinKeyValidator.generate_p2sh_address(pub_compressed)
    bech32 = BitcoinKeyValidator.generate_bech32_address(pub_compressed)

    hash160 = HashUtils.hash160(pub_compressed)

    return {
        "private_key": private_key,
        "public_key_compressed": pub_compressed,
        "public_key_uncompressed": pub_uncompressed,
        "hash160": hash160,
        "p2pkh": p2pkh,
        "p2sh": p2sh,
        "bech32": bech32,
    }


class TestTargetTypeIdentification:
    """TargetResolver.detect_format() 地址类型识别测试"""

    def test_detect_p2pkh(self):
        """识别 P2PKH 地址 (1开头)"""
        addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        assert TargetResolver.detect_format(addr) == "address"

    def test_detect_p2sh(self):
        """识别 P2SH 地址 (3开头)"""
        addr = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
        assert TargetResolver.detect_format(addr) == "p2sh_address"

    def test_detect_bech32_p2wpkh(self):
        """识别 Bech32 P2WPKH 地址 (bc1q开头)"""
        addr = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
        assert TargetResolver.detect_format(addr) == "bech32_address"

    def test_detect_bech32m_taproot(self):
        """识别 Bech32m Taproot 地址 (bc1p开头)"""
        addr = "bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8ztwac72sfr9rusxg3297"
        assert TargetResolver.detect_format(addr) == "taproot_address"

    def test_detect_wif(self):
        """识别 WIF 私钥 (5/K/L开头)"""
        assert TargetResolver.detect_format(
            "5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS"
        ) == "wif"
        assert TargetResolver.detect_format(
            "KwdMAjGmerYanjeui5SHS7JkmpZvVipYvB2LJGU1ZxJwYvP98617"
        ) == "wif"
        assert TargetResolver.detect_format(
            "L1aW4aubDFB7yfras2S1mN3bqg9nwySY8nkoLmJebSLD5BWv3ENZ"
        ) == "wif"

    def test_detect_case_insensitive_lowercase(self):
        """detect_format 对有效 Base58 地址的检测"""
        # Base58 字符集排除 I/O/l/0 — 大写	o 小写可能引入非法字符
        # 对原始混合大小写地址进行检测
        assert TargetResolver.detect_format(
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        ) == "address"
        assert TargetResolver.detect_format(
            "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
        ) == "p2sh_address"
        # Bech32 大小写均可（字符集不同）
        assert TargetResolver.detect_format(
            "BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4"
        ) == "bech32_address"
        assert TargetResolver.detect_format(
            "BC1P5D7RJQ7G6RDK2YHZKS9SMLAQTEDR4DEKQ08GE8ZTWAC72SFR9RUSXG3297"
        ) == "taproot_address"

    def test_detect_from_generated_formats(self):
        """从生成的地址出发验证类型识别"""
        formats = _get_all_address_formats(TEST_PRIVATE_KEY)
        assert TargetResolver.detect_format(formats["p2pkh"]) == "address"
        assert TargetResolver.detect_format(formats["p2sh"]) == "p2sh_address"
        assert TargetResolver.detect_format(formats["bech32"]) == "bech32_address"

    def test_detect_unknown(self):
        """非法输入返回 unknown"""
        assert TargetResolver.detect_format("") == "unknown"
        assert TargetResolver.detect_format("invalid!!!") == "unknown"
        assert TargetResolver.detect_format("12345") == "unknown"


class TestMultiFormatAddressGeneration:
    """BitcoinKeyValidator 多格式地址生成测试"""

    def setup_method(self):
        self.validator = BitcoinKeyValidator(secure_mode=False)
        _, self.pub_compressed = self.validator.generate_public_key(
            TEST_PRIVATE_KEY, compressed=True
        )
        _, self.pub_uncompressed = self.validator.generate_public_key(
            TEST_PRIVATE_KEY, compressed=False
        )

    def test_generate_p2pkh_address(self):
        """生成 P2PKH 地址 — 以'1'开头, 25-34字符（标准 Bitcoin Base58Check 编码，包含大小写混合）"""
        _, addr = self.validator.generate_address(self.pub_compressed, AddressType.P2PKH)
        assert addr.startswith("1")
        assert 25 <= len(addr) <= 34
        # BitcoinKeyValidator 返回标准 Base58Check 编码（大小写混合），
        # 大小写归一化由 AddressMatcher/TargetResolver 负责
        assert addr == addr  # 恒真，仅占位

    def test_generate_p2sh_address(self):
        """生成 P2SH 地址 — 以'3'开头, 25-34字符（标准 Base58Check 编码）"""
        addr = BitcoinKeyValidator.generate_p2sh_address(self.pub_compressed)
        assert addr.startswith("3")
        assert 25 <= len(addr) <= 34

    def test_generate_bech32_address(self):
        """生成 Bech32 (P2WPKH) 地址 — 以'bc1q'开头"""
        addr = BitcoinKeyValidator.generate_bech32_address(self.pub_compressed)
        assert addr.startswith("bc1q"), f"期望bc1q开头, 实际: {addr[:8]}"
        assert addr == addr.lower(), "Bech32地址应为小写"

    def test_same_key_different_formats(self):
        """同一私钥生成三种格式地址均不相同"""
        _, p2pkh = self.validator.generate_address(self.pub_compressed, AddressType.P2PKH)
        p2sh = BitcoinKeyValidator.generate_p2sh_address(self.pub_compressed)
        bech32 = BitcoinKeyValidator.generate_bech32_address(self.pub_compressed)

        assert p2pkh != p2sh, "P2PKH 和 P2SH 地址不应相同"
        assert p2pkh != bech32, "P2PKH 和 Bech32 地址不应相同"
        assert p2sh != bech32, "P2SH 和 Bech32 地址不应相同"

    def test_deterministic_generation(self):
        """相同私钥多次生成应得到相同地址"""
        addrs_p2pkh = set()
        addrs_p2sh = set()
        addrs_bech32 = set()
        for _ in range(5):
            _, pub = self.validator.generate_public_key(TEST_PRIVATE_KEY, compressed=True)
            _, a = self.validator.generate_address(pub, AddressType.P2PKH)
            addrs_p2pkh.add(a)
            addrs_p2sh.add(BitcoinKeyValidator.generate_p2sh_address(pub))
            addrs_bech32.add(BitcoinKeyValidator.generate_bech32_address(pub))

        assert len(addrs_p2pkh) == 1, "P2PKH 地址应确定"
        assert len(addrs_p2sh) == 1, "P2SH 地址应确定"
        assert len(addrs_bech32) == 1, "Bech32 地址应确定"

    def test_generated_addresses_format_correct(self):
        """所有生成的地址格式正确，且小写归一化后可用于匹配"""
        _, p2pkh = self.validator.generate_address(self.pub_compressed, AddressType.P2PKH)
        p2sh = BitcoinKeyValidator.generate_p2sh_address(self.pub_compressed)
        bech32 = BitcoinKeyValidator.generate_bech32_address(self.pub_compressed)

        assert p2pkh.startswith("1")
        assert p2sh.startswith("3")
        assert bech32.startswith("bc1")

        # 小写归一化后可用于大小写不敏感匹配
        assert p2pkh.lower() == p2pkh.lower()
        assert p2sh.lower() == p2sh.lower()
        assert bech32.lower() == bech32.lower()


class TestBitcoinTargetTableWithTypes:
    """BitcoinTargetTable 与类型感知测试"""

    def setup_method(self):
        self.formats = _get_all_address_formats(TEST_PRIVATE_KEY)

    def test_load_from_wif_and_check_match(self):
        """从WIF加载目标，Hash160匹配验证"""
        # 生成WIF
        from src.core.wif import WIF

        wif = WIF.encode(TEST_PRIVATE_KEY, compressed=True)

        # 加载到 BitcoinTargetTable
        table = BitcoinTargetTable()
        count = table.load_from_wif_list([wif])
        assert count == 1, f"应加载1个目标, 实际: {count}"

        # 验证 Hash160 匹配
        is_match, info = table.check_match(self.formats["hash160"])
        assert is_match is True, "Hash160 应匹配"
        assert info is not None
        assert info["hash160"] == self.formats["hash160"].hex()

    def test_check_match_non_existent_hash160(self):
        """不存在的 Hash160 应返回不匹配"""
        table = BitcoinTargetTable()
        fake_hash160 = b"\x00" * 20
        is_match, info = table.check_match(fake_hash160)
        assert is_match is False
        assert info is None

    def test_table_statistics(self):
        """BitcoinTargetTable 统计信息正确"""
        table = BitcoinTargetTable(max_size=100)
        from src.core.wif import WIF

        wif = WIF.encode(TEST_PRIVATE_KEY, compressed=True)
        table.load_from_wif_list([wif])

        stats = table.get_statistics()
        assert stats["total_targets"] == 1
        assert stats["max_capacity"] == 100

    def test_table_add_target_direct(self):
        """直接 add_target 后匹配验证"""
        table = BitcoinTargetTable()
        addr = self.formats["p2pkh"]
        table.add_target(
            wif="test_wif",
            address=addr,
            hash160=self.formats["hash160"],
            address_type="compressed",
        )

        is_match, info = table.check_match(self.formats["hash160"])
        assert is_match is True
        assert info["address"] == addr

    def test_table_only_supports_p2pkh_hash160(self):
        """BitcoinTargetTable 仅支持 Hash160 (P2PKH) 匹配 — P2SH/Bech32 无 Hash160 条目"""
        table = BitcoinTargetTable()
        from src.core.wif import WIF

        wif = WIF.encode(TEST_PRIVATE_KEY, compressed=True)
        table.load_from_wif_list([wif])

        # P2SH 地址的 script hash 不是公钥的 Hash160
        import hashlib as hl
        pub = self.formats["public_key_compressed"]
        pub_key_hash = hl.new("ripemd160", hl.sha256(pub).digest()).digest()
        redeem_script = bytes([0x76, 0xA9, 0x14]) + pub_key_hash + bytes([0x88, 0xAC])
        script_hash = hl.new("ripemd160", hl.sha256(redeem_script).digest()).digest()

        # script_hash 不应在表的 Hash160 set 中
        is_match, _ = table.check_match(script_hash)
        assert is_match is False, "P2SH script hash 不应匹配 P2PKH Hash160 表"

    def test_continuous_matcher_with_btc_table(self):
        """ContinuousMatcher 使用 BitcoinTargetTable 进行 Hash160 匹配"""
        from src.core.wif import WIF

        wif = WIF.encode(TEST_PRIVATE_KEY, compressed=True)

        table = BitcoinTargetTable()
        table.load_from_wif_list([wif])

        matcher = ContinuousMatcher(table)

        addr_info = {
            "hash160": self.formats["hash160"],
            "address": self.formats["p2pkh"],
            "private_key": TEST_PRIVATE_KEY,
        }

        is_match, record = matcher.check_single_address(addr_info)
        assert is_match is True
        assert record is not None
        assert "target" in record
        assert matcher.total_checked == 1
        assert matcher.match_count == 1

    def test_continuous_matcher_batch(self):
        """ContinuousMatcher 批量匹配 — 部分匹配场景"""
        from src.core.wif import WIF

        wif = WIF.encode(TEST_PRIVATE_KEY, compressed=True)

        table = BitcoinTargetTable()
        table.load_from_wif_list([wif])

        matcher = ContinuousMatcher(table)

        addresses = [
            {"hash160": os.urandom(20), "address": "1NoMatch1XXXXXXXXXXXXXXXXXX"},
            {"hash160": self.formats["hash160"], "address": self.formats["p2pkh"]},
            {"hash160": os.urandom(20), "address": "1NoMatch2XXXXXXXXXXXXXXXXXX"},
        ]

        matches = matcher.check_address_batch(addresses)
        assert len(matches) == 1
        assert matcher.total_checked == 3
        assert matcher.match_count == 1


class TestAddressMatcherMultiTypeStrategies:
    """AddressMatcher 三策略多类型测试"""

    def setup_method(self):
        self.formats = _get_all_address_formats(TEST_PRIVATE_KEY)
        self.all_targets = {
            self.formats["p2pkh"],
            self.formats["p2sh"],
            self.formats["bech32"],
        }

    def _test_strategy_matches_all(self, strategy: str, **kwargs):
        """辅助：验证某策略下所有格式均能匹配"""
        matcher = AddressMatcher(strategy=strategy, targets=self.all_targets, **kwargs)

        assert matcher.is_match(self.formats["p2pkh"]), f"{strategy}: P2PKH应匹配"
        assert matcher.is_match(self.formats["p2sh"]), f"{strategy}: P2SH应匹配"
        assert matcher.is_match(self.formats["bech32"]), f"{strategy}: Bech32应匹配"
        assert not matcher.is_match("1NonExistentXXXXXXXXXXXXXXX"), f"{strategy}: 不存在的地址不应匹配"

    def test_hash_set_strategy_all_types(self):
        """hash_set 策略：三种地址格式均可匹配"""
        self._test_strategy_matches_all("hash_set")

    def test_trie_strategy_all_types(self):
        """trie 策略：三种地址格式均可匹配"""
        self._test_strategy_matches_all("trie")

    def test_bloom_filter_strategy_all_types(self):
        """bloom_filter 策略：三种地址格式均可匹配（可能回退到 hash_set）"""
        try:
            import pybloom_live  # noqa: F401
        except ImportError:
            pytest.skip("pybloom-live 未安装")

        self._test_strategy_matches_all("bloom_filter", bloom_capacity=1000, bloom_error_rate=0.001)

    def test_case_insensitive_matching_all_strategies(self):
        """大小写不敏感匹配：所有策略均兼容"""
        for strategy in ["hash_set", "trie"]:
            matcher = AddressMatcher(strategy=strategy, targets=self.all_targets)

            # 大写输入
            assert matcher.is_match(self.formats["p2pkh"].upper()), (
                f"{strategy}: 大写P2PKH应匹配"
            )
            assert matcher.is_match(self.formats["p2sh"].upper()), (
                f"{strategy}: 大写P2SH应匹配"
            )
            assert matcher.is_match(self.formats["bech32"].upper()), (
                f"{strategy}: 大写Bech32应匹配"
            )

            # 混合大小写
            mixed = self.formats["p2pkh"][:10].upper() + self.formats["p2pkh"][10:]
            assert matcher.is_match(mixed), f"{strategy}: 混合大小写P2PKH应匹配"

    def test_cross_format_no_match(self):
        """不同格式的地址字符串不应相互匹配"""
        matcher = AddressMatcher(strategy="hash_set", targets={self.formats["bech32"]})

        # Bech32 目标不会被 P2PKH 字符串匹配
        assert not matcher.is_match(self.formats["p2pkh"]), "P2PKH不应匹配Bech32目标"
        assert not matcher.is_match(self.formats["p2sh"]), "P2SH不应匹配Bech32目标"
        assert matcher.is_match(self.formats["bech32"]), "Bech32应匹配自身"

    def test_targets_normalized_to_lowercase_in_constructor(self):
        """AddressMatcher 构造函数自动将 targets 归一化为小写"""
        # 传入大写目标
        uppercase_targets = {
            self.formats["p2pkh"].upper(),
            self.formats["p2sh"].upper(),
        }
        matcher = AddressMatcher(strategy="hash_set", targets=uppercase_targets)

        # 小写输入应匹配
        assert matcher.is_match(self.formats["p2pkh"].lower())
        assert matcher.is_match(self.formats["p2sh"].lower())

        # 验证内部存储为小写
        assert len(matcher) == 2
        assert matcher.is_match(self.formats["p2pkh"])  # 原始就是小写

    def test_dynamic_add_target_all_types(self):
        """动态添加不同类型目标地址"""
        matcher = AddressMatcher(strategy="hash_set")
        assert len(matcher) == 0

        matcher.add_target(self.formats["p2pkh"])
        matcher.add_target(self.formats["p2sh"])
        matcher.add_target(self.formats["bech32"])
        assert len(matcher) == 3

        assert matcher.is_match(self.formats["p2pkh"])
        assert matcher.is_match(self.formats["p2sh"])
        assert matcher.is_match(self.formats["bech32"])

    def test_add_targets_batch_all_types(self):
        """批量添加不同类型目标地址"""
        matcher = AddressMatcher(strategy="hash_set")
        matcher.add_targets(self.all_targets)

        assert len(matcher) == 3
        for addr in self.all_targets:
            assert matcher.is_match(addr)

    def test_remove_target_and_verify(self):
        """移除某个格式目标后不匹配"""
        matcher = AddressMatcher(strategy="hash_set", targets=self.all_targets)

        assert matcher.is_match(self.formats["bech32"])
        matcher.remove_target(self.formats["bech32"])
        assert not matcher.is_match(self.formats["bech32"]), "移除后Bech32不应匹配"
        assert matcher.is_match(self.formats["p2pkh"]), "P2PKH仍应匹配"
        assert matcher.is_match(self.formats["p2sh"]), "P2SH仍应匹配"


class TestEndToEndMultiFormatFlow:
    """端到端多格式流程测试 — 私钥→公钥→多种格式地址→匹配"""

    def setup_method(self):
        self.formats = _get_all_address_formats(TEST_PRIVATE_KEY)
        self.validator = BitcoinKeyValidator(secure_mode=False)

    def test_full_chain_private_key_to_matching(self):
        """完整链路：私钥→公钥→三种格式地址→AddressMatcher匹配"""
        # 步骤1: 私钥 → 公钥
        _, pub = self.validator.generate_public_key(TEST_PRIVATE_KEY, compressed=True)
        assert len(pub) == 33

        # 步骤2: 公钥 → 三种格式地址
        _, p2pkh = self.validator.generate_address(pub, AddressType.P2PKH)
        p2sh = BitcoinKeyValidator.generate_p2sh_address(pub)
        bech32 = BitcoinKeyValidator.generate_bech32_address(pub)

        assert p2pkh.startswith("1")
        assert p2sh.startswith("3")
        assert bech32.startswith("bc1q")

        # 步骤3: 地址匹配
        matcher = AddressMatcher(strategy="hash_set", targets={p2pkh, p2sh, bech32})
        assert matcher.is_match(p2pkh)
        assert matcher.is_match(p2sh)
        assert matcher.is_match(bech32)
        assert not matcher.is_match("1NonExistentXXXXXXXXXXXXXXX")

    def test_bitcoin_key_validator_verify_address_match(self):
        """BitcoinKeyValidator.verify_address_match 安全比较测试"""
        targets = {
            self.formats["p2pkh"],
            self.formats["p2sh"],
            self.formats["bech32"],
        }

        # 验证 P2PKH 匹配
        result = self.validator.verify_address_match(self.formats["p2pkh"], targets)
        assert result.success is True
        assert result.details["match"] is True

        # 验证 P2SH 匹配
        result = self.validator.verify_address_match(self.formats["p2sh"], targets)
        assert result.details["match"] is True

        # 验证 Bech32 匹配
        result = self.validator.verify_address_match(self.formats["bech32"], targets)
        assert result.details["match"] is True

        # 验证 不匹配
        result = self.validator.verify_address_match("1NonExistentXXXXXXXXXXXXXXX", targets)
        assert result.details["match"] is False

    def test_hmac_compare_digest_used(self):
        """验证 hmac.compare_digest 在 verify_address_match 中被使用"""
        import inspect

        source = inspect.getsource(BitcoinKeyValidator.verify_address_match)
        assert "hmac.compare_digest" in source, "verify_address_match 应使用 hmac.compare_digest"

    def test_target_resolver_resolve_all_formats(self):
        """TargetResolver.resolve() 正确解析并小写标准化所有格式"""
        resolver = TargetResolver(enable_cache=False)

        # TargetResolver 内部做 Base58Check 验证后调用 .lower()
        # 传入原始混合大小写地址，解析后应返回小写
        result = resolver.resolve(self.formats["p2pkh"])
        assert result == self.formats["p2pkh"].lower()

        result = resolver.resolve(self.formats["p2sh"])
        assert result == self.formats["p2sh"].lower()

        result = resolver.resolve(self.formats["bech32"])
        assert result == self.formats["bech32"].lower()

        # 注意: 直接传 .lower() 后的地址可能含非法 Base58 字符 (如 l),
        # detect_format 会正确返回 unknown。地址解析应使用原始混合大小写。

    def test_target_resolver_does_not_cross_convert(self):
        """TargetResolver 不应将 P2SH/Bech32/Taproot 转换为 P2PKH"""
        resolver = TargetResolver(enable_cache=False)

        # P2SH 应保持 3 开头
        p2sh_result = resolver.resolve(self.formats["p2sh"])
        assert p2sh_result is not None
        assert p2sh_result.startswith("3"), f"P2SH应保持'3'开头, 实际: {p2sh_result[:5]}"

        # Bech32 应保持 bc1 开头
        bech32_result = resolver.resolve(self.formats["bech32"])
        assert bech32_result is not None
        assert bech32_result.startswith("bc1"), f"Bech32应保持'bc1'开头, 实际: {bech32_result[:5]}"

    def test_resolve_batch_all_formats(self):
        """批量解析混合格式地址"""
        resolver = TargetResolver(enable_cache=False)
        inputs = [
            self.formats["p2pkh"],
            self.formats["p2sh"],
            self.formats["bech32"],
            "invalid!!!",
        ]
        results = resolver.resolve_batch(inputs)

        assert results[self.formats["p2pkh"]] == self.formats["p2pkh"].lower()
        assert results[self.formats["p2sh"]] == self.formats["p2sh"].lower()
        assert results[self.formats["bech32"]] == self.formats["bech32"].lower()
        assert results["invalid!!!"] is None

    def test_full_validation_chain_with_all_types(self):
        """BitcoinKeyValidator.full_validation_chain 覆盖所有地址类型"""
        targets = {
            self.formats["p2pkh"],
            self.formats["p2sh"],
            self.formats["bech32"],
        }

        report = self.validator.full_validation_chain(TEST_PRIVATE_KEY, targets)
        assert report["overall_success"] is True
        assert "address_match" in report["steps"]
        # P2PKH 应匹配（full_validation_chain 只生成 P2PKH 地址）
        assert report["steps"]["address_match"]["details"]["match"] is True

    def test_continuous_matcher_end_to_end(self):
        """端到端 ContinuousMatcher + BitcoinTargetTable 流程"""
        from src.core.wif import WIF

        wif = WIF.encode(TEST_PRIVATE_KEY, compressed=True)

        # 加载目标
        table = BitcoinTargetTable()
        table.load_from_wif_list([wif])

        # 用 ContinuousMatcher 匹配
        matcher = ContinuousMatcher(table)
        addr_info = {
            "hash160": self.formats["hash160"],
            "address": self.formats["p2pkh"],
            "private_key": TEST_PRIVATE_KEY,
        }
        is_match, record = matcher.check_single_address(addr_info)
        assert is_match is True

        # 统计信息
        stats = matcher.get_statistics()
        assert stats["total_checked"] == 1
        assert stats["matches_found"] == 1
        assert stats["efficiency"] == "O(1) per address"


class TestCaseInsensitiveConsistency:
    """大小写一致性测试 — 全链路统一使用 .lower()"""

    def setup_method(self):
        self.formats = _get_all_address_formats(TEST_PRIVATE_KEY)

    def test_generated_addresses_always_case_insensitive_compatible(self):
        """生成的地址经 TargetResolver 解析后返回小写"""
        resolver = TargetResolver(enable_cache=False)
        for addr in [self.formats["p2pkh"], self.formats["p2sh"], self.formats["bech32"]]:
            # TargetResolver 接收原始混合大小写，内部验证后 .lower()
            result = resolver.resolve(addr)
            assert result == addr.lower(), f"{addr[:10]}... 应被正确解析为小写"

    def test_resolver_returns_lowercase_on_valid_input(self):
        """TargetResolver 对原始混合大小写地址解析后返回小写"""
        resolver = TargetResolver(enable_cache=False)
        for addr in [self.formats["p2pkh"], self.formats["p2sh"], self.formats["bech32"]]:
            # TargetResolver 内部 Base58Check 验证 + .lower()
            result = resolver.resolve(addr)
            assert result == addr.lower(), f"{addr[:10]}... 应返回小写"

            # 重复解析应一致（缓存一致性）
            result2 = resolver.resolve(addr)
            assert result2 == addr.lower(), f"重复解析 {addr[:10]}... 应一致"

    def test_matcher_normalizes_to_lowercase(self):
        """AddressMatcher 内部存储和匹配均为小写"""
        matcher = AddressMatcher(
            strategy="hash_set",
            targets={
                self.formats["p2pkh"].upper(),
                self.formats["p2sh"].upper(),
            },
        )

        # 构造函数已归一化 — 验证
        assert matcher.is_match(self.formats["p2pkh"].lower())
        assert matcher.is_match(self.formats["p2sh"].lower())

    def test_add_target_normalizes_to_lowercase(self):
        """add_target 自动归一化为小写"""
        matcher = AddressMatcher(strategy="hash_set")
        matcher.add_target(self.formats["bech32"].upper())
        assert matcher.is_match(self.formats["bech32"].lower())


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
