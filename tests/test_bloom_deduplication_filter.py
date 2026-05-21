#!/usr/bin/env python3
"""Bloom Filter 去重过滤器 (BloomDeduplicationFilter) 单元测试

覆盖：
- BloomFilter: 初始化、_optimal_bit_size、_optimal_hash_count
- BloomFilter: add、check、_hashes
- BloomFilter: get_current_false_positive_rate、get_fill_ratio
- BloomFilter: get_stats、clear
- BloomDeduplicationFilter: check_and_add、_fingerprint
- BloomDeduplicationFilter: enabled/disabled
- BloomDeduplicationFilter: get_stats、reset、should_auto_reset
- 边界值：空元素、大容量、最小误判率、类型错误
- 并发安全：多线程 add/check
"""

import threading

import pytest

from src.collision.bloom_deduplication_filter import (
    BloomDeduplicationFilter,
    BloomFilter,
)

# ============================================================================
# BloomFilter 测试
# ============================================================================


@pytest.mark.unit
class TestBloomFilterInit:
    """BloomFilter 初始化测试"""

    def test_default_init(self):
        """测试默认初始化"""
        bf = BloomFilter(max_elements=1000, false_positive_rate=0.01)
        assert bf.max_elements == 1000
        assert bf.false_positive_rate == 0.01
        assert bf.bit_size > 0
        assert bf.hash_count > 0
        assert bf.elements_added == 0

    def test_large_capacity(self):
        """测试大容量"""
        bf = BloomFilter(max_elements=10_000_000, false_positive_rate=0.001)
        assert bf.max_elements == 10_000_000
        assert bf.bit_size > 0

    def test_small_capacity(self):
        """测试小容量"""
        bf = BloomFilter(max_elements=1, false_positive_rate=0.5)
        assert bf.max_elements == 1
        assert bf.bit_size >= 1

    def test_very_low_false_positive_rate(self):
        """测试极低误判率"""
        bf = BloomFilter(max_elements=1000, false_positive_rate=0.0001)
        # 误判率低 -> 位数组更大
        assert bf.bit_size > 0

    # ── 参数验证 ──

    def test_invalid_max_elements_zero(self):
        """测试 max_elements=0 抛出异常"""
        with pytest.raises(ValueError, match="正整数"):
            BloomFilter(max_elements=0)

    def test_invalid_max_elements_negative(self):
        """测试 max_elements 负数抛出异常"""
        with pytest.raises(ValueError, match="正整数"):
            BloomFilter(max_elements=-10)

    def test_invalid_false_positive_zero(self):
        """测试 false_positive_rate=0 抛出异常"""
        with pytest.raises(ValueError, match="范围内"):
            BloomFilter(max_elements=100, false_positive_rate=0.0)

    def test_invalid_false_positive_one(self):
        """测试 false_positive_rate=1 抛出异常"""
        with pytest.raises(ValueError, match="范围内"):
            BloomFilter(max_elements=100, false_positive_rate=1.0)

    def test_invalid_false_positive_negative(self):
        """测试 false_positive_rate 负数抛出异常"""
        with pytest.raises(ValueError, match="范围内"):
            BloomFilter(max_elements=100, false_positive_rate=-0.1)

    def test_invalid_false_positive_above_one(self):
        """测试 false_positive_rate > 1 抛出异常"""
        with pytest.raises(ValueError, match="范围内"):
            BloomFilter(max_elements=100, false_positive_rate=1.5)


@pytest.mark.unit
class TestBloomFilterOptimal:
    """最优参数计算测试"""

    def test_optimal_bit_size_monotonic(self):
        """测试位数组大小随元素增加单调增长"""
        bf_small = BloomFilter(max_elements=100, false_positive_rate=0.01)
        bf_large = BloomFilter(max_elements=10000, false_positive_rate=0.01)
        assert bf_large.bit_size > bf_small.bit_size

    def test_optimal_hash_count_positive(self):
        """测试哈希函数数量为正"""
        bf = BloomFilter(max_elements=1000)
        assert bf.hash_count >= 1

    def test_bit_size_reasonable(self):
        """测试位数组大小在合理范围"""
        bf = BloomFilter(max_elements=1000, false_positive_rate=0.01)
        # 对于 1000 元素 1% 误判率，位数组大约在 9585 bits
        assert bf.bit_size > 1000
        assert bf.bit_size < 20000


