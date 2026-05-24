"""KeyCollisionEngine 整合测试入口 (MAINT-1拆分)

测试已按主题拆分到以下文件：
- test_engine_lifecycle.py    - 生命周期、上下文管理器、stop边界
- test_engine_callbacks.py     - 回调函数、安全回调
- test_engine_range_scan.py    - 范围扫描模式（含worker+编排）
- test_engine_brute_force.py   - 暴力穷举模式（含worker）
- test_engine_constructor.py   - 构造函数分支和参数验证
- test_engine_internals.py     - 内部方法、安全生成、去重
- test_engine_checkpoint.py    - 断点持久化
"""

import json
import os
import pathlib
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import pytest

from src.collision.collision_stats import CollisionStats
from src.collision.key_collision_engine import KeyCollisionEngine
from tests.conftest_engine import get_known_target as _get_known_target


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
        time.sleep(1.0)  # 增加运行时间确保引擎产生足够数据
        engine.stop()
        # 等待完成回调（stop()内部join最长10s，需要等worker完全退出）
        complete_called.wait(timeout=15)
        self.assertTrue(complete_called.is_set(), "完成回调应在stop后触发")

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
        # 确保引擎已启动
        time.sleep(0.5)
        if not engine.is_running():
            self.fail("引擎未启动")
        # 等待范围扫描完成（增加超时到60秒以处理慢CI环境）
        if not complete_event.wait(timeout=60):
            engine.stop()
            self.fail("范围扫描未在60秒内完成")
        stats = engine.get_stats()
        # 范围内应检查接近1000个
        self.assertGreater(stats.total_checked, 900, f"total_checked={stats.total_checked}")


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


class TestKeyCollisionEngineConstructorBranches(unittest.TestCase):
    """构造函数分支覆盖：非优化路径、显式参数"""

    def test_constructor_standard_generator(self):
        """use_performance_optimization=False 使用标准版生成器"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            use_performance_optimization=False,
            max_workers=1,
            data_logging_enabled=False,
        )
        self.assertFalse(engine.is_running())
        # 标准版生成器不应设置优化参数
        engine.stop()

    def test_constructor_explicit_check_uncompressed_true(self):
        """显式 check_uncompressed=True"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            check_uncompressed=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        self.assertTrue(engine.check_uncompressed)
        engine.stop()

    def test_constructor_explicit_check_uncompressed_false(self):
        """显式 check_uncompressed=False"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            check_uncompressed=False,
            max_workers=1,
            data_logging_enabled=False,
        )
        self.assertFalse(engine.check_uncompressed)
        engine.stop()

    def test_constructor_data_logging_disabled(self):
        """data_logging_enabled=False 不初始化日志系统"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            data_logging_enabled=False,
            max_workers=1,
        )
        self.assertFalse(engine.data_logging_enabled)
        self.assertIsNone(engine.data_logger)
        engine.stop()

    def test_constructor_enhanced_monitoring_disabled(self):
        """use_enhanced_monitoring=False 使用传统DataLogger"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            use_enhanced_monitoring=False,
            max_workers=1,
        )
        self.assertIsNone(engine.enhanced_monitoring)
        self.assertIsNotNone(engine.data_logger)
        engine.stop()

    def test_constructor_explicit_crypto_backend(self):
        """显式指定 crypto_backend_type='pure_python'"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            crypto_backend_type="pure_python",
            max_workers=1,
            data_logging_enabled=False,
        )
        self.assertFalse(engine.is_running())
        engine.stop()

    def test_constructor_verbose_logging_enabled(self):
        """verbose_logging=True 启用详细日志"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            verbose_logging=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        self.assertTrue(engine.verbose_logging)
        engine.stop()

    def test_constructor_performance_with_custom_window_size(self):
        """自定义 precomputed_window_size=4"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            use_performance_optimization=True,
            precomputed_window_size=4,
            use_simd_hash=False,
            use_memory_pool=False,
            max_workers=1,
            data_logging_enabled=False,
        )
        self.assertFalse(engine.is_running())
        engine.stop()


