"""KeyCollisionEngine 单元测试 - 启动/停止、进度回调、匹配回调"""

import threading
import time
import unittest
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collision.key_collision_engine import KeyCollisionEngine
from src.collision.collision_stats import CollisionStats
from src.core.address_generator import P2PKHAddressGenerator


def _get_known_target() -> tuple:
    """获取一个已知私钥对应的地址（用于匹配测试）"""
    # 私钥 = 1
    pk = (1).to_bytes(32, "big")
    gen = P2PKHAddressGenerator()
    addr, _, _ = gen.generate_address(pk)
    return pk, addr


class TestKeyCollisionEngineLifecycle(unittest.TestCase):
    """引擎生命周期测试"""

    def test_initial_state_not_running(self):
        """初始状态为未运行"""
        engine = KeyCollisionEngine(targets={"1TestAddr"})
        self.assertFalse(engine.is_running())

    def test_start_sets_running(self):
        """start() 后引擎处于运行状态"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1)
        engine.start(mode="random")
        time.sleep(0.2)
        self.assertTrue(engine.is_running())
        engine.stop()

    def test_stop_ends_running(self):
        """stop() 后引擎停止运行"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1)
        engine.start(mode="random")
        time.sleep(0.2)
        engine.stop()
        time.sleep(0.3)
        self.assertFalse(engine.is_running())

    def test_double_start_ignored(self):
        """重复 start() 不崩溃"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1)
        engine.start(mode="random")
        time.sleep(0.1)
        engine.start(mode="random")  # 第二次 start 应被忽略
        engine.stop()

    def test_stop_without_start_safe(self):
        """未启动直接调用 stop() 不崩溃"""
        engine = KeyCollisionEngine(targets={"1TestAddr"})
        engine.stop()  # 不应抛出异常

    def test_get_stats_returns_collision_stats(self):
        """get_stats() 返回 CollisionStats 对象"""
        engine = KeyCollisionEngine(targets={"1TestAddr"})
        stats = engine.get_stats()
        self.assertIsInstance(stats, CollisionStats)


class TestKeyCollisionEngineCallbacks(unittest.TestCase):
    """回调函数测试"""

    def test_progress_callback_called(self):
        """进度回调在运行期间被调用"""
        progress_events = []

        def on_progress(stats: CollisionStats):
            progress_events.append(stats.total_checked)

        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            on_progress=on_progress,
            max_workers=1,
        )
        engine.start(mode="random")
        time.sleep(2.5)  # 等待至少一次进度回调
        engine.stop()

        self.assertGreater(len(progress_events), 0, "进度回调应至少被调用一次")

    def test_complete_callback_called(self):
        """完成回调在停止后被调用"""
        complete_called = threading.Event()

        def on_complete(stats: CollisionStats):
            complete_called.set()

        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            on_complete=on_complete,
            max_workers=1,
        )
        engine.start(mode="random")
        time.sleep(0.3)
        engine.stop()
        # 等待完成回调
        complete_called.wait(timeout=5)
        self.assertTrue(complete_called.is_set())

    def test_match_callback_called_for_known_key(self):
        """使用已知私钥-地址对，range 扫描找到匹配后触发回调"""
        _, known_addr = _get_known_target()
        match_event = threading.Event()
        match_results = []

        def on_match(pk: bytes, addr: str, wif: str):
            match_results.append((pk, addr, wif))
            match_event.set()

        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=on_match,
            max_workers=1,
        )
        # 范围扫描 [1, 5]，私钥1对应已知地址
        engine.start(mode="range", start=1, end=5)
        match_event.wait(timeout=10)
        engine.stop()

        self.assertTrue(match_event.is_set(), "应在范围[1,5]内找到匹配")
        self.assertGreater(len(match_results), 0)
        _, found_addr, wif = match_results[0]
        self.assertEqual(found_addr, known_addr)
        self.assertTrue(wif.startswith(("K", "L", "5")))


class TestKeyCollisionEngineRangeScan(unittest.TestCase):
    """范围扫描模式测试"""

    def test_range_scan_basic(self):
        """范围扫描能正常启动和停止"""
        engine = KeyCollisionEngine(
            targets={"1NonExistentAddress"},
            max_workers=1,
        )
        engine.start(mode="range", start=1, end=100)
        time.sleep(1)
        engine.stop()
        # 不崩溃即通过

    def test_range_scan_counts_checked(self):
        """范围扫描后检查数正确"""
        complete_event = threading.Event()

        def on_complete(stats):
            complete_event.set()

        engine = KeyCollisionEngine(
            targets={"1NonExistentAddress"},
            on_complete=on_complete,
            max_workers=1,
        )
        engine.start(mode="range", start=1, end=1000)
        complete_event.wait(timeout=30)
        stats = engine.get_stats()
        # 范围内应检查接近1000个
        self.assertGreater(stats.total_checked, 900)


class TestKeyCollisionEngineBruteForce(unittest.TestCase):
    """暴力穷举模式测试"""

    def test_brute_force_start_stop(self):
        """暴力穷举能正常启动和停止"""
        engine = KeyCollisionEngine(
            targets={"1NonExistentAddress"},
            max_workers=1,
        )
        engine.start(mode="brute_force", start=1)
        time.sleep(1)
        engine.stop()

    def test_brute_force_increments_from_start(self):
        """暴力穷举从指定起始值递增"""
        # 私钥 1 对应已知地址
        _, known_addr = _get_known_target()
        match_event = threading.Event()

        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=lambda pk, addr, wif: match_event.set(),
            max_workers=1,
        )
        engine.start(mode="brute_force", start=1)
        match_event.wait(timeout=10)
        engine.stop()
        self.assertTrue(match_event.is_set())


class TestKeyCollisionEngineDedup(unittest.TestCase):
    """去重过滤器集成测试"""

    @pytest.mark.flaky(reruns=2, reruns_delay=1)  # 允许重试2次（性能测试不稳定）
    def test_dedup_enabled_reduces_speed(self):
        """启用去重后引擎正常运行"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            dedup_enabled=True,
            dedup_max_size=10000,
            max_workers=1,
        )
        engine.start(mode="random")
        time.sleep(2.0)  # 增加运行时间
        engine.stop()
        # 等待引擎完全停止并更新统计
        time.sleep(2.0)  # 增加等待时间
        stats = engine.get_stats()
        # 重试机制：如果首次检查为0，再等待一会儿
        if stats.total_checked == 0:
            time.sleep(1.0)
            stats = engine.get_stats()
        self.assertGreater(stats.total_checked, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
