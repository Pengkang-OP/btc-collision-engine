"""CollisionStats 单元测试 - 线程安全、snapshot、add_match 不存私钥"""

import hashlib
import threading
import time
import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collision.collision_stats import CollisionStats  # noqa: E402


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
            pk = (i + 1).to_bytes(32, "big")
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
        self.assertRegex(result, r"^\d{2}:\d{2}:\d{2}$")


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
        stats.add_match(b"\x01" * 32, "1Another")

        self.assertEqual(snap.total_checked, 500)
        self.assertEqual(len(snap.matches), 1)

    def test_snapshot_contains_correct_data(self):
        """snapshot 包含正确数据"""
        stats = CollisionStats()
        stats.start_time = time.time()
        stats.update(1234)
        snap = stats.snapshot()
        self.assertEqual(snap.total_checked, 1234)


class TestCollisionStatsIncrement(unittest.TestCase):
    """increment() 增量更新测试"""

    def setUp(self):
        self.stats = CollisionStats()
        self.stats.start_time = time.time() - 1  # 1秒前启动，确保 elapsed > 0

    def test_increment_adds_to_total(self):
        """increment 累加到 total_checked"""
        self.stats.increment(100)
        self.assertEqual(self.stats.total_checked, 100)
        self.stats.increment(50)
        self.assertEqual(self.stats.total_checked, 150)

    def test_increment_zero_delta(self):
        """increment delta=0 合法"""
        self.stats.increment(0)
        self.assertEqual(self.stats.total_checked, 0)

    def test_increment_negative_delta_raises(self):
        """increment delta<0 触发 AssertionError"""
        with self.assertRaises(AssertionError):
            self.stats.increment(-1)

    def test_increment_with_total_range(self):
        """increment 设置 total_range 并计算 ETA"""
        self.stats.increment(100, total_range=1000)
        self.assertEqual(self.stats.total_range, 1000)
        self.assertGreater(self.stats.eta_seconds, 0)

    def test_increment_multiple_times(self):
        """多次 increment 累计正确"""
        for i in range(5):
            self.stats.increment(200)
        self.assertEqual(self.stats.total_checked, 1000)


class TestCollisionStatsETA(unittest.TestCase):
    """ETA 计算测试"""

    def setUp(self):
        self.stats = CollisionStats()
        self.stats.start_time = time.time() - 10  # 10秒前启动

    def test_eta_calculated_when_range_and_speed(self):
        """有范围和速度时 ETA 正常计算"""
        self.stats.update(500, total_range=2000)
        self.assertGreater(self.stats.eta_seconds, 0)
        self.assertLess(self.stats.eta_seconds, 1000)

    def test_eta_not_calculated_when_no_range(self):
        """无范围时 ETA = -1"""
        self.stats.update(500)
        self.assertEqual(self.stats.eta_seconds, -1.0)

    def test_eta_zero_when_complete(self):
        """已完成时 ETA = 0"""
        self.stats.update(1000, total_range=1000)
        self.assertEqual(self.stats.eta_seconds, 0.0)


class TestCollisionStatsReset(unittest.TestCase):
    """reset() 线程安全重置测试"""

    def setUp(self):
        self.stats = CollisionStats()
        self.stats.start_time = time.time()

    def test_reset_clears_all_counters(self):
        """reset 清除所有计数器"""
        self.stats.update(500)
        self.stats.gpu_errors = 3
        self.stats.worker_errors = 2
        self.stats.wif_encode_errors = 1
        self.stats.resource_errors = 1
        pk = (1).to_bytes(32, "big")
        self.stats.add_match(pk, "1Addr")

        self.stats.reset()

        self.assertEqual(self.stats.total_checked, 0)
        self.assertEqual(self.stats.speed, 0.0)
        self.assertEqual(len(self.stats.matches), 0)
        self.assertEqual(self.stats._match_count, 0)
        self.assertEqual(self.stats.total_range, 0)
        self.assertEqual(self.stats.eta_seconds, -1.0)
        self.assertEqual(self.stats.gpu_errors, 0)
        self.assertEqual(self.stats.worker_errors, 0)
        self.assertEqual(self.stats.wif_encode_errors, 0)
        self.assertEqual(self.stats.resource_errors, 0)

    def test_reset_updates_start_time(self):
        """reset 更新 start_time"""
        old_start = self.stats.start_time
        self.stats.update(100)
        self.stats.reset()
        self.assertGreaterEqual(self.stats.start_time, old_start)

    def test_reset_clears_progress_percent_if_present(self):
        """reset 清除 _progress_percent"""
        self.stats._progress_percent = 75.0
        self.stats.reset()
        self.assertEqual(self.stats._progress_percent, 0.0)

    def test_reset_then_reuse(self):
        """reset 后可正常使用"""
        self.stats.update(100)
        self.stats.reset()
        self.stats.start_time = time.time()
        self.stats.update(200)
        self.assertEqual(self.stats.total_checked, 200)


