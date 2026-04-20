"""DeduplicationFilter 单元测试 - 双缓冲轮换、内存上限、并发安全"""
import threading
import time
import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collision.deduplication_filter import DeduplicationFilter


class TestDeduplicationFilterBasic(unittest.TestCase):
    """基础功能测试"""

    def test_first_check_passes(self):
        """首次检查返回 True（允许通过）"""
        f = DeduplicationFilter(max_size=100)
        pk = bytes(range(32))
        self.assertTrue(f.check_and_add(pk))

    def test_duplicate_blocked(self):
        """重复私钥被拦截"""
        f = DeduplicationFilter(max_size=100)
        pk = bytes(range(32))
        f.check_and_add(pk)
        self.assertFalse(f.check_and_add(pk))

    def test_different_keys_pass(self):
        """不同私钥都能通过"""
        f = DeduplicationFilter(max_size=1000)
        for i in range(100):
            pk = i.to_bytes(32, 'big')
            self.assertTrue(f.check_and_add(pk), f"私钥 {i} 应通过")

    def test_disabled_always_returns_true(self):
        """禁用状态始终返回 True"""
        f = DeduplicationFilter(max_size=100, enabled=False)
        pk = bytes(32)
        self.assertTrue(f.check_and_add(pk))
        self.assertTrue(f.check_and_add(pk))
        self.assertTrue(f.check_and_add(pk))

    def test_stats_tracking(self):
        """统计计数正确"""
        f = DeduplicationFilter(max_size=100)
        pk1 = b'\x01' * 32
        pk2 = b'\x02' * 32
        f.check_and_add(pk1)
        f.check_and_add(pk1)  # 重复
        f.check_and_add(pk2)

        self.assertEqual(f.checks_total, 3)
        self.assertEqual(f.duplicates_found, 1)


class TestDeduplicationFilterDoubleBuffer(unittest.TestCase):
    """双缓冲轮换测试"""

    def test_buffer_rotation(self):
        """缓冲区满时正确轮换"""
        max_size = 100
        f = DeduplicationFilter(max_size=max_size)
        half = max_size // 2

        # 填满半个缓冲区，触发轮换
        for i in range(half + 5):
            pk = i.to_bytes(32, 'big')
            f.check_and_add(pk)

        # 轮换后 current 应被清空，pending 应有数据
        self.assertGreater(len(f._pending), 0)
        self.assertLessEqual(len(f._current), 5)

    def test_memory_bounded(self):
        """最大跟踪量不超过 max_size"""
        max_size = 200
        f = DeduplicationFilter(max_size=max_size)
        for i in range(max_size * 2):
            pk = i.to_bytes(32, 'big')
            f.check_and_add(pk)
        total_tracked = len(f._current) + len(f._pending)
        self.assertLessEqual(total_tracked, max_size)

    def test_old_keys_may_reappear(self):
        """超出容量的旧键在轮换后可能重新通过（正常行为）"""
        max_size = 20
        f = DeduplicationFilter(max_size=max_size)
        # 填入超出 max_size 的键
        for i in range(max_size + 10):
            pk = i.to_bytes(32, 'big')
            f.check_and_add(pk)
        # 此时早期键可能已被淘汰，不断言具体行为，只验证不崩溃
        pk_old = (0).to_bytes(32, 'big')
        result = f.check_and_add(pk_old)
        self.assertIsInstance(result, bool)


class TestDeduplicationFilterConcurrency(unittest.TestCase):
    """多线程并发测试"""

    def test_concurrent_checks_no_crash(self):
        """多线程并发检查不崩溃"""
        f = DeduplicationFilter(max_size=10000)
        errors = []

        def worker(thread_id: int):
            try:
                for i in range(200):
                    pk = (thread_id * 200 + i).to_bytes(32, 'big')
                    f.check_and_add(pk)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])

    def test_concurrent_count_accuracy(self):
        """并发下 checks_total 准确"""
        f = DeduplicationFilter(max_size=100000)
        n_threads = 10
        n_per_thread = 500

        def worker(thread_id: int):
            for i in range(n_per_thread):
                pk = (thread_id * 1000000 + i).to_bytes(32, 'big')
                f.check_and_add(pk)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(f.checks_total, n_threads * n_per_thread)

    def test_duplicate_detection_concurrent(self):
        """并发下重复检测有效（同一批私钥多个线程并发检查）"""
        f = DeduplicationFilter(max_size=10000)
        shared_keys = [i.to_bytes(32, 'big') for i in range(100)]
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
        self.assertLessEqual(total_pass, 100)


class TestDeduplicationFilterGetStats(unittest.TestCase):
    """get_stats() 测试"""

    def test_get_stats_structure(self):
        """get_stats 返回正确的字典结构"""
        f = DeduplicationFilter(max_size=1000)
        for i in range(10):
            f.check_and_add(i.to_bytes(32, 'big'))
        stats = f.get_stats()

        self.assertIn("tracked_total", stats)
        self.assertIn("duplicates_found", stats)
        self.assertIn("checks_total", stats)
        self.assertIn("duplicate_rate", stats)
        self.assertIn("max_size", stats)

    def test_get_stats_values(self):
        """get_stats 返回正确的数值"""
        f = DeduplicationFilter(max_size=1000)
        pk = b'\xAA' * 32
        f.check_and_add(pk)
        f.check_and_add(pk)  # 重复

        stats = f.get_stats()
        self.assertEqual(stats["checks_total"], 2)
        self.assertEqual(stats["duplicates_found"], 1)
        self.assertAlmostEqual(stats["duplicate_rate"], 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