@pytest.mark.unit
class TestBloomFilterAddCheck:
    """add / check 测试"""

    def test_add_and_check(self):
        """测试添加后检查返回 True"""
        bf = BloomFilter(max_elements=1000)
        item = b"test_item_32_bytes_data_here"
        bf.add(item)
        assert bf.check(item) is True

    def test_check_unadded(self):
        """测试未添加的元素返回 False"""
        bf = BloomFilter(max_elements=1000)
        item = b"never_added_item_bytes_here"
        assert bf.check(item) is False

    def test_multiple_items(self):
        """测试多个元素"""
        bf = BloomFilter(max_elements=10000)
        items = [f"item_{i}".encode() for i in range(100)]
        for item in items:
            bf.add(item)
        # 所有添加的都应该返回 True
        for item in items:
            assert bf.check(item) is True

    def test_elements_added_counter(self):
        """测试元素计数"""
        bf = BloomFilter(max_elements=1000)
        for i in range(50):
            bf.add(f"item_{i}".encode())
        assert bf.elements_added == 50

    # ── 类型验证 ──

    def test_add_invalid_type(self):
        """测试 add 非 bytes 类型抛出异常"""
        bf = BloomFilter(max_elements=100)
        with pytest.raises(TypeError, match="bytes"):
            bf.add("not_bytes")

    def test_add_invalid_type_int(self):
        """测试 add int 类型抛出异常"""
        bf = BloomFilter(max_elements=100)
        with pytest.raises(TypeError, match="bytes"):
            bf.add(12345)

    def test_check_invalid_type(self):
        """测试 check 非 bytes 类型抛出异常"""
        bf = BloomFilter(max_elements=100)
        with pytest.raises(TypeError, match="bytes"):
            bf.check("not_bytes")

    # ── 边界值 ──

    def test_empty_bytes(self):
        """测试空字节"""
        bf = BloomFilter(max_elements=100)
        bf.add(b"")
        assert bf.check(b"") is True

    def test_large_item(self):
        """测试大字节项"""
        bf = BloomFilter(max_elements=100)
        large = b"X" * 10000
        bf.add(large)
        assert bf.check(large) is True

    def test_false_positive_rate_in_practice(self):
        """验证实际误判率在可接受范围"""
        bf = BloomFilter(max_elements=10000, false_positive_rate=0.01)
        # 添加 10000 个元素
        added = {f"added_{i}".encode() for i in range(10000)}
        for item in added:
            bf.add(item)
        # 检查 10000 个未添加的元素
        false_positives = 0
        for i in range(10000, 20000):
            if bf.check(f"check_{i}".encode()):
                false_positives += 1
        # 1% 误判率下，10000 个检查预期约 100 个误判
        # 允许一定容差
        assert false_positives < 500  # < 5%（宽松容差）


@pytest.mark.unit
class TestBloomFilterStats:
    """统计信息测试"""

    def test_get_stats_structure(self):
        """测试统计信息结构"""
        bf = BloomFilter(max_elements=1000)
        stats = bf.get_stats()
        assert "max_elements" in stats
        assert "elements_added" in stats
        assert "bit_size" in stats
        assert "hash_count" in stats
        assert "fill_ratio" in stats
        assert "current_false_positive_rate" in stats
        assert "target_false_positive_rate" in stats
        assert "memory_usage_bytes" in stats

    def test_get_stats_values(self):
        """测试统计信息数值正确"""
        bf = BloomFilter(max_elements=1000)
        for i in range(10):
            bf.add(f"item_{i}".encode())
        stats = bf.get_stats()
        assert stats["max_elements"] == 1000
        assert stats["elements_added"] == 10

    def test_fill_ratio_after_adding(self):
        """测试添加元素后填充率增加"""
        bf = BloomFilter(max_elements=10000)
        assert bf.get_fill_ratio() == 0.0
        for i in range(100):
            bf.add(f"item_{i}".encode())
        assert bf.get_fill_ratio() > 0.0

    def test_current_false_positive_rate_zero_initially(self):
        """测试初始误判率为 0"""
        bf = BloomFilter(max_elements=1000)
        assert bf.get_current_false_positive_rate() == 0.0

    def test_current_false_positive_rate_increases(self):
        """测试添加元素后误判率增加"""
        bf = BloomFilter(max_elements=10000)
        for i in range(500):
            bf.add(f"item_{i}".encode())
        rate = bf.get_current_false_positive_rate()
        assert rate > 0.0
        assert rate <= 1.0

    def test_memory_usage_reasonable(self):
        """测试内存使用合理"""
        bf = BloomFilter(max_elements=1000000, false_positive_rate=0.01)
        stats = bf.get_stats()
        # 100 万元素 1% 误判率，内存应在几个 MB 内
        memory_mb = stats["memory_usage_bytes"] / (1024 * 1024)
        assert memory_mb < 10


