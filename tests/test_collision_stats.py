"""CollisionStats 单元测试 - 线程安全、snapshot、add_match 不存私钥"""
import hashlib
import threading
import time
import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collision.collision_stats import CollisionStats


class TestCollisionStatsBasic(unittest.TestCase):
    """基础功能测试"""

    def setUp(self):
        self.stats = CollisionStats()

    def test_initial_state(self):
        """初始状态校验"""
        self.assertEqual(self.stats.total_checked, 0)
        self.assertEqual(len(self.stats.matches), 0)
        # start_time 初始为 0.0 或 None（表示未启动）
        self.assertFalse(bool(self.stats.start_time))

    def test_update_increments_count(self):
        """update() 正确设置总检查数"""
        self.stats.start_time = time.time()
        self.stats.update(1000)
        self.assertEqual(self.stats.total_checked, 1000)

    def test_add_match_no_private_key(self):
        """add_match 不存储私钥明文"""
        pk = bytes(range(32))
        self.stats.add_match(pk, "1TestAddress")
        self.assertEqual(len(self.stats.matches), 1)
        match = self.stats.matches[0]
        # 不应有 private_key_hex 或 private_key_wif 字段
        self.assertNotIn("private_key_hex", match)
        self.assertNotIn("private_key_wif", match)
        self.assertNotIn("private_key", match)
        # 应有地址
        self.assertEqual(match["address"], "1TestAddress")

    def test_add_match_stores_hash(self):
        """add_match 存储私钥哈希（前16字符）"""
        pk = bytes(range(32))
        self.stats.add_match(pk, "1TestAddress")
        match = self.stats.matches[0]
        expected_hash = hashlib.sha256(pk).hexdigest()[:16]
        self.assertEqual(match.get("private_key_hash"), expected_hash)

    def test_add_match_multiple(self):
        """多次 add_match 计数正确"""
        for i in range(5):
            pk = (i + 1).to_bytes(32, 'big')
            self.stats.add_match(pk, f"1Address{i}")
        self.assertEqual(len(self.stats.matches), 5)
        self.assertEqual(self.stats._match_count, 5)

    def test_format_elapsed_initial(self):
        """未启动时 format_elapsed 返回合理值"""
        result = self.stats.format_elapsed()
        self.assertIsInstance(result, str)

    def test_format_speed_zero(self):
        """速度格式化（未运行时）"""
        result = self.stats.format_speed()
        self.assertIsInstance(result, str)

    def test_format_elapsed_running(self):
        """运行中 format_elapsed 格式正确"""
        self.stats.start_time = time.time() - 65  # 模拟65秒前启动
        result = self.stats.format_elapsed()
        # 应为 HH:MM:SS 格式
        self.assertRegex(result, r'^\d{2}:\d{2}:\d{2}$')


class TestCollisionStatsSnapshot(unittest.TestCase):
    """snapshot() 深拷贝测试"""

    def test_snapshot_independence(self):
        """snapshot 是独立副本，修改不影响原始数据"""
        stats = CollisionStats()
        stats.start_time = time.time()
        stats.update(500)
        pk = bytes(32)
        stats.add_match(pk, "1TestAddr")

        snap = stats.snapshot()
        # 修改原始 stats 不影响 snap
        stats.update(9999)
        stats.add_match(b'\x01' * 32, "1Another")

        self.assertEqual(snap.total_checked, 500)
        self.assertEqual(len(snap.matches), 1)

    def test_snapshot_contains_correct_data(self):
        """snapshot 包含正确数据"""
        stats = CollisionStats()
        stats.start_time = time.time()
        stats.update(1234)
        snap = stats.snapshot()
        self.assertEqual(snap.total_checked, 1234)


class TestCollisionStatsThreadSafety(unittest.TestCase):
    """多线程并发测试"""

    def test_concurrent_add_match(self):
        """并发 add_match 不丢失数据"""
        stats = CollisionStats()
        stats.start_time = time.time()
        n_threads = 10
        n_per_thread = 100

        def add_matches(thread_id: int):
            for i in range(n_per_thread):
                pk = (thread_id * n_per_thread + i + 1).to_bytes(32, 'big')
                stats.add_match(pk, f"1Addr{thread_id}_{i}")

        threads = [threading.Thread(target=add_matches, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(stats.matches), n_threads * n_per_thread)
        self.assertEqual(stats._match_count, n_threads * n_per_thread)

    def test_concurrent_update(self):
        """并发 update 不引发异常"""
        stats = CollisionStats()
        stats.start_time = time.time()
        errors = []

        def do_update():
            try:
                for i in range(100):
                    stats.update(i * 100)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_update) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