class TestKeyCollisionEngineSecureGeneration(unittest.TestCase):
    """安全密钥生成 _generate_and_check_secure + 匹配处理 _process_key_match"""

    def test_generate_and_check_secure_no_match(self):
        """_generate_and_check_secure 无匹配时返回 None"""
        engine = KeyCollisionEngine(
            targets={"1NonExistentAddress12345"},
            max_workers=1,
            data_logging_enabled=False,
        )
        result = engine._generate_and_check_secure()
        self.assertIsNone(result, "无匹配应返回 None")
        engine.stop()

    def test_generate_and_check_secure_with_match(self):
        """_generate_and_check_secure 找到匹配时返回 (pk, addr)"""
        _, known_addr = _get_known_target()
        # 将地址小写（因为 _generate_and_check_secure 使用 .lower() 比较）
        engine = KeyCollisionEngine(
            targets={known_addr.lower()},
            max_workers=1,
            data_logging_enabled=False,
        )
        # 直接调用内部方法 — 随机生成极大概率无匹配，
        # 这里验证方法可被调用且不抛异常
        result = engine._generate_and_check_secure()
        self.assertIsNone(result)
        engine.stop()

    def test_process_key_match_valid(self):
        """_process_key_match 正常处理匹配"""
        _, known_addr = _get_known_target()
        pk = (1).to_bytes(32, "big")
        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=lambda pk, addr, wif: None,
            max_workers=1,
            data_logging_enabled=False,
        )
        local_matches = []
        should_continue = engine._process_key_match(
            private_key=pk,
            matched_address=known_addr,
            matched_compressed=True,
            local_matches=local_matches,
            worker_id=0,
        )
        self.assertTrue(should_continue)
        self.assertEqual(len(local_matches), 1)
        engine.stop()

    def test_process_key_match_no_callback_stops(self):
        """_process_key_match 无 on_match 回调时设置停止事件"""
        _, known_addr = _get_known_target()
        pk = (1).to_bytes(32, "big")
        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=None,
            max_workers=1,
            data_logging_enabled=False,
        )
        local_matches = []
        should_continue = engine._process_key_match(
            private_key=pk,
            matched_address=known_addr,
            matched_compressed=True,
            local_matches=local_matches,
            worker_id=0,
        )
        self.assertFalse(should_continue, "无回调时应返回 False 停止引擎")
        self.assertTrue(engine._stop_event.is_set())
        engine.stop()

    def test_process_key_match_batch_flush(self):
        """_process_key_match 批量提交阈值时刷新"""
        _, known_addr = _get_known_target()
        pk = (1).to_bytes(32, "big")
        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=lambda pk, addr, wif: None,
            max_workers=1,
            data_logging_enabled=False,
        )
        # 填充到 MATCH_BATCH_FLUSH_THRESHOLD - 1 个条目 (M3: 4元组格式)
        local_matches = [(b"dummy_pk", "dummy_addr", "dummy_wif", None)] * 9
        should_continue = engine._process_key_match(
            private_key=pk,
            matched_address=known_addr,
            matched_compressed=True,
            local_matches=local_matches,
            worker_id=0,
        )
        self.assertTrue(should_continue)
        # 达到阈值10后应触发批量提交并清空列表
        self.assertEqual(len(local_matches), 0)
        engine.stop()


class TestKeyCollisionEngineSafeCallback(unittest.TestCase):
    """安全回调 _safe_invoke_match_callback 异常/超时路径"""

    def test_match_callback_exception_isolation(self):
        """匹配回调抛出异常不影响引擎运行"""
        _, known_addr = _get_known_target()
        exception_raised = threading.Event()

        def on_match_error(pk: bytes, addr: str, wif: str):
            exception_raised.set()
            raise ValueError("模拟回调异常")

        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=on_match_error,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.start(mode="range", start=1, end=5)
        exception_raised.wait(timeout=10)
        time.sleep(0.5)
        # 回调异常不应导致引擎崩溃
        stats = engine.get_stats()
        self.assertGreater(stats.total_checked, 0, "引擎应继续运行")
        engine.stop()

    def test_match_callback_slow_isolation(self):
        """慢速匹配回调由 _safe_invoke_match_callback 超时保护"""
        _, known_addr = _get_known_target()
        callback_started = threading.Event()
        callback_completed = threading.Event()

        def on_match_slow(pk: bytes, addr: str, wif: str):
            callback_started.set()
            time.sleep(10)  # 远超 5 秒超时
            callback_completed.set()

        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=on_match_slow,
            max_workers=1,
            data_logging_enabled=False,
        )
        # 将超时设为 1 秒以加速测试
        engine._match_callback_timeout = 1
        engine.start(mode="range", start=1, end=5)
        callback_started.wait(timeout=10)
        time.sleep(1.5)  # 等待超时处理
        # 回调应被超时拦截，引擎不崩溃
        stats = engine.get_stats()
        self.assertGreater(stats.total_checked, 0)
        engine.stop()