class TestCollisionStatsFormatSpeed(unittest.TestCase):
    """format_speed 各种量级测试"""

    def setUp(self):
        self.stats = CollisionStats()

    def test_format_speed_zero(self):
        """速度为 0"""
        result = self.stats.format_speed()
        self.assertIn("/s", result)

    def test_format_speed_k(self):
        """K/s 级别"""
        self.stats.speed = 5000
        result = self.stats.format_speed()
        self.assertIn("K/s", result)

    def test_format_speed_m(self):
        """M/s 级别"""
        self.stats.speed = 5_000_000
        result = self.stats.format_speed()
        self.assertIn("M/s", result)

    def test_format_speed_below_thousand(self):
        """/s 级别"""
        self.stats.speed = 500
        result = self.stats.format_speed()
        self.assertIn("/s", result)
        self.assertNotIn("K/s", result)
        self.assertNotIn("M/s", result)


class TestCollisionStatsGetters(unittest.TestCase):
    """get_total_checked / get_elapsed / get_speed 测试"""

    def setUp(self):
        self.stats = CollisionStats()

    def test_get_total_checked(self):
        """get_total_checked 线程安全"""
        self.stats.total_checked = 42
        self.assertEqual(self.stats.get_total_checked(), 42)

    def test_get_elapsed(self):
        """get_elapsed 线程安全"""
        self.stats.elapsed = 12.5
        self.assertEqual(self.stats.get_elapsed(), 12.5)

    def test_get_speed(self):
        """get_speed 线程安全"""
        self.stats.speed = 1500.0
        self.assertEqual(self.stats.get_speed(), 1500.0)


class TestCollisionStatsSnapshotProgressPercent(unittest.TestCase):
    """snapshot 包含 _progress_percent"""

    def test_snapshot_copies_progress_percent_if_present(self):
        """snapshot 拷贝 _progress_percent"""
        stats = CollisionStats()
        stats._progress_percent = 42.5
        snap = stats.snapshot()
        self.assertTrue(hasattr(snap, "_progress_percent"))
        self.assertEqual(snap._progress_percent, 42.5)

    def test_snapshot_ok_without_progress_percent(self):
        """snapshot 无 _progress_percent 时正常"""
        stats = CollisionStats()
        # 不要设置 _progress_percent
        if hasattr(stats, "_progress_percent"):
            delattr(stats, "_progress_percent")
        snap = stats.snapshot()
        self.assertIsNotNone(snap)


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
                pk = (thread_id * n_per_thread + i + 1).to_bytes(32, "big")
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




