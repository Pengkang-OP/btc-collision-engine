"""DeduplicationFilter 单元测试 - 基于集合的去重过滤器"""

import threading
import unittest

from src.collision.deduplication_filter import DeduplicationFilter


class TestDeduplicationFilterBasic:
    """基础功能测试"""

    def test_first_check_passes(self):
        """首次检查返回 True（允许通过）"""
        f = DeduplicationFilter(max_size=100)
        pk = bytes(range(32))
        assert f.check_and_add(pk)

    def test_duplicate_blocked(self):
        """重复私钥被拦截"""
        f = DeduplicationFilter(max_size=100)
        pk = bytes(range(32))
        f.check_and_add(pk)
        assert not f.check_and_add(pk)

    def test_different_keys_pass(self):
        """不同私钥都能通过"""
        f = DeduplicationFilter(max_size=1000)
        for i in range(100):
            pk = i.to_bytes(32, "big")
            assert f.check_and_add(pk), f"私钥 {i} 应通过"

    def test_disabled_always_returns_true(self):
        """禁用状态始终返回 True"""
        f = DeduplicationFilter(max_size=100, enabled=False)
        pk = bytes(32)
        assert f.check_and_add(pk)
        assert f.check_and_add(pk)
        assert f.check_and_add(pk)

    def test_stats_tracking(self):
        """统计计数正确"""
        f = DeduplicationFilter(max_size=100)
        pk1 = b"\x01" * 32
        pk2 = b"\x02" * 32
        f.check_and_add(pk1)
        f.check_and_add(pk1)  # 重复
        f.check_and_add(pk2)

        stats = f.get_stats()
        assert stats["checks_total"] == 3
        assert stats["duplicates_found"] == 1