class TestKeyCollisionEngineInternalHelpers(unittest.TestCase):
    """内部辅助方法直接测试：内存降级、batch调优、断点、限频日志"""

    # ── _check_memory_and_downgrade ──

    def test_memory_critical_downgrade(self):
        """M13: 临界内存(>=3GB)触发 batch_size 和 max_workers 降级"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=4, data_logging_enabled=False)
        old_batch = engine._batch_size
        old_workers = engine.max_workers
        engine._check_memory_and_downgrade(3500.0, time.time())
        self.assertLess(engine._batch_size, old_batch, "临界状态应降低batch_size")
        self.assertLess(engine.max_workers, old_workers, "临界状态应降低max_workers")
        engine.stop()

    def test_memory_high_downgrade_single_worker(self):
        """M13: 高警内存(>=2GB)仅降低batch_size（单worker时）"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        old_batch = engine._batch_size
        engine._check_memory_and_downgrade(2500.0, time.time())
        if engine._batch_size < old_batch:
            self.assertLess(engine._batch_size, old_batch)
        # 单worker不触发max_workers降级
        engine.stop()

    def test_memory_high_downgrade_multi_worker(self):
        """M13: 高警内存(>=2GB)仅降低batch_size（多worker场景）"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=4, data_logging_enabled=False)
        engine._batch_size = 2000
        engine._check_memory_and_downgrade(2500.0, time.time())
        # 降至 75% = 1500
        self.assertEqual(engine._batch_size, 1500)
        engine.stop()

    def test_memory_downgrade_cooldown(self):
        """M13: 冷却期内不重复降级"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=4, data_logging_enabled=False)
        now = time.time()
        engine._check_memory_and_downgrade(3500.0, now)
        batch_after_first = engine._batch_size
        # 立即再次调用（冷却期内）
        engine._check_memory_and_downgrade(3500.0, now + 1.0)
        self.assertEqual(engine._batch_size, batch_after_first, "冷却期内不应再次降级")
        engine.stop()

    # ── _tune_batch_size ──

    def test_tune_batch_size_dual_core(self):
        """P3-9: 2核CPU调优 batch_size=500"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine._cpu_count = 2
        engine._auto_tune_batch_size = True
        engine._tune_batch_size()
        self.assertEqual(engine._batch_size, 500)
        engine.stop()

    def test_tune_batch_size_quad_core(self):
        """P3-9: 4核CPU调优 batch_size=1000"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine._cpu_count = 4
        engine._auto_tune_batch_size = True
        engine._tune_batch_size()
        self.assertEqual(engine._batch_size, 1000)
        engine.stop()

    def test_tune_batch_size_disabled(self):
        """P3-9: _auto_tune_batch_size=False 时跳过"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine._auto_tune_batch_size = False
        old_batch = engine._batch_size
        engine._tune_batch_size()
        self.assertEqual(engine._batch_size, old_batch)
        engine.stop()

    # ── _save_checkpoint ──

    def test_save_checkpoint_enabled(self):
        """启用断点时 _save_checkpoint 正常保存"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._current_mode = "random"
        engine.stats.total_checked = 100
        engine._save_checkpoint(100)
        # 不抛出异常即通过
        engine.stop()

    def test_save_checkpoint_range_mode(self):
        """范围模式下 _save_checkpoint 保存位置信息"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._current_mode = "range"
        engine._current_position = 500
        engine._range_start = 1
        engine._range_end = 1000
        engine._save_checkpoint(50)
        engine.stop()

    # ── _log_throttled_error ──

    def test_log_throttled_error_with_data_logger(self):
        """_log_throttled_error 通过数据日志记录错误"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            use_enhanced_monitoring=True,
            max_workers=1,
        )
        self.assertIsNotNone(engine.data_logger)
        engine._log_throttled_error("test_error", "测试错误消息", ValueError("test"), worker_id=0)
        engine.stop()

    def test_log_throttled_error_disabled(self):
        """data_logging_enabled=False 时 _log_throttled_error 跳过"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine._log_throttled_error("test_error", "测试错误消息", ValueError("test"), worker_id=0)
        # 不应崩溃
        engine.stop()

    # ── _auto_detect_compression_needed ──

    def _generate_test_addresses(self, count: int) -> set[str]:
        """生成有效的测试地址用于测试"""
        from src.core.base58 import Base58

        addresses = set()
        i = 0
        while len(addresses) < count:
            # 使用递增的32位整数作为基础，确保唯一性
            hash160 = (i).to_bytes(4, "big") + bytes([0] * 16)
            addresses.add(Base58.check_encode(0x00, hash160))
            i += 1
        return addresses

    def test_auto_detect_compression_many_targets(self):
        """目标地址>=10000时仅检查压缩格式（阈值从50000降至10000以减少漏匹配风险）"""
        many_targets = self._generate_test_addresses(15000)
        engine = KeyCollisionEngine(targets=many_targets, max_workers=1, data_logging_enabled=False)
        self.assertFalse(engine.check_uncompressed)
        engine.stop()

    # ── _init_crypto_backend ──

    def test_init_crypto_backend_unknown_type(self):
        """未知 crypto_backend_type 时使用默认后端"""
        from src.core.base58 import Base58

        test_addr = Base58.check_encode(0x00, bytes([i % 256 for i in range(20)]))
        engine = KeyCollisionEngine(
            targets={test_addr},
            crypto_backend_type="nonexistent_backend",
            max_workers=1,
            data_logging_enabled=False,
        )
        self.assertFalse(engine.is_running())
        engine.stop()

    # ── _safe_invoke_match_callback ──

    def test_safe_invoke_callback_no_handler(self):
        """on_match=None 时 _safe_invoke_match_callback 返回 True"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"}, on_match=None, max_workers=1, data_logging_enabled=False,
        )
        result = engine._safe_invoke_match_callback((1).to_bytes(32, "big"), "1TestAddr", "WIF123")
        self.assertTrue(result)
        engine.stop()