class TestCollisionStatsErrorTracking(unittest.TestCase):
    """record_*_error 和 get_error_rates 测试"""

    def setUp(self):
        self.stats = CollisionStats()
        self.stats.total_checked = 1000  # 避免除零

    def test_record_gpu_error(self):
        """record_gpu_error 递增 gpu_errors"""
        self.stats.record_gpu_error()
        self.assertEqual(self.stats.gpu_errors, 1)
        self.assertEqual(self.stats.resource_errors, 0)

    def test_record_gpu_error_as_resource(self):
        """record_gpu_error(is_resource_error=True) 同时递增 resource_errors"""
        self.stats.record_gpu_error(is_resource_error=True)
        self.assertEqual(self.stats.gpu_errors, 1)
        self.assertEqual(self.stats.resource_errors, 1)

    def test_record_worker_error(self):
        """record_worker_error 递增 worker_errors"""
        self.stats.record_worker_error()
        self.assertEqual(self.stats.worker_errors, 1)

    def test_record_wif_encode_error(self):
        """record_wif_encode_error 递增 wif_encode_errors"""
        self.stats.record_wif_encode_error()
        self.assertEqual(self.stats.wif_encode_errors, 1)

    def test_get_error_rates_zero_checked(self):
        """total_checked=0 时所有错误率为 0"""
        self.stats.total_checked = 0
        self.stats.gpu_errors = 5
        rates = self.stats.get_error_rates()
        self.assertEqual(rates["total_error_rate"], 0.0)
        self.assertEqual(rates["gpu_error_rate"], 0.0)
        self.assertEqual(rates["worker_error_rate"], 0.0)
        self.assertEqual(rates["wif_encode_error_rate"], 0.0)
        self.assertEqual(rates["resource_error_rate"], 0.0)

    def test_get_error_rates_normal(self):
        """正常错误率计算"""
        self.stats.gpu_errors = 10
        self.stats.worker_errors = 5
        self.stats.wif_encode_errors = 2
        self.stats.resource_errors = 3
        rates = self.stats.get_error_rates()
        self.assertAlmostEqual(rates["total_error_rate"], 15 / 1000)
        self.assertAlmostEqual(rates["gpu_error_rate"], 10 / 1000)
        self.assertAlmostEqual(rates["worker_error_rate"], 5 / 1000)
        self.assertAlmostEqual(rates["wif_encode_error_rate"], 2 / 1000)
        self.assertAlmostEqual(rates["resource_error_rate"], 3 / 1000)

    def test_get_error_rates_all_zero(self):
        """无错误时所有错误率为 0"""
        rates = self.stats.get_error_rates()
        for rate in rates.values():
            self.assertEqual(rate, 0.0)


class TestCollisionStatsHealthCheck(unittest.TestCase):
    """is_healthy 和 error_summary 测试"""

    def setUp(self):
        self.stats = CollisionStats()
        self.stats.total_checked = 10000

    def test_is_healthy_default_threshold(self):
        """默认阈值 1%，无错误时健康"""
        self.assertTrue(self.stats.is_healthy())

    def test_is_healthy_below_threshold(self):
        """错误率低于阈值"""
        self.stats.gpu_errors = 50  # 0.5%
        self.assertTrue(self.stats.is_healthy())

    def test_is_healthy_above_threshold(self):
        """错误率超过阈值"""
        self.stats.gpu_errors = 200  # 2%%
        self.assertFalse(self.stats.is_healthy())

    def test_is_healthy_custom_threshold(self):
        """自定义阈值"""
        self.stats.gpu_errors = 500  # 5%%
        self.assertTrue(self.stats.is_healthy(error_rate_threshold=0.1))
        self.assertFalse(self.stats.is_healthy(error_rate_threshold=0.01))

    def test_is_healthy_total_error_includes_both(self):
        """总错误率 = gpu + worker"""
        self.stats.gpu_errors = 100   # 1%%
        self.stats.worker_errors = 50  # 0.5%%
        # total_error_rate = 150/10000 = 1.5%% > 1%%
        self.assertFalse(self.stats.is_healthy())

    def test_error_summary_format(self):
        """error_summary 格式正确"""
        self.stats.gpu_errors = 3
        self.stats.worker_errors = 2
        self.stats.wif_encode_errors = 1
        self.stats.resource_errors = 1
        summary = self.stats.error_summary()
        self.assertIn("GPU=3", summary)
        self.assertIn("Worker=2", summary)
        self.assertIn("WIF=1", summary)
        self.assertIn("Resource=1", summary)
        self.assertIn("总计=5", summary)

    def test_error_summary_zero_errors(self):
        """无错误时的摘要"""
        summary = self.stats.error_summary()
        self.assertIn("GPU=0", summary)
        self.assertIn("Worker=0", summary)
        self.assertIn("总计=0", summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