class TestDeduplicationFilterAddress:
    """地址去重测试"""

    def test_address_duplicate_blocked(self):
        """相同地址的私钥被拦截"""
        f = DeduplicationFilter(max_size=100)
        f.check_and_add(b"\x01" * 32, address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        assert not f.check_and_add(b"\x02" * 32, address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")

    def test_address_case_insensitive(self):
        """地址比较大小写不敏感"""
        f = DeduplicationFilter(max_size=100)
        f.check_and_add(b"\x01" * 32, address="1ABCdef")
        result = f.check_and_add(b"\x02" * 32, address="1abcDEF")
        assert not result

    def test_is_duplicate_method(self):
        """is_duplicate 只检查不添加"""
        f = DeduplicationFilter(max_size=100)
        pk = b"\x01" * 32
        addr = "1TestAddress"
        f.check_and_add(pk, address=addr)

        assert f.is_duplicate(pk, addr)
        # 不同的 key/address 不应重复
        assert not f.is_duplicate(b"\x02" * 32, "1OtherAddress")

    def test_is_duplicate_disabled(self):
        """禁用时 is_duplicate 始终返回 False"""
        f = DeduplicationFilter(max_size=100, enabled=False)
        assert not f.is_duplicate(b"\x01" * 32, "1Test")


class TestDeduplicationFilterMaxSize:
    """容量限制测试"""

    def test_exceed_max_size_no_crash(self):
        """超过 max_size 不崩溃（仅警告）"""
        max_size = 50
        f = DeduplicationFilter(max_size=max_size)
        for i in range(max_size * 2):
            pk = i.to_bytes(32, "big")
            f.check_and_add(pk)
        # 超过了 max_size 但不崩溃
        assert len(f._seen_keys) > max_size

    def test_check_and_add_still_works_after_exceed(self):
        """超过 max_size 后仍可正常使用"""
        f = DeduplicationFilter(max_size=50)
        for i in range(100):
            f.check_and_add(i.to_bytes(32, "big"))
        # 仍然可以检测重复
        result = f.check_and_add((0).to_bytes(32, "big"))
        assert not result  # 第0个已添加，是重复


class TestDeduplicationFilterConcurrency:
    """多线程并发测试"""

    def test_concurrent_checks_no_crash(self):
        """多线程并发检查不崩溃"""
        f = DeduplicationFilter(max_size=10000)
        errors = []

        def worker(thread_id: int):
            try:
                for i in range(200):
                    pk = (thread_id * 200 + i).to_bytes(32, "big")
                    f.check_and_add(pk)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

    def test_concurrent_count_accuracy(self):
        """并发下 checks_total 准确"""
        f = DeduplicationFilter(max_size=100000)
        n_threads = 10
        n_per_thread = 500

        def worker(thread_id: int):
            for i in range(n_per_thread):
                pk = (thread_id * 1000000 + i).to_bytes(32, "big")
                f.check_and_add(pk)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = f.get_stats()
        assert stats["checks_total"] == n_threads * n_per_thread

    def test_duplicate_detection_concurrent(self):
        """并发下重复检测有效（同一批私钥多个线程并发检查）"""
        f = DeduplicationFilter(max_size=10000)
        shared_keys = [i.to_bytes(32, "big") for i in range(100)]
        pass_counts = []

        def worker():
            count = 0
            for pk in shared_keys:
                if f.check_and_add(pk):
                    count += 1
            pass_counts.append(count)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 总通过数不超过 100（每个键最多通过一次）
        total_pass = sum(pass_counts)
        assert total_pass <= 100


class TestDeduplicationFilterGetStats:
    """get_stats() 测试"""

    def test_get_stats_structure(self):
        """get_stats 返回正确的字典结构"""
        f = DeduplicationFilter(max_size=1000)
        for i in range(10):
            f.check_and_add(i.to_bytes(32, "big"))
        stats = f.get_stats()

        assert "unique_keys" in stats
        assert "unique_addresses" in stats
        assert "duplicates_found" in stats
        assert "checks_total" in stats
        assert "max_size" in stats
        assert "enabled" in stats

    def test_get_stats_values(self):
        """get_stats 返回正确的数值"""
        f = DeduplicationFilter(max_size=1000)
        pk = b"\xaa" * 32
        f.check_and_add(pk)
        f.check_and_add(pk)  # 重复

        stats = f.get_stats()
        assert stats["checks_total"] == 2
        assert stats["duplicates_found"] == 1
        assert stats["unique_keys"] == 1
        assert stats["unique_addresses"] == 0
        assert stats["enabled"]
        assert stats["max_size"] == 1000


class TestDeduplicationFilterReset:
    """reset() / clear() 测试"""

    def test_reset_clears_all_tracking(self):
        """Reset 清除所有跟踪数据"""
        f = DeduplicationFilter(max_size=1000)
        for i in range(10):
            f.check_and_add(i.to_bytes(32, "big"))
        # 确认有数据
        assert f.get_stats()["checks_total"] > 0

        f.reset()

        stats = f.get_stats()
        assert stats["checks_total"] == 0
        assert stats["duplicates_found"] == 0
        assert len(f._seen_keys) == 0
        assert len(f._seen_addresses) == 0

    def test_reset_then_reuse(self):
        """Reset 后可正常使用"""
        f = DeduplicationFilter(max_size=1000)
        f.check_and_add(b"key1".ljust(32, b"\x00"))
        f.reset()
        # 重置后可以再次添加
        assert f.check_and_add(b"key2".ljust(32, b"\x00"))
        assert f.get_stats()["checks_total"] == 1

    def test_reset_with_duplicates(self):
        """Reset 清除重复计数"""
        f = DeduplicationFilter(max_size=1000)
        pk = b"dup".ljust(32, b"\x00")
        f.check_and_add(pk)
        f.check_and_add(pk)  # 重复
        assert f.get_stats()["duplicates_found"] == 1

        f.reset()
        assert f.get_stats()["duplicates_found"] == 0
        # 之前的重复键可以再次通过
        assert f.check_and_add(pk)

    def test_clear_alias(self):
        """clear() 是 reset() 的别名"""
        f = DeduplicationFilter(max_size=100)
        f.check_and_add(b"\x01" * 32)
        f.clear()
        assert f.get_stats()["checks_total"] == 0


if __name__ == "__main__":
    unittest.main(verbosity=2)