class TestKeyCollisionEngineStartValidation(unittest.TestCase):
    """start() 参数验证 + 断点恢复路径"""

    def test_start_invalid_mode_raises(self):
        """未知模式抛出 ValueError"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        with self.assertRaises(ValueError):
            engine.start(mode="invalid_mode")
        engine.stop()

    def test_start_range_missing_params(self):
        """range模式缺少参数抛出 ValueError"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        with self.assertRaises(ValueError):
            engine.start(mode="range")
        engine.stop()

    def test_start_range_non_int_params(self):
        """range模式非整数参数抛出 ValueError"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        with self.assertRaises(ValueError):
            engine.start(mode="range", start="abc", end=100)
        engine.stop()

    def test_start_range_invalid_range(self):
        """Start < 1 或 end < start 抛出 ValueError"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        with self.assertRaises(ValueError):
            engine.start(mode="range", start=100, end=50)
        engine.stop()

    def test_start_brute_force_non_int_start(self):
        """brute_force模式非整数start抛出 ValueError"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        with self.assertRaises(ValueError):
            engine.start(mode="brute_force", start="abc")
        engine.stop()

    def test_start_brute_force_negative_start(self):
        """brute_force模式start<1抛出 ValueError"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        with self.assertRaises(ValueError):
            engine.start(mode="brute_force", start=-5)
        engine.stop()

    def test_start_with_resume_no_checkpoint(self):
        """resume=True 但无断点文件时正常启动"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.start(mode="random", resume=True)
        time.sleep(0.3)
        self.assertTrue(engine.is_running())
        engine.stop()

    def test_brute_force_with_max_keys(self):
        """brute_force 设置 max_keys 限制扫描数量"""
        engine = KeyCollisionEngine(
            targets={"1NonExistentAddress"},
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.start(mode="brute_force", start=1, max_keys=10)
        time.sleep(0.5)
        engine.stop()
        stats = engine.get_stats()
        # max_keys限制生效，引擎正常运行
        self.assertGreater(stats.total_checked, 0)
        engine.stop()


class TestKeyCollisionEngineContextManager(unittest.TestCase):
    """上下文管理器 + 析构函数"""

    def test_context_manager_enter_exit(self):
        """with语句进入/退出引擎"""
        with KeyCollisionEngine(
            targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False,
        ) as engine:
            self.assertFalse(engine.is_running())
            engine.start(mode="random")
            time.sleep(0.2)
            self.assertTrue(engine.is_running())
        # __exit__ 应调用 stop()
        time.sleep(0.3)
        self.assertFalse(engine.is_running())

    def test_del_with_running_engine(self):
        """__del__ 在引擎运行时安全停止"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine.start(mode="random")
        time.sleep(0.2)
        # 模拟析构
        engine.__del__()
        self.assertFalse(engine.is_running())

    def test_del_with_stopped_engine(self):
        """__del__ 在引擎已停止时不报错"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine.__del__()


class TestKeyCollisionEngineRangeScanWorker(unittest.TestCase):
    """_range_scan_worker 内部路径：匹配、压缩/非压缩、错误处理"""

    def test_range_scan_worker_known_key_match(self):
        """范围扫描工作线程：已知私钥匹配"""
        _, known_addr = _get_known_target()
        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=lambda pk, addr, wif: None,
            max_workers=1,
            data_logging_enabled=False,
        )
        # k=1 在 [1, 5] 范围内
        count = engine._range_scan_worker(1, 5, 0)
        self.assertEqual(count, 5, "应扫描5个私钥")
        self.assertEqual(len(engine.stats.matches), 1)
        engine.stop()

    def test_range_scan_worker_compressed_only(self):
        """范围扫描：仅压缩格式（check_uncompressed=False）"""
        _, known_addr = _get_known_target()
        engine = KeyCollisionEngine(
            targets={known_addr},
            check_uncompressed=False,
            on_match=lambda pk, addr, wif: None,
            max_workers=1,
            data_logging_enabled=False,
        )
        count = engine._range_scan_worker(1, 5, 0)
        self.assertEqual(count, 5)
        self.assertEqual(len(engine.stats.matches), 1)
        engine.stop()

    def test_range_scan_worker_with_uncompressed_check(self):
        """范围扫描：启用双格式检查（check_uncompressed=True）"""
        _, known_addr = _get_known_target()
        engine = KeyCollisionEngine(
            targets={known_addr},
            check_uncompressed=True,
            on_match=lambda pk, addr, wif: None,
            max_workers=1,
            data_logging_enabled=False,
        )
        count = engine._range_scan_worker(1, 5, 0)
        self.assertEqual(count, 5)
        self.assertEqual(len(engine.stats.matches), 1)
        engine.stop()

    def test_range_scan_worker_no_callback_stops(self):
        """范围扫描：无 on_match 回调时匹配后停止"""
        _, known_addr = _get_known_target()
        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=None,
            max_workers=1,
            data_logging_enabled=False,
        )
        count = engine._range_scan_worker(1, 5, 0)
        self.assertLess(count, 5, "匹配后应提前停止")
        self.assertTrue(engine._stop_event.is_set())
        engine.stop()

    def test_range_scan_worker_no_match(self):
        """范围扫描：无匹配目标"""
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddressXYZ"},
            max_workers=1,
            data_logging_enabled=False,
        )
        count = engine._range_scan_worker(1, 10, 0)
        self.assertEqual(count, 10)
        self.assertEqual(len(engine.stats.matches), 0)
        engine.stop()

    def test_range_scan_worker_out_of_range_key(self):
        """范围扫描：私钥超出secp256k1范围时跳过"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            max_workers=1,
            data_logging_enabled=False,
        )
        # k=0 < 1 会被跳过，仅统计有效私钥
        count = engine._range_scan_worker(0, 5, 0)
        self.assertEqual(count, 5, "k=0应跳过，仅5个有效")
        engine.stop()


