"""目标地址比对流程完整单元测试

测试目标地址比对的完整流程：
1. TargetResolver - 多格式地址解析和统一转换
2. AddressMatcher - 三种匹配策略（hash_set/bloom_filter/trie）
3. ContinuousMatcher - O(1)哈希表查找和批量比对
4. BitcoinKeyValidator - 安全地址比较和验证
5. 端到端比对流程集成测试
"""

import os
import tempfile
from unittest.mock import Mock

import pytest

from src.collision.continuous_matcher import ContinuousMatcher
from src.collision.targets.matcher import AddressMatcher

# 导入被测模块
from src.collision.targets.resolver import TargetResolver
from src.core.bitcoin_key_validator import BitcoinKeyValidator


class TestTargetResolverFormatDetection:
    """TargetResolver 格式检测测试"""

    def test_detect_p2pkh_address(self):
        """测试P2PKH地址格式检测（1开头）"""
        # 标准P2PKH地址
        address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        fmt = TargetResolver.detect_format(address)
        assert fmt == "address"

    def test_detect_p2sh_address(self):
        """测试P2SH地址格式检测（3开头）"""
        # P2SH地址
        address = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
        fmt = TargetResolver.detect_format(address)
        assert fmt == "p2sh_address"

    def test_detect_bech32_address(self):
        """测试Bech32地址格式检测（bc1开头）"""
        # SegWit v0地址
        address = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
        fmt = TargetResolver.detect_format(address)
        assert fmt == "bech32_address"

    def test_detect_taproot_address(self):
        """测试Taproot地址格式检测（bc1p开头）"""
        # Taproot地址
        address = "bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8ztwac72sfr9rusxg3297"
        fmt = TargetResolver.detect_format(address)
        assert fmt == "taproot_address"

    def test_detect_wif_uncompressed(self):
        """测试非压缩WIF格式检测（5开头，51字符）"""
        wif = "5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS"
        fmt = TargetResolver.detect_format(wif)
        assert fmt == "wif"

    def test_detect_wif_compressed_k(self):
        """测试压缩WIF格式检测（K开头，52字符）"""
        wif = "KwdMAjGmerYanjeui5SHS7JkmpZvVipYvB2LJGU1ZxJwYvP98617"
        fmt = TargetResolver.detect_format(wif)
        assert fmt == "wif"

    def test_detect_wif_compressed_l(self):
        """测试压缩WIF格式检测（L开头，52字符）"""
        wif = "L1aW4aubDFB7yfras2S1mN3bqg9nwySY8nkoLmJebSLD5BWv3ENZ"
        fmt = TargetResolver.detect_format(wif)
        assert fmt == "wif"

    def test_detect_compressed_public_key(self):
        """测试压缩公钥格式检测（66字符，02/03开头）"""
        pubkey = "0279BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798"
        fmt = TargetResolver.detect_format(pubkey)
        assert fmt == "pubkey_compressed"

        pubkey = "03F1C2C47C125BED7CD7E8E28E7E82BF72B65F3A5B67D4A4E3E1C3F8C7D6E5F4A3"
        fmt = TargetResolver.detect_format(pubkey)
        assert fmt == "pubkey_compressed"

    def test_detect_uncompressed_public_key(self):
        """测试非压缩公钥格式检测（130字符，04开头）"""
        pubkey = "04" + "79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798" * 2
        fmt = TargetResolver.detect_format(pubkey)
        assert fmt == "pubkey_uncompressed"

    def test_detect_hash160(self):
        """测试Hash160格式检测（40字符hex）"""
        hash160 = "62e907b15cbf27d5425399ebf6f0fb50ebb88f18"
        fmt = TargetResolver.detect_format(hash160)
        assert fmt == "hash160"

    def test_detect_unknown_format(self):
        """测试未知格式检测"""
        assert TargetResolver.detect_format("") == "unknown"
        assert TargetResolver.detect_format("invalid!!!") == "unknown"
        assert TargetResolver.detect_format("12345") == "unknown"


