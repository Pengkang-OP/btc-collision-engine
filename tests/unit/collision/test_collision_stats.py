"""CollisionStats 单元测试 — 对齐 src/collision/collision_stats.py 真实 API"""

import hashlib
import threading
import pytest

from src.collision.collision_stats import CollisionStats, StatsSnapshot


class TestCollisionStatsInit:
    """初始化测试"""

    def test_initial_state(self):
        stats = CollisionStats()
        assert stats.total_checked  ==  0
        assert stats.matches_found  ==  0
        assert len(stats.matches)  ==  0
        assert isinstance(stats.start_time, float)
        assert stats.start_time  >  0

    def test_default_throughput_is_zero(self):
        stats = CollisionStats()
        assert stats.avg_speed  ==  0.0


class TestCollisionStatsRecordKey:
    """record_key / record_keys 测试"""

    def setUp(self):
        self.stats = CollisionStats()

    def test_record_key_increments(self):
        self.stats.record_key()
        assert self.stats.total_checked  ==  1

    def test_record_keys_batch(self):
        self.stats.record_keys(100)
        assert self.stats.total_checked  ==  100

    def test_record_key_multiple(self):
        for _ in range(5):
            self.stats.record_key()
        assert self.stats.total_checked  ==  5


class TestCollisionStatsAddMatch:
    """add_match 测试 — 不存储私钥明文"""

    def setUp(self):
        self.stats = CollisionStats()

    def test_add_match_no_private_key(self):
        pk = bytes(range(32))
        self.stats.add_match(pk, "1TestAddress")
        assert len(self.stats.matches)  ==  1
        match = self.stats.matches[0]
        assert match  not in  "private_key_hex"
        assert match  not in  "private_key_wif"
        assert match  not in  "private_key"
        assert match["address"]  ==  "1TestAddress"

    def test_add_match_stores_hash(self):
        pk = bytes(range(32))
        self.stats.add_match(pk, "1TestAddress")
        match = self.stats.matches[0]
        expected_hash = hashlib.sha256(pk).hexdigest()[:16]
        assert match.get("private_key_hash")  ==  expected_hash

    def test_add_match_multiple(self):
        for i in range(5):
            pk = (i + 1).to_bytes(32, "big")
            self.stats.add_match(pk, f"1Address{i}")
        assert len(self.stats.matches)  ==  5
        assert self.stats.matches_found  ==  5

    def test_add_match_without_args(self):
        self.stats.add_match()
        assert self.stats.matches_found  ==  1
        assert len(self.stats.matches)  ==  0  # no pk or address → no entry

    def test_add_match_address_only(self):
        self.stats.add_match(address="1TestAddress")
        assert len(self.stats.matches)  ==  1
        assert self.stats.matches[0]["address"]  ==  "1TestAddress"
        assert self.stats.matches[0]  not in  "private_key_hash"


class TestCollisionStatsUpdate:
    """update() 测试"""

    def setUp(self):
        self.stats = CollisionStats()

    def test_update_sets_total_checked(self):
        self.stats.update(1000)
        assert self.stats.total_checked  ==  1000

    def test_update_zero_does_nothing(self):
        self.stats.update(0)
        assert self.stats.total_checked  ==  0

    def test_update_with_total_range(self):
        self.stats.update(total_range=5000)
        assert self.stats.total_checked  ==  5000


class TestCollisionStatsSnapshot:
    """snapshot() 测试 — 返回 StatsSnapshot dataclass"""

    def test_snapshot_returns_dataclass(self):
        stats = CollisionStats()
        stats.record_keys(500)
        snap = stats.snapshot()
        assert isinstance(snap, StatsSnapshot)
        assert snap.total_keys_checked  ==  500

    def test_snapshot_is_independent(self):
        stats = CollisionStats()
        stats.record_keys(500)
        stats.add_match(bytes(32), "1Addr")
        snap = stats.snapshot()

        stats.record_keys(9999)
        stats.add_match(b"\x01" * 32, "1Another")

        assert snap.total_keys_checked  ==  500
        assert snap.total_matches  ==  1

    def test_snapshot_keys(self):
        stats = CollisionStats()
        snap = stats.snapshot()
        assert snap.total_keys_checked  ==  0
        assert snap.total_matches  ==  0
        assert snap.total_errors  ==  0
        assert snap.elapsed_seconds  >=  0
        assert snap.throughput  >=  0
        assert isinstance(snap.matches, list)