@pytest.mark.unit
class TestBloomFilterClear:
    """clear 测试"""

    def test_clear_resets_all(self):
        """测试清空重置所有数据"""
        bf = BloomFilter(max_elements=1000)
        for i in range(100):
            bf.add(f"item_{i}".encode())
        bf.clear()

        assert bf.elements_added == 0
        # 之前添加的元素不应再被检测到
        assert bf.check(b"item_0") is False

    def test_clear_then_reuse(self):
        """测试清空后可重新使用"""
        bf = BloomFilter(max_elements=1000)
        bf.add(b"key1")
        bf.clear()
        bf.add(b"key2")
        assert bf.check(b"key2") is True
        assert bf.check(b"key1") is False


# ============================================================================
# BloomDeduplicationFilter 测试
# ============================================================================


@pytest.mark.unit
class TestBloomDedupInit:
    """BloomDeduplicationFilter 初始化测试"""

    def test_default_init(self):
        """测试默认初始化"""
        f = BloomDeduplicationFilter()
        assert f.enabled is True
        assert f.max_size == 10_000_000
        assert f.false_positive_rate == 0.001
        assert f.duplicates_found == 0
        assert f.total_checks == 0

    def test_custom_init(self):
        """测试自定义初始化"""
        f = BloomDeduplicationFilter(
            max_size=1000,
            false_positive_rate=0.01,
            enabled=False,
        )
        assert f.max_size == 1000
        assert f.false_positive_rate == 0.01
        assert f.enabled is False

    def test_enabled_false(self):
        """测试禁用模式"""
        f = BloomDeduplicationFilter(enabled=False)
        # 禁用状态下所有检查都返回 True
        assert f.check_and_add(b"key1") is True
        assert f.check_and_add(b"key1") is True  # 重复也通过


@pytest.mark.unit
class TestBloomDedupCheckAndAdd:
    """check_and_add 测试"""

    def test_first_check_passes(self):
        """测试首次检查通过"""
        f = BloomDeduplicationFilter(max_size=1000)
        result = f.check_and_add(b"unique_key_32_bytes_here!")
        assert result is True

    def test_duplicate_blocked(self):
        """测试重复检查被拦截"""
        f = BloomDeduplicationFilter(max_size=1000)
        key = b"dup_key_32_bytes_here_!!!!"
        f.check_and_add(key)
        result = f.check_and_add(key)
        assert result is False

    def test_different_keys_pass(self):
        """测试不同键通过"""
        f = BloomDeduplicationFilter(max_size=10000)
        for i in range(100):
            key = f"key_{i:032d}".encode()
            assert f.check_and_add(key) is True

    def test_stats_updated(self):
        """测试统计更新"""
        f = BloomDeduplicationFilter(max_size=1000)
        key = b"stats_key_32_bytes_here_!"
        f.check_and_add(key)
        f.check_and_add(key)  # 重复

        stats = f.get_stats()
        assert stats["total_checks"] == 2
        assert stats["duplicates_found"] == 1
        assert stats["unique_elements"] == 1

    # ── 边界值 ──

    def test_empty_key(self):
        """测试空键"""
        f = BloomDeduplicationFilter(max_size=100)
        result = f.check_and_add(b"")
        assert result is True

    def test_large_number_of_keys(self):
        """测试大量键"""
        f = BloomDeduplicationFilter(max_size=100000)
        for i in range(10000):
            key = f"batch_key_{i:032d}".encode()
            f.check_and_add(key)
        assert f.total_checks == 10000


@pytest.mark.unit
class TestBloomDedupStats:
    """get_stats 测试"""

    def test_get_stats_contains_bloom(self):
        """测试统计信息包含 Bloom Filter 数据"""
        f = BloomDeduplicationFilter(max_size=1000)
        stats = f.get_stats()
        assert "enabled" in stats
        assert "total_checks" in stats
        assert "duplicates_found" in stats
        assert "unique_elements" in stats
        assert "duplicate_rate" in stats
        assert "bloom_filter" in stats

    def test_duplicate_rate_calculation(self):
        """测试重复率计算"""
        f = BloomDeduplicationFilter(max_size=10000)
        for _ in range(100):
            f.check_and_add(f"key_{_}".encode()[:32].ljust(32, b"\x00"))
        # 重复添加
        for _ in range(25):
            f.check_and_add(b"key_0".ljust(32, b"\x00"))
        stats = f.get_stats()
        # 125 次检查，25 次重复（到检查时已添加）
        assert stats["total_checks"] >= 125
        assert stats["duplicates_found"] >= 25

    def test_duplicate_rate_zero_initial(self):
        """测试初始重复率为 0"""
        f = BloomDeduplicationFilter()
        stats = f.get_stats()
        assert stats["duplicate_rate"] == 0