class TestTargetResolverAddressConversion:
    """TargetResolver 地址转换测试"""

    def test_resolve_p2pkh_valid(self):
        """测试有效P2PKH地址解析"""
        resolver = TargetResolver(enable_cache=False)
        address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

        result = resolver.resolve(address)

        # P2PKH地址应返回原始大小写(保留Base58校验和)
        assert result == address

    def test_resolve_p2pkh_invalid_checksum(self):
        """测试校验和错误的P2PKH地址"""
        resolver = TargetResolver(enable_cache=False)
        # 修改最后一个字符使校验和错误
        invalid_address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb"

        result = resolver.resolve(invalid_address)

        # 校验和错误应该返回None
        assert result is None

    def test_resolve_with_cache_hit(self):
        """测试缓存命中"""
        resolver = TargetResolver(enable_cache=True, cache_max_size=100)
        address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

        # 第一次解析（缓存未命中）
        result1 = resolver.resolve(address)

        # 第二次解析（缓存命中）
        result2 = resolver.resolve(address)

        assert result1 == result2

        # 检查缓存统计
        stats = resolver.get_cache_stats()
        assert stats["hits"] >= 1

    def test_resolve_batch(self):
        """测试批量解析"""
        resolver = TargetResolver(enable_cache=True)

        inputs = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
            "invalid_format",
        ]

        results = resolver.resolve_batch(inputs)

        # 有效地址应该有结果
        assert results["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"] is not None
        assert results["1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"] is not None
        # 无效格式应该为None
        assert results["invalid_format"] is None

    def test_resolve_multiple_alias(self):
        """测试resolve_multiple别名方法"""
        resolver = TargetResolver(enable_cache=False)

        inputs = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "invalid",
        ]

        results = resolver.resolve_multiple(inputs)

        # 只返回有效结果
        assert len(results) == 1
        assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in results