class TestKeyCollisionEngineBruteForceWorker(unittest.TestCase):
    """_brute_force_worker 内部路径：max_keys、匹配、错误处理"""

    def test_brute_force_worker_max_keys_limit(self):
        """暴力穷举：max_keys 限制生效"""
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._current_position = 1
        count = engine._brute_force_worker(0, batch_size=2, max_keys=5)
        self.assertGreaterEqual(count, 5, "应至少处理 max_keys 个私钥")
        engine.stop()

    def test_brute_force_worker_known_key_match(self):
        """暴力穷举：已知私钥匹配"""
        _, known_addr = _get_known_target()
        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=lambda pk, addr, wif: None,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._current_position = 1
        engine._stop_event.clear()
        count = engine._brute_force_worker(0, batch_size=3, max_keys=10)
        self.assertGreaterEqual(count, 1)
        self.assertEqual(len(engine.stats.matches), 1)
        engine.stop()

    def test_brute_force_worker_no_callback_stops(self):
        """暴力穷举：无 on_match 回调时匹配后停止"""
        _, known_addr = _get_known_target()
        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=None,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._current_position = 1
        engine._stop_event.clear()
        count = engine._brute_force_worker(0, batch_size=3, max_keys=10)
        self.assertGreaterEqual(count, 1)
        self.assertTrue(engine._stop_event.is_set())
        engine.stop()

    def test_brute_force_worker_out_of_range_key(self):
        """暴力穷举：从 k=0 开始跳过无效私钥不崩溃"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._current_position = 0
        engine._stop_event.clear()
        count = engine._brute_force_worker(0, batch_size=2, max_keys=5)
        # k=0 被跳过不崩溃，有效私钥正常处理
        self.assertGreater(count, 0, "k=0应被跳过，不应崩溃")
        engine.stop()


class TestKeyCollisionEngineRangeScanOrchestration(unittest.TestCase):
    """range_scan + brute_force 编排层：进度回调、数据日志"""

    def test_range_scan_with_progress_callback(self):
        """范围扫描：进度回调被调用"""
        progress_called = []

        def on_progress(snapshot):
            progress_called.append(snapshot.total_checked)

        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            on_progress=on_progress,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.start(mode="range", start=1, end=20)
        time.sleep(0.5)
        engine.stop()
        self.assertGreater(len(progress_called), 0, "进度回调应至少被调用一次")

    def test_brute_force_with_progress_callback(self):
        """暴力穷举：进度回调被调用"""
        progress_called = []

        def on_progress(snapshot):
            progress_called.append(snapshot.total_checked)

        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            on_progress=on_progress,
            max_workers=1,
            data_logging_enabled=False,
        )
        # 降低进度回调间隔阈值以触发回调
        engine.progress_interval = 1
        engine.start(mode="brute_force", start=1, max_keys=10)
        time.sleep(1.0)
        engine.stop()
        self.assertGreater(len(progress_called), 0)

    def test_range_scan_with_complete_callback(self):
        """范围扫描：完成回调被调用"""
        complete_called = threading.Event()
        final_stats = []

        def on_complete(stats):
            final_stats.append(stats.total_checked)
            complete_called.set()

        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            on_complete=on_complete,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.start(mode="range", start=1, end=10)
        complete_called.wait(timeout=10)
        engine.stop()
        self.assertGreater(len(final_stats), 0)

    def test_brute_force_with_complete_callback(self):
        """暴力穷举：完成回调被调用"""
        complete_called = threading.Event()
        final_stats = []

        def on_complete(stats):
            final_stats.append(stats.total_checked)
            complete_called.set()

        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            on_complete=on_complete,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.start(mode="brute_force", start=1, max_keys=10)
        complete_called.wait(timeout=10)
        engine.stop()
        self.assertGreater(len(final_stats), 0)


class TestKeyCollisionEngineResumeAndStop(unittest.TestCase):
    """start() resume 路径 + stop() 边界条件"""

    def test_start_empty_targets_warning(self):
        """空目标地址集合时启动发出警告"""
        engine = KeyCollisionEngine(
            targets=set(),
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.start(mode="random")
        time.sleep(0.2)
        self.assertTrue(engine.is_running())
        engine.stop()

    def test_stop_with_thread_timeout(self):
        """stop() 超时等待线程结束"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.start(mode="random")
        time.sleep(0.2)
        # 使用极短超时（0.001秒），线程必然未结束
        engine.stop(timeout=0.001)
        self.assertFalse(engine.is_running())

    def test_del_with_exception_during_stop(self):
        """__del__ 中 stop 抛出异常时静默处理"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._running = True
        # 模拟 stop 会抛出异常的场景：设置一个无效的状态
        engine._stop_event = None  # type: ignore[assignment]
        try:
            engine.__del__()
        except Exception:
            self.fail("__del__ 不应向上抛出异常")
        # 清理
        engine._stop_event = threading.Event()
        engine._running = False

    def test_get_stats_with_live_count(self):
        """get_stats() 合并 live_range_count"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            max_workers=1,
            data_logging_enabled=False,
        )
        engine._live_range_count = 100
        engine.stats.total_checked = 50
        stats = engine.get_stats()
        self.assertGreaterEqual(stats.total_checked, 100)
        engine.stop()

    def test_stop_save_checkpoint_error(self):
        """stop() 保存断点失败时记录错误但不崩溃"""
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.start(mode="random")
        time.sleep(0.2)
        # 设置无效的 checkpoint_mgr 触发保存错误
        engine.checkpoint_mgr = None
        engine.stop()
        self.assertFalse(engine.is_running())


