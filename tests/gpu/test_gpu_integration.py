#!/usr/bin/env python3
"""GPU 引擎集成测试 - 验证 P0/P1/P2 所有功能集成
"""

import unittest
import pytest


@pytest.mark.skip(reason="Integration checks for removed components (timeout_manager)")
class TestGPUIntegration(unittest.TestCase):
    """GPU 引擎集成测试 - 验证模块导入和方法存在"""

    def test_01_import_modules(self):
        """测试所有 P1/P2 模块可以导入"""
        # P2 模块
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor
        from src.gpu.intel_timeout_manager import AdaptiveTimeoutManager

        # 验证导入成功
        self.assertIsNotNone(AdaptiveTimeoutManager)
        self.assertIsNotNone(IntelMemoryMonitor)

    def test_02_gpu_engine_has_p1_p2_attributes(self):
        """测试 GPU 引擎类有 P1/P2 属性"""
        from src.collision.gpu.engine import GPUCollisionEngine

        # 检查类有这些属性（虽然实例可能是 None）
        self.assertTrue(hasattr(GPUCollisionEngine, "__init__"))

        # 检查源代码中有这些属性初始化
        import inspect

        source = inspect.getsource(GPUCollisionEngine.__init__)

        self.assertIn("timeout_manager", source)
        self.assertIn("memory_monitor", source)
        self.assertIn("benchmark_suite", source)
        self.assertIn("auto_tuner", source)
        self.assertIn("performance_reporter", source)

    def test_03_gpu_engine_has_p2_methods(self):
        """测试 GPU 引擎有 P2 便捷方法"""
        from src.collision.gpu.engine import GPUCollisionEngine

        # 验证方法存在
        self.assertTrue(hasattr(GPUCollisionEngine, "run_benchmark"))
        self.assertTrue(hasattr(GPUCollisionEngine, "start_auto_tuning"))
        self.assertTrue(hasattr(GPUCollisionEngine, "generate_performance_report"))

        # 验证可调用
        self.assertTrue(callable(GPUCollisionEngine.run_benchmark))
        self.assertTrue(callable(GPUCollisionEngine.start_auto_tuning))
        self.assertTrue(callable(GPUCollisionEngine.generate_performance_report))

    def test_04_timeout_manager_creation(self):
        """测试可以创建超时管理器"""
        from src.gpu.intel_timeout_manager import AdaptiveTimeoutManager

        manager = AdaptiveTimeoutManager(base_timeout=30.0, history_size=50, safety_factor=3.0)

        self.assertIsNotNone(manager)
        self.assertEqual(manager.base_timeout, 30.0)

    def test_05_memory_monitor_creation(self):
        """测试可以创建显存监控器"""
        from src.gpu.intel_memory_monitor import IntelMemoryMonitor

        monitor = IntelMemoryMonitor(total_memory_bytes=8 * 1024**3, safe_usage_ratio=0.45)

        self.assertIsNotNone(monitor)
        self.assertEqual(monitor.total_memory, 8 * 1024**3)

    def test_06_import_integration_in_engine(self):
        """测试 GPU 引擎中导入了 P1/P2 模块"""
        import inspect

        from src.collision.gpu import engine as gpu_collision_engine

        source = inspect.getsource(gpu_collision_engine)

        # 验证导入语句
        self.assertIn("from ..gpu.intel_timeout_manager import AdaptiveTimeoutManager", source)
        self.assertIn("from ..gpu.intel_memory_monitor import IntelMemoryMonitor", source)
        self.assertIn("from ..gpu.benchmark_suite import GPUBenchmarkSuite", source)
        self.assertIn("from ..gpu.auto_tuner import GPUAutoTuner", source)
        self.assertIn("from ..gpu.performance_reporter import PerformanceReportGenerator", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
