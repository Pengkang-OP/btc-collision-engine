"""CollisionStats 单元测试 — 对齐 src/collision/collision_stats.py 真实 API"""

import hashlib
import threading
import time
import unittest

from src.collision.collision_stats import CollisionStats


class TestCollisionStatsInit(unittest.TestCase):
    """初始化测试"""

    def test_initial_state(self):
        stats = CollisionStats()
        self.assertEqual(stats.total_checked, 0)
        self.assertEqual(stats.matches_found, 0)
        self.assertEqual(len(stats.matches), 0)
        self.assertIsInstance(stats.start_time, float)
        self.assertGreater(stats.start_time, 0)

    def test_default_throughput_is_zero(self):
        stats = CollisionStats()
        self.assertEqual(stats.avg_speed, 0.0)


class TestCollisionStatsRecordKey(unittest.TestCase):
    """record_key / record_keys 测试"""

    def setUp(self):
        self.stats = CollisionStats()

    def test_record_key_increments(self):
        self.stats.record_key()
        self.assertEqual(self.stats.total_checked, 1)

    def test_record_keys_batch(self):
        self.stats.record_keys(100)
        self.assertEqual(self.stats.total_checked, 100)

    def test_record_key_multiple(self):
        for _ in range(5):
            self.stats.record_key()
        self.assertEqual(self.stats.total_checked, 5)


class TestCollisionStatsAddMatch(unittest.TestCase):
    """add_match 测试 — 不存储私钥明文"""

    def setUp(self):
        self.stats = CollisionStats()

    def test_add_match_no_private_key(self):
        pk = bytes(range(32))
        self.stats.add_match(pk, "1TestAddress")
        self.assertEqual(len(self.stats.matches), 1)
        match = self.stats.matches[0]
        self.assertNotIn("private_key_hex", match)
        self.assertNotIn("private_key_wif", match)
        self.assertNotIn("private_key", match)
        self.assertEqual(match["address"], "1TestAddress")

    def test_add_match_stores_hash(self):
        pk = bytes(range(32))
        self.stats.add_match(pk, "1TestAddress")
        match = self.stats.matches[0]
        expected_hash = hashlib.sha256(pk).hexdigest()[:16]
        self.assertEqual(match.get("private_key_hash"), expected_hash)

    def test_add_match_multiple(self):
        for i in range(5):
            pk = (i + 1).to_bytes(32, "big")
            self.stats.add_match(pk, f"1Address{i}")
        self.assertEqual(len(self.stats.matches), 5)
        self.assertEqual(self.stats.matches_found, 5)

    def test_add_match_without_args(self):
        self.stats.add_match()
        self.assertEqual(self.stats.matches_found, 1)
        self.assertEqual(len(self.stats.matches), 0)  # no pk or address → no entry

    def test_add_match_address_only(self):
        self.stats.add_match(address="1TestAddress")
        self.assertEqual(len(self.stats.matches), 1)
        self.assertEqual(self.stats.matches[0]["address"], "1TestAddress")
        self.assertNotIn("private_key_hash", self.stats.matches[0])


class TestCollisionStatsUpdate(unittest.TestCase):
    """update() 测试"""

    def setUp(self):
        self.stats = CollisionStats()

    def test_update_sets_total_checked(self):
        self.stats.update(1000)
        self.assertEqual(self.stats.total_checked, 1000)

    def test_update_zero_does_nothing(self):
        self.stats.update(0)
        self.assertEqual(self.stats.total_checked, 0)

    def test_update_with_total_range(self):
        self.stats.update(total_range=5000)
        self.assertEqual(self.stats.total_checked, 5000)


class TestCollisionStatsSnapshot(unittest.TestCase):
    """snapshot() 测试 — 返回 dict"""

    def test_snapshot_returns_dict(self):
        stats = CollisionStats()
        stats.record_keys(500)
        snap = stats.snapshot()
        self.assertIsInstance(snap, dict)
        self.assertEqual(snap["total_keys_checked"], 500)

    def test_snapshot_is_independent(self):
        stats = CollisionStats()
        stats.record_keys(500)
        stats.add_match(bytes(32), "1Addr")
        snap = stats.snapshot()

        stats.record_keys(9999)
        stats.add_match(b"\x01" * 32, "1Another")

        self.assertEqual(snap["total_keys_checked"], 500)
        self.assertEqual(snap["total_matches"], 1)

    def test_snapshot_keys(self):
        stats = CollisionStats()
        snap = stats.snapshot()
        for key in ["total_keys_checked", "total_matches", "total_errors", "elapsed_seconds", "throughput"]:
            self.assertIn(key, snap)