class TestCollisionStatsToDict:
    """to_dict() 测试"""

    def test_to_dict_basic(self):
        stats = CollisionStats()
        stats.record_keys(1000)
        d = stats.to_dict()
        assert d["total_keys_checked"]  ==  1000
        assert d["total_matches"]  ==  0
        assert d["total_errors"]  ==  0

    def test_to_dict_has_throughput(self):
        stats = CollisionStats()
        d = stats.to_dict()
        assert d  in  "throughput"
        assert isinstance(d["throughput"], float)


class TestCollisionStatsAvgSpeed:
    """avg_speed / get_throughput 测试"""

    def test_avg_speed_initial_zero(self):
        stats = CollisionStats()
        assert stats.avg_speed  ==  0.0

    def test_get_throughput(self):
        stats = CollisionStats()
        assert stats.get_throughput()  ==  0.0


class TestCollisionStatsGet:
    """dict-like get() 兼容访问"""

    def setUp(self):
        self.stats = CollisionStats()

    def test_get_total_checked(self):
        self.stats.record_keys(42)
        assert self.stats.get("total_checked")  ==  42

    def test_get_speed(self):
        assert self.stats.get("speed")  ==  0.0

    def test_get_matches_found(self):
        assert self.stats.get("matches_found")  ==  0

    def test_get_elapsed(self):
        elapsed = self.stats.get("elapsed")
        assert isinstance(elapsed, float)
        assert elapsed  >=  0

    def test_get_unknown_key_returns_default(self):
        assert self.stats.get("nonexistent")  ==  None
        assert self.stats.get("nonexistent", 42)  ==  42


class TestCollisionStatsRecordMatch:
    """record_match 测试"""

    def test_record_match_increments(self):
        stats = CollisionStats()
        stats.record_match()
        stats.record_match()
        assert stats.matches_found  ==  2


class TestCollisionStatsReset:
    """reset() 测试"""

    def test_reset_clears_counters(self):
        """reset() 清零所有内部计数器包括 matches 列表"""
        stats = CollisionStats()
        stats.record_keys(500)
        stats.record_match()
        stats.record_error()
        stats.add_match(bytes(32), "1Addr")

        stats.reset()

        assert stats.total_checked  ==  0
        assert stats.matches_found  ==  0
        # matches 列表也被清空（源码 reset() 调用 self.matches.clear()）
        assert len(stats.matches)  ==  0
        # to_dict 中 total_errors 也清零
        assert stats.to_dict()["total_errors"]  ==  0

    def test_reset_updates_start_time(self):
        stats = CollisionStats()
        old_start = stats.start_time
        stats.record_keys(100)
        stats.reset()
        assert stats.start_time  >=  old_start

    def test_reset_then_reuse(self):
        stats = CollisionStats()
        stats.record_keys(100)
        stats.reset()
        stats.record_keys(200)
        assert stats.total_checked  ==  200


class TestCollisionStatsRecordError:
    """record_error 测试"""

    def test_record_error_increments(self):
        stats = CollisionStats()
        stats.record_error()
        stats.record_error()
        assert stats.to_dict()["total_errors"]  ==  2


class TestCollisionStatsThreadSafety:
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

        assert len(stats.matches)  ==  n_threads * n_per_thread

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

        assert errors  ==  []
        assert stats.total_checked  ==  500


if __name__ == "__main__":
    unittest.main(verbosity=2)