class TestAddressMatcherStrategies:
    """AddressMatcher 三种匹配策略测试"""

    def test_hash_set_strategy(self):
        """测试Hash Set策略（默认）"""
        targets = {
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        }

        matcher = AddressMatcher(strategy="hash_set", targets=targets)

        # 测试匹配
        assert matcher.is_match("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is True
        assert matcher.is_match("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2") is True

        # 测试不匹配
        assert matcher.is_match("1CinvalidAddressXXXXXXXXXXXXX") is False

        # 测试策略
        assert matcher.strategy == "hash_set"

    def test_bloom_filter_strategy(self):
        """测试Bloom Filter策略"""
        targets = {f"1Test{i:030d}" for i in range(100)}

        try:
            matcher = AddressMatcher(
                strategy="bloom_filter",
                targets=targets,
                bloom_capacity=1000,
                bloom_error_rate=0.001,
            )

            # Bloom Filter可能有误判，但不应有漏判
            for target in targets:
                assert matcher.is_match(target) is True

            # 统计信息
            stats = matcher.get_stats()
            assert stats["strategy"] == "bloom_filter"
            assert stats["target_count"] == 100

        except ImportError:
            # 如果pybloom_live未安装，应该回退到hash_set
            pytest.skip("pybloom-live未安装")

    def test_trie_strategy(self):
        """测试Trie前缀树策略"""
        targets = {
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        }

        matcher = AddressMatcher(strategy="trie", targets=targets)

        # 测试匹配
        assert matcher.is_match("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is True
        assert matcher.is_match("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2") is True

        # 测试不匹配
        assert matcher.is_match("1CinvalidXXXXXXXXXXXXXXXXXXX") is False

    def test_add_target(self):
        """测试动态添加目标地址"""
        matcher = AddressMatcher(strategy="hash_set")

        # 初始为空
        assert len(matcher) == 0

        # 添加单个目标
        matcher.add_target("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        assert len(matcher) == 1
        assert matcher.is_match("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is True

    def test_add_targets_batch(self):
        """测试批量添加目标地址"""
        matcher = AddressMatcher(strategy="hash_set")

        targets = {
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
            "1HQ3Go3ggs8pFnXuHVHR9PCPfwM1UuFb3g",
        }

        matcher.add_targets(targets)

        assert len(matcher) == 3
        for target in targets:
            assert matcher.is_match(target) is True

    def test_remove_target(self):
        """测试移除目标地址"""
        targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        matcher = AddressMatcher(strategy="hash_set", targets=targets)

        # 移除存在的地址
        result = matcher.remove_target("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        assert result is True
        assert matcher.is_match("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is False

        # 移除不存在的地址
        result = matcher.remove_target("1NonExistentXXXXXXXXXXXXXXX")
        assert result is False

    def test_clear_all_targets(self):
        """测试清空所有目标"""
        targets = {
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        }
        matcher = AddressMatcher(strategy="hash_set", targets=targets)

        assert len(matcher) == 2

        matcher.clear()

        assert len(matcher) == 0

    def test_contains_operator(self):
        """测试in操作符支持"""
        targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        matcher = AddressMatcher(strategy="hash_set", targets=targets)

        assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in matcher
        assert "1NonExistentXXXXXXXXXXXXXXX" not in matcher

    def test_invalid_strategy(self):
        """测试无效策略"""
        with pytest.raises(ValueError, match="未知策略"):
            AddressMatcher(strategy="invalid_strategy")

    def test_input_type_validation(self):
        """测试输入类型验证"""
        matcher = AddressMatcher(strategy="hash_set")

        # 非字符串输入应该被转换或拒绝
        result = matcher.is_match(12345)
        assert result is False  # 转换后仍然不匹配


class TestContinuousMatcher:
    """ContinuousMatcher O(1)匹配测试"""

    def setup_method(self):
        """每个测试方法前的设置"""
        # 创建模拟的BitcoinTargetTable
        self.mock_target_table = Mock()
        self.matcher = ContinuousMatcher(self.mock_target_table)

    def test_check_single_address_match(self):
        """测试单个地址匹配成功"""
        # 模拟目标表返回匹配
        self.mock_target_table.check_match.return_value = (
            True,
            {"address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
        )

        addr_info = {
            "hash160": bytes.fromhex("62e907b15cbf27d5425399ebf6f0fb50ebb88f18"),
            "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "private_key": os.urandom(32),
        }

        is_match, match_record = self.matcher.check_single_address(addr_info)

        assert is_match is True
        assert match_record is not None
        assert match_record["target"]["address"] == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        assert self.matcher.match_count == 1
        assert self.matcher.total_checked == 1

    def test_check_single_address_no_match(self):
        """测试单个地址不匹配"""
        # 模拟目标表返回不匹配
        self.mock_target_table.check_match.return_value = (False, None)

        addr_info = {
            "hash160": bytes.fromhex("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
            "address": "1NonExistentXXXXXXXXXXXXXXX",
            "private_key": os.urandom(32),
        }

        is_match, match_record = self.matcher.check_single_address(addr_info)

        assert is_match is False
        assert match_record is None
        assert self.matcher.match_count == 0
        assert self.matcher.total_checked == 1

    def test_check_single_address_missing_hash160(self):
        """测试缺少hash160字段"""
        addr_info = {
            "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        }

        is_match, match_record = self.matcher.check_single_address(addr_info)

        assert is_match is False
        assert match_record is None

    def test_check_address_batch(self):
        """测试批量地址检查"""

        # 模拟部分匹配
        def mock_check_match(hash160):
            if hash160 == bytes.fromhex("62e907b15cbf27d5425399ebf6f0fb50ebb88f18"):
                return True, {"address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
            return False, None

        self.mock_target_table.check_match.side_effect = mock_check_match

        addresses = [
            {
                "hash160": bytes.fromhex("62e907b15cbf27d5425399ebf6f0fb50ebb88f18"),
                "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "private_key": os.urandom(32),
            },
            {
                "hash160": bytes.fromhex("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"),
                "address": "1NonExistent1XXXXXXXXXXXXXX",
                "private_key": os.urandom(32),
            },
            {
                "hash160": bytes.fromhex("cccccccccccccccccccccccccccccccccccccccc"),
                "address": "1NonExistent2XXXXXXXXXXXXXX",
                "private_key": os.urandom(32),
            },
        ]

        matches = self.matcher.check_address_batch(addresses)

        # 应该只有1个匹配
        assert len(matches) == 1
        assert matches[0]["target"]["address"] == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        assert self.matcher.match_count == 1
        assert self.matcher.total_checked == 3

    def test_get_statistics(self):
        """测试统计信息"""
        self.mock_target_table.check_match.return_value = (False, None)

        # 执行一些检查
        for i in range(10):
            addr_info = {
                "hash160": os.urandom(20),
            }
            self.matcher.check_single_address(addr_info)

        stats = self.matcher.get_statistics()

        assert stats["total_checked"] == 10
        assert stats["matches_found"] == 0
        assert stats["match_rate"] == 0.0
        assert stats["elapsed_seconds"] >= 0  # 快速操作可在同一毫秒内完成
        assert stats["check_rate"] >= 0  # elapsed=0 时 check_rate 为 0
        assert stats["efficiency"] == "O(1) per address"

    def test_reset_statistics(self):
        """测试重置统计信息"""
        self.mock_target_table.check_match.return_value = (False, None)

        # 执行一些检查
        addr_info = {"hash160": os.urandom(20)}
        self.matcher.check_single_address(addr_info)

        assert self.matcher.total_checked == 1

        # 重置
        self.matcher.reset_statistics()

        assert self.matcher.total_checked == 0
        assert self.matcher.match_count == 0

    def test_thread_safety(self):
        """测试线程安全性"""
        import threading

        self.mock_target_table.check_match.return_value = (False, None)

        def check_addresses(count):
            for _ in range(count):
                addr_info = {"hash160": os.urandom(20)}
                self.matcher.check_single_address(addr_info)

        # 创建多个线程并发检查
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=check_addresses, args=(100,))
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 总检查数应该是 10线程 × 100次 = 1000次
        assert self.matcher.total_checked == 1000


class TestBitcoinKeyValidatorSecurity:
    """BitcoinKeyValidator 安全比较测试"""

    def test_verify_address_match_success(self):
        """测试地址匹配成功"""
        validator = BitcoinKeyValidator(secure_mode=True)

        target_addresses = {
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        }

        result = validator.verify_address_match("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", target_addresses)

        assert result.success is True
        assert result.details["match"] is True
        assert result.details["matched_target"] == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

    def test_verify_address_match_failure(self):
        """测试地址匹配失败"""
        validator = BitcoinKeyValidator(secure_mode=True)

        target_addresses = {
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        }

        result = validator.verify_address_match("1NonExistentXXXXXXXXXXXXXXX", target_addresses)

        assert result.details["match"] is False

    def test_hmac_compare_digest_usage(self):
        """测试使用hmac.compare_digest防止时序攻击"""
        # 验证代码中确实使用了hmac.compare_digest
        import inspect

        from src.core.bitcoin_key_validator import BitcoinKeyValidator

        source = inspect.getsource(BitcoinKeyValidator.verify_address_match)
        assert "hmac.compare_digest" in source

    def test_validate_address_p2pkh(self):
        """测试P2PKH地址验证"""
        validator = BitcoinKeyValidator()

        result = validator.validate_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")

        assert result.success is True
        assert result.details["address_type"] == "P2PKH"
        assert result.details["checksum_valid"] is True

    def test_validate_address_p2sh(self):
        """测试P2SH地址验证"""
        validator = BitcoinKeyValidator()

        result = validator.validate_address("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy")

        assert result.success is True
        assert result.details["address_type"] == "P2SH"


class TestEndToEndMatchingFlow:
    """端到端比对流程集成测试"""

    def test_full_matching_workflow(self):
        """测试完整的地址比对工作流程"""
        # 1. 创建解析器
        resolver = TargetResolver(enable_cache=True)

        # 2. 解析多个目标地址
        target_inputs = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # P2PKH
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",  # P2PKH
        ]

        resolved_addresses = set()
        for target in target_inputs:
            resolved = resolver.resolve(target)
            if resolved:
                resolved_addresses.add(resolved)

        assert len(resolved_addresses) == 2

        # 3. 创建匹配器
        matcher = AddressMatcher(strategy="hash_set", targets=resolved_addresses)

        # 4. 验证匹配
        assert matcher.is_match("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is True
        assert matcher.is_match("1NonExistentXXXXXXXXXXXXXXX") is False

    def test_batch_resolution_and_matching(self):
        """测试批量解析和匹配"""
        resolver = TargetResolver(enable_cache=True)

        # 批量解析
        inputs = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
            "invalid_format",
        ]

        results = resolver.resolve_batch(inputs)

        # 过滤有效地址
        valid_addresses = {addr for addr in results.values() if addr is not None}

        assert len(valid_addresses) == 2

        # 创建匹配器并测试
        matcher = AddressMatcher(strategy="hash_set", targets=valid_addresses)

        for addr in valid_addresses:
            assert matcher.is_match(addr) is True

    def test_cache_optimization_in_workflow(self):
        """测试工作流中的缓存优化"""
        resolver = TargetResolver(enable_cache=True, cache_max_size=100)

        address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

        # 第一次解析（未命中缓存）
        result1 = resolver.resolve(address)
        stats1 = resolver.get_cache_stats()

        # 第二次解析（命中缓存）
        result2 = resolver.resolve(address)
        stats2 = resolver.get_cache_stats()

        assert result1 == result2
        assert stats2["hits"] > stats1["hits"]

    def test_load_targets_from_file(self):
        """测试从文件加载目标地址"""
        resolver = TargetResolver(enable_cache=True)

        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("# 目标地址列表\n")
            f.write("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n")
            f.write("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2\n")
            f.write("\n")  # 空行
            f.write("# 注释\n")
            f.write("invalid_format\n")
            temp_file = f.name

        try:
            # 从文件加载
            addresses = resolver.load_from_file(temp_file)

            # 应该加载2个有效地址(保留原始大小写)
            assert len(addresses) == 2
            assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in addresses
            assert "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2" in addresses

        finally:
            os.unlink(temp_file)

    def test_security_path_traversal_protection(self):
        """测试路径遍历攻击防护"""
        resolver = TargetResolver(enable_cache=False)

        # 尝试访问不允许的路径
        result = resolver.load_from_file("../../etc/passwd")

        # 应该返回空集合
        assert result == set()


class TestPerformanceOptimization:
    """性能优化测试"""

    def test_o1_lookup_performance(self):
        """测试O(1)查找性能"""
        import time

        # 使用Base58字符集生成有效格式的地址
        base58_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        targets = set()

        for i in range(10000):
            # 生成33个Base58字符
            addr_chars = []
            num = i
            for _ in range(33):
                addr_chars.append(base58_chars[num % len(base58_chars)])
                num = num // len(base58_chars) + num % len(base58_chars)
            fake_addr = "1" + "".join(addr_chars)
            targets.add(fake_addr)

        matcher = AddressMatcher(strategy="hash_set", targets=targets)

        # 测试查找性能
        start_time = time.time()
        iterations = 10000

        # 使用已存在的地址进行测试
        test_addresses = list(targets)[:iterations]
        for test_addr in test_addresses:
            matcher.is_match(test_addr)

        elapsed = time.time() - start_time

        # 10000次查找应该在很短时间内完成
        assert elapsed < 1.0  # 小于1秒

        # 计算平均每次查找时间
        avg_time = elapsed / iterations
        assert avg_time < 0.0001  # 平均每次小于0.1毫秒

    def test_batch_vs_single_performance(self):
        """测试批量处理与单个处理的性能对比"""
        import time

        # 使用Base58字符集生成有效格式的地址
        base58_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        addresses = []
        for i in range(100):
            # 简单生成：使用循环字符
            suffix = "".join([base58_chars[(i + j) % len(base58_chars)] for j in range(33)])
            addresses.append("1" + suffix)

        resolver = TargetResolver(enable_cache=False)

        # 单个解析（慢）
        start_time = time.time()
        for addr in addresses:
            resolver.resolve(addr)
        single_time = time.time() - start_time

        # 批量解析（快）
        start_time = time.time()
        resolver.resolve_batch(addresses)
        batch_time = time.time() - start_time

        # 批量处理应该更快或至少不会慢太多
        # （由于缓存效应，可能差异不大）
        assert batch_time <= single_time * 1.5  # 允许50%的误差


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_target_set(self):
        """测试空目标集合"""
        matcher = AddressMatcher(strategy="hash_set", targets=set())

        assert len(matcher) == 0
        assert matcher.is_match("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is False

    def test_duplicate_addresses(self):
        """测试重复地址处理"""
        targets = {
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # noqa: B033  # 有意重复以测试去重
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        }

        matcher = AddressMatcher(strategy="hash_set", targets=targets)

        # 集合自动去重
        assert len(matcher) == 2

    def test_large_target_set(self):
        """测试大规模目标集合"""
        # 创建1000个不同的目标地址（使用真实格式的地址）
        # 注意：这些地址仅用于测试数据结构，不是有效的比特币地址
        import hashlib

        targets = set()
        for i in range(1000):
            # 使用hash生成唯一的33字符后缀
            hash_suffix = hashlib.md5(f"test_address_{i}".encode(), usedforsecurity=False).hexdigest()[
                :33
            ]
            fake_addr = "1" + hash_suffix
            targets.add(fake_addr)

        # 验证确实生成了1000个不同的地址
        assert len(targets) == 1000, f"Expected 1000 unique addresses, got {len(targets)}"

        matcher = AddressMatcher(strategy="hash_set", targets=targets)

        assert len(matcher) == 1000

        # 测试查找存在的地址
        sample_addr = list(targets)[0]
        assert matcher.is_match(sample_addr) is True

        # 测试查找不存在的地址
        assert matcher.is_match("1NonExistentXXXXXXXXXXXXXXXXXX") is False

    def test_concurrent_access(self):
        """测试并发访问"""
        import threading

        targets = {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"}
        matcher = AddressMatcher(strategy="hash_set", targets=targets)

        errors = []

        def access_matcher():
            try:
                for _ in range(100):
                    matcher.is_match("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
                    matcher.add_target("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2")
            except Exception as e:
                errors.append(e)

        # 创建多个线程
        threads = [threading.Thread(target=access_matcher) for _ in range(10)]
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # 不应该有错误
        assert len(errors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