@pytest.mark.unit
class TestBloomDedupReset:
    """reset 测试"""

    def test_reset_clears_counters(self):
        """测试重置清除计数器"""
        f = BloomDeduplicationFilter(max_size=1000)
        key = b"reset_key_32_bytes_here_!"
        f.check_and_add(key)
        f.check_and_add(key)

        f.reset()
        assert f.total_checks == 0
        assert f.duplicates_found == 0

    def test_reset_allows_reuse(self):
        """测试重置后可重新使用"""
        f = BloomDeduplicationFilter(max_size=100)
        key = b"reuse_key_32_bytes_here_!"
        f.check_and_add(key)
        f.reset()
        # 重置后相同键应再次通过
        assert f.check_and_add(key) is True


@pytest.mark.unit
class TestBloomDedupAutoReset:
    """should_auto_reset 测试"""

    def test_initial_fill_ratio_low(self):
        """测试初始填充率低时不建议重置"""
        f = BloomDeduplicationFilter(max_size=100000)
        assert f.should_auto_reset() is False

    def test_after_many_adds(self):
        """测试添加大量元素后可能建议重置"""
        f = BloomDeduplicationFilter(max_size=1000)
        # 添加大量元素增加填充率
        for i in range(5000):
            f.check_and_add(f"fill_{i}".encode()[:32].ljust(32, b"\x00"))
        # 此时填充率可能超过 70%
        result = f.should_auto_reset()
        assert isinstance(result, bool)


@pytest.mark.unit
class TestBloomDedupFingerprint:
    """_fingerprint 测试"""

    def test_fingerprint_deterministic(self):
        """测试指纹确定性"""
        f = BloomDeduplicationFilter(max_size=100)
        fp1 = f._fingerprint(b"test_key")
        fp2 = f._fingerprint(b"test_key")
        assert fp1 == fp2

    def test_fingerprint_different_keys(self):
        """测试不同键产生不同指纹"""
        f = BloomDeduplicationFilter(max_size=100)
        fp1 = f._fingerprint(b"key_a")
        fp2 = f._fingerprint(b"key_b")
        assert fp1 != fp2

    def test_fingerprint_length(self):
        """测试指纹长度"""
        f = BloomDeduplicationFilter(max_size=100)
        fp = f._fingerprint(b"test_key")
        assert len(fp) == 32  # SHA256 输出 32 字节


@pytest.mark.unit
class TestBloomDedupConcurrency:
    """并发测试"""

    def test_concurrent_checks_no_crash(self):
        """测试并发检查不崩溃"""
        f = BloomDeduplicationFilter(max_size=100000)
        errors = []

        def worker(tid: int):
            try:
                for i in range(200):
                    key = f"concurrent_{tid}_{i}".encode()[:32].ljust(32, b"\x00")
                    f.check_and_add(key)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_count_consistency(self):
        """测试并发计数一致性"""
        f = BloomDeduplicationFilter(max_size=100000)
        n_threads = 5
        n_per_thread = 200

        def worker(tid: int):
            for i in range(n_per_thread):
                key = f"count_{tid}_{i}".encode()[:32].ljust(32, b"\x00")
                f.check_and_add(key)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert f.total_checks == n_threads * n_per_thread


# ============================================================================
# _optimal_bit_size / _optimal_hash_count 静态方法测试
# ============================================================================


@pytest.mark.unit
class TestOptimalFormulas:
    """最优公式测试"""

    def test_optimal_bit_size_formula(self):
        """测试位数组大小公式"""
        result = BloomFilter._optimal_bit_size(1000, 0.01)
        assert isinstance(result, int)
        assert result > 0

    def test_optimal_bit_size_large_n(self):
        """测试大 n 的位数组大小"""
        result = BloomFilter._optimal_bit_size(1000000, 0.001)
        assert result > 0

    def test_optimal_hash_count_formula(self):
        """测试哈希函数数量公式"""
        result = BloomFilter._optimal_hash_count(10000, 1000)
        assert isinstance(result, int)
        assert result >= 1

    def test_optimal_hash_count_at_least_one(self):
        """测试哈希函数数量至少为 1"""
        result = BloomFilter._optimal_hash_count(100, 100)
        assert result >= 1
