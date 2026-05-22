"""KeyCollisionEngine 构造函数和参数验证测试 (MAINT-1拆分)

原 file: test_key_collision_engine.py
抽取类: TestKeyCollisionEngineConstructorBranches, TestKeyCollisionEngineStartValidation
"""

import threading
import time
import unittest

from src.collision.key_collision_engine import KeyCollisionEngine
from tests.conftest_engine import get_known_target


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

    def test_constructor_data_logger_init_exception(self):
        """__init__ 数据日志系统初始化失败时优雅降级"""
        from unittest.mock import patch

        with patch(
            "src.collision.key_collision_engine.EnhancedMonitoringSystem",
            side_effect=RuntimeError("模拟初始化失败"),
        ):
            engine = KeyCollisionEngine(
                targets={"1TestAddr"},
                use_enhanced_monitoring=True,
                max_workers=1,
            )
            self.assertFalse(engine.data_logging_enabled)
            self.assertIsNone(engine.data_logger)
            self.assertIsNone(engine.enhanced_monitoring)
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
        """start < 1 或 end < start 抛出 ValueError"""
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