class TestCollisionStatsToDict(unittest.TestCase):
    """to_dict() 测试"""

    def test_to_dict_basic(self):
        stats = CollisionStats()
        stats.record_keys(1000)
        d = stats.to_dict()
        self.assertEqual(d["total_keys_checked"], 1000)
        self.assertEqual(d["total_matches"], 0)
        self.assertEqual(d["total_errors"], 0)

    def test_to_dict_has_throughput(self):
        stats = CollisionStats()
        d = stats.to_dict()
        self.assertIn("throughput", d)
        self.assertIsInstance(d["throughput"], float)


class TestCollisionStatsAvgSpeed(unittest.TestCase):
    """avg_speed / get_throughput 测试"""

    def test_avg_speed_initial_zero(self):
        stats = CollisionStats()
        self.assertEqual(stats.avg_speed, 0.0)

    def test_get_throughput(self):
        stats = CollisionStats()
        self.assertEqual(stats.get_throughput(), 0.0)


class TestCollisionStatsGet(unittest.TestCase):
    """dict-like get() 兼容访问"""

    def setUp(self):
        self.stats = CollisionStats()

    def test_get_total_checked(self):
        self.stats.record_keys(42)
        self.assertEqual(self.stats.get("total_checked"), 42)

    def test_get_speed(self):
        self.assertEqual(self.stats.get("speed"), 0.0)

    def test_get_matches_found(self):
        self.assertEqual(self.stats.get("matches_found"), 0)

    def test_get_elapsed(self):
        elapsed = self.stats.get("elapsed")
        self.assertIsInstance(elapsed, float)
        self.assertGreaterEqual(elapsed, 0)

    def test_get_unknown_key_returns_default(self):
        self.assertEqual(self.stats.get("nonexistent"), None)
        self.assertEqual(self.stats.get("nonexistent", 42), 42)


class TestCollisionStatsRecordMatch(unittest.TestCase):
    """record_match 测试"""

    def test_record_match_increments(self):
        stats = CollisionStats()
        stats.record_match()
        stats.record_match()
        self.assertEqual(stats.matches_found, 2)


class TestCollisionStatsReset(unittest.TestCase):
    """reset() 测试"""

    def test_reset_clears_counters(self):
        """reset() 清零内部计数器但保留 matches 列表"""
        stats = CollisionStats()
        stats.record_keys(500)
        stats.record_match()
        stats.record_error()
        stats.add_match(bytes(32), "1Addr")

        stats.reset()

        self.assertEqual(stats.total_checked, 0)
        self.assertEqual(stats.matches_found, 0)
        # matches 列表不自动清空
        self.assertEqual(len(stats.matches), 1)
        # to_dict 中 total_errors 也清零
        self.assertEqual(stats.to_dict()["total_errors"], 0)

    def test_reset_updates_start_time(self):
        stats = CollisionStats()
        old_start = stats.start_time
        stats.record_keys(100)
        stats.reset()
        self.assertGreaterEqual(stats.start_time, old_start)

    def test_reset_then_reuse(self):
        stats = CollisionStats()
        stats.record_keys(100)
        stats.reset()
        stats.record_keys(200)
        self.assertEqual(stats.total_checked, 200)


class TestCollisionStatsRecordError(unittest.TestCase):
    """record_error 测试"""

    def test_record_error_increments(self):
        stats = CollisionStats()
        stats.record_error()
        stats.record_error()
        self.assertEqual(stats.to_dict()["total_errors"], 2)


class TestCollisionStatsThreadSafety(unittest.TestCase):
    """多线程并发测试"""

    def test_concurrent_add_match(self):
        stats = CollisionStats()
        n_threads = 10
        n_per_thread = 100

        def add_matches(thread_id: int):
            for i in range(n_per_thread):
                pk = (thread_id * n_per_thread + i + 1).to_bytes(32, "big")
                stats.add_match(pk, f"1Addr{thread_id}_{i}")

        threads = [threading.Thread(target=add_matches, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(stats.matches), n_threads * n_per_thread)

    def test_concurrent_record_keys(self):
        stats = CollisionStats()
        errors = []

        def do_record():
            try:
                for _ in range(100):
                    stats.record_key()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_record) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertEqual(stats.total_checked, 500)


if __name__ == "__main__":
    unittest.main(verbosity=2)