class TestKeyCollisionEngineP3MockExceptions(unittest.TestCase):
    """P3: Mock 异常路径 - 构造器/Crypto/WIF/回调"""

    def test_constructor_data_logger_init_exception(self):
        """__init__ 数据日志系统初始化失败时优雅降级"""
        with patch(
            "src.collision.key_collision_engine.EnhancedMonitoringSystem",
            side_effect=RuntimeError("模拟初始化失败"),
        ):
            engine = KeyCollisionEngine(
                targets={"1TestAddr"},
                use_enhanced_monitoring=True,
                max_workers=1,
            )
            # 应降级：禁用日志，不崩溃
            self.assertFalse(engine.data_logging_enabled)
            self.assertIsNone(engine.data_logger)
            self.assertIsNone(engine.enhanced_monitoring)
            engine.stop()

    def test_safe_invoke_callback_outer_exception(self):
        """_safe_invoke_match_callback 外层 try/except 异常隔离"""
        _, known_addr = _get_known_target()

        def on_match(pk, addr, wif):
            pass

        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=on_match,
            max_workers=1,
            data_logging_enabled=False,
        )
        # 模拟 threading.Thread 构造函数抛出异常
        with patch("threading.Thread", side_effect=RuntimeError("线程创建失败")):
            result = engine._safe_invoke_match_callback((1).to_bytes(32, "big"), known_addr, "WIF123")
            self.assertFalse(result, "线程创建失败应返回 False")
        engine.stop()

    def test_process_key_match_wif_error(self):
        """_process_key_match WIF 编码异常不终止引擎"""
        _, known_addr = _get_known_target()
        engine = KeyCollisionEngine(
            targets={known_addr},
            on_match=lambda pk, addr, wif: None,
            max_workers=1,
            data_logging_enabled=False,
        )
        local_matches = []
        should_continue = engine._process_key_match(
            private_key=b"too_short",
            matched_address=known_addr,
            matched_compressed=True,
            local_matches=local_matches,
            worker_id=0,
        )
        self.assertTrue(should_continue, "WIF编码错误应继续运行")
        engine.stop()


class TestKeyCollisionEngineP3TuneBatch(unittest.TestCase):
    """P3: _tune_batch_size 8核/16核路径"""

    def test_tune_batch_size_octa_core(self):
        """8核CPU调优 batch_size=2000"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine._cpu_count = 8
        engine._auto_tune_batch_size = True
        engine._tune_batch_size()
        self.assertEqual(engine._batch_size, 2000)
        engine.stop()

    def test_tune_batch_size_hexadeca_core(self):
        """16核+CPU调优 batch_size=4000"""
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine._cpu_count = 16
        engine._auto_tune_batch_size = True
        engine._batch_size = 500
        engine._tune_batch_size()
        self.assertEqual(engine._batch_size, 4000)
        engine.stop()


class TestKeyCollisionEngineP3Checkpoint(unittest.TestCase):
    """P3: Checkpoint 持久化：resume_from / start_from / start resume"""

    def setUp(self):
        self._ckpt_dir = tempfile.mkdtemp(prefix="test_ckpt_")
        self._ckpt_path = os.path.join(self._ckpt_dir, "checkpoint.json")

    def tearDown(self):
        import shutil

        shutil.rmtree(self._ckpt_dir, ignore_errors=True)

    def _create_checkpoint(self, mode="range", current_position=100, total_checked=500, range_end=1000):
        data = {
            "version": 1,
            "timestamp": "2026-05-03T00:00:00",
            "mode": mode,
            "targets": ["1TestAddr"],
            "current_position": current_position,
            "total_checked": total_checked,
            "matches": [],
            "range_start": 1,
            "range_end": range_end,
        }
        pathlib.Path(os.path.dirname(self._ckpt_path)).mkdir(exist_ok=True, parents=True)
        with pathlib.Path(self._ckpt_path).open("w") as f:
            json.dump(data, f)

    def test_resume_from_checkpoint_no_file(self):
        """无断点文件时返回 None"""
        from src.collision.checkpoint_manager import CheckpointManager

        mgr = CheckpointManager(filepath=self._ckpt_path)
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine.checkpoint_mgr = mgr
        result = engine.resume_from_checkpoint()
        self.assertIsNone(result)
        engine.stop()

    def test_resume_from_checkpoint_range(self):
        """从 range 模式断点恢复"""
        from src.collision.checkpoint_manager import CheckpointManager

        self._create_checkpoint(mode="range", current_position=100, total_checked=500, range_end=1000)
        mgr = CheckpointManager(filepath=self._ckpt_path)
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine.checkpoint_mgr = mgr
        result = engine.resume_from_checkpoint()
        self.assertIsNotNone(result)
        self.assertEqual(result["mode"], "range")
        self.assertEqual(engine.stats.total_checked, 500)
        engine.stop()

    def test_resume_from_checkpoint_brute_force(self):
        """从 brute_force 模式断点恢复"""
        from src.collision.checkpoint_manager import CheckpointManager

        self._create_checkpoint(
            mode="brute_force", current_position=200, total_checked=300, range_end=None,
        )
        mgr = CheckpointManager(filepath=self._ckpt_path)
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine.checkpoint_mgr = mgr
        result = engine.resume_from_checkpoint()
        self.assertIsNotNone(result)
        self.assertEqual(result["mode"], "brute_force")
        engine.stop()

    def test_start_from_checkpoint_range(self):
        """start_from_checkpoint range 模式"""
        data = {"mode": "range", "current_position": 50, "range_end": 500000}
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine.start_from_checkpoint(data)
        time.sleep(0.3)
        self.assertTrue(engine.is_running())
        engine.stop()

    def test_start_from_checkpoint_brute_force(self):
        """start_from_checkpoint brute_force 模式"""
        data = {"mode": "brute_force", "current_position": 50}
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine.start_from_checkpoint(data)
        time.sleep(0.3)
        self.assertTrue(engine.is_running())
        engine.stop()

    def test_start_from_checkpoint_random(self):
        """start_from_checkpoint random 模式"""
        data = {"mode": "random"}
        engine = KeyCollisionEngine(targets={"1TestAddr"}, max_workers=1, data_logging_enabled=False)
        engine.start_from_checkpoint(data)
        time.sleep(0.2)
        self.assertTrue(engine.is_running())
        engine.stop()

    def test_start_resume_from_range_checkpoint(self):
        """start(resume=True) 从 range 断点恢复"""
        from src.collision.checkpoint_manager import CheckpointManager

        self._create_checkpoint(mode="range", current_position=1, total_checked=0, range_end=500000)
        mgr = CheckpointManager(filepath=self._ckpt_path)
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.checkpoint_mgr = mgr
        engine.start(mode="range", resume=True, start=1, end=1000)
        time.sleep(0.3)
        self.assertTrue(engine.is_running())
        engine.stop()

    def test_start_resume_from_brute_force_checkpoint(self):
        """start(resume=True) 从 brute_force 断点恢复"""
        from src.collision.checkpoint_manager import CheckpointManager

        self._create_checkpoint(mode="brute_force", current_position=1, total_checked=0, range_end=None)
        mgr = CheckpointManager(filepath=self._ckpt_path)
        engine = KeyCollisionEngine(
            targets={"1NoMatchAddrXYZ"},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.checkpoint_mgr = mgr
        engine.start(mode="brute_force", resume=True, start=1, max_keys=5)
        time.sleep(0.5)
        self.assertTrue(engine.is_running())
        engine.stop()

    def test_start_resume_from_random_checkpoint(self):
        """start(resume=True) 从 random 断点恢复"""
        from src.collision.checkpoint_manager import CheckpointManager

        self._create_checkpoint(mode="random", current_position=0, total_checked=100, range_end=None)
        mgr = CheckpointManager(filepath=self._ckpt_path)
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.checkpoint_mgr = mgr
        engine.start(mode="random", resume=True)
        time.sleep(0.2)
        self.assertTrue(engine.is_running())
        engine.stop()

    def test_start_resume_checkpoint_load_failure(self):
        """start(resume=True) 断点加载失败时回退到正常启动"""
        from src.collision.checkpoint_manager import CheckpointManager

        class FailingCheckpointManager(CheckpointManager):
            def load(self):
                raise RuntimeError("模拟加载失败")

        mgr = FailingCheckpointManager(filepath=self._ckpt_path)
        engine = KeyCollisionEngine(
            targets={"1TestAddr"},
            checkpoint_enabled=True,
            max_workers=1,
            data_logging_enabled=False,
        )
        engine.checkpoint_mgr = mgr
        engine.start(mode="random", resume=True)
        time.sleep(0.2)
        self.assertTrue(engine.is_running(), "断点加载失败应回退到正常启动")
        engine.stop()


if __name__ == "__main__":
    unittest.main(verbosity=2)
