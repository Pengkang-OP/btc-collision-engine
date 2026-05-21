"""PerformanceOptimizationConfig 单元测试

覆盖 src/config/performance_config.py 中未直接测试的路径：
- __post_init__ 边界值修正
- optimize_for_gpu/memory/speed 方法
- recommend_config 未知场景异常
"""

import unittest

from src.config.performance_config import (
    PerformanceOptimizationConfig,
    PerformanceTuner,
)


class TestPerformanceOptimizationConfig(unittest.TestCase):
    """PerformanceOptimizationConfig __post_init__ 边界与优化方法测试"""

    # ── __post_init__ 边界值修正 ──────────────────────────────

    def test_post_init_clamps_simd_batch_size(self):
        """simd_batch_size < 1000 时自动修正为 1000"""
        cfg = PerformanceOptimizationConfig(simd_batch_size=500)
        self.assertEqual(cfg.simd_batch_size, 1000)

    def test_post_init_clamps_process_batch_size(self):
        """process_batch_size < 1000 时自动修正为 1000"""
        cfg = PerformanceOptimizationConfig(process_batch_size=500)
        self.assertEqual(cfg.process_batch_size, 1000)

    def test_post_init_clamps_bloom_rate_zero(self):
        """bloom_false_positive_rate <= 0 时回退为 0.001"""
        cfg = PerformanceOptimizationConfig(bloom_false_positive_rate=0.0)
        self.assertEqual(cfg.bloom_false_positive_rate, 0.001)

    def test_post_init_clamps_bloom_rate_one(self):
        """bloom_false_positive_rate >= 1 时回退为 0.001"""
        cfg = PerformanceOptimizationConfig(bloom_false_positive_rate=1.0)
        self.assertEqual(cfg.bloom_false_positive_rate, 0.001)

    def test_post_init_valid_bloom_rate(self):
        """bloom_false_positive_rate 在 (0,1) 范围内保持原值"""
        cfg = PerformanceOptimizationConfig(bloom_false_positive_rate=0.01)
        self.assertEqual(cfg.bloom_false_positive_rate, 0.01)

    # ── optimize_for_* 方法 ───────────────────────────────────

    def test_optimize_for_gpu(self):
        """optimize_for_gpu() 设置 GPU 相关参数"""
        cfg = PerformanceOptimizationConfig()
        result = cfg.optimize_for_gpu(device_index=2)
        self.assertIs(result, cfg)  # 链式调用返回 self
        self.assertTrue(cfg.use_gpu)
        self.assertEqual(cfg.gpu_device_index, 2)
        self.assertEqual(cfg.gpu_batch_size, 2000000)
        self.assertFalse(cfg.use_multiprocess)

    def test_optimize_for_memory(self):
        """optimize_for_memory() 降低内存使用"""
        cfg = PerformanceOptimizationConfig()
        result = cfg.optimize_for_memory(max_memory_mb=1024)
        self.assertIs(result, cfg)
        self.assertEqual(cfg.max_memory_mb, 1024)
        self.assertEqual(cfg.simd_batch_size, 50000)
        self.assertEqual(cfg.process_batch_size, 5000)
        self.assertEqual(cfg.bloom_max_size, 1_000_000)
        self.assertEqual(cfg.cache_max_size, 10000)

    def test_optimize_for_speed(self):
        """optimize_for_speed() 针对速度优化"""
        cfg = PerformanceOptimizationConfig()
        result = cfg.optimize_for_speed(num_cores=4)
        self.assertIs(result, cfg)
        self.assertTrue(cfg.use_multiprocess)
        self.assertEqual(cfg.num_workers, 4)
        self.assertEqual(cfg.process_batch_size, 100000)
        self.assertEqual(cfg.bloom_max_size, 100_000_000)

    def test_optimize_for_cpu(self):
        """optimize_for_cpu() 针对 CPU 优化"""
        cfg = PerformanceOptimizationConfig()
        result = cfg.optimize_for_cpu(num_cores=8)
        self.assertIs(result, cfg)
        self.assertTrue(cfg.use_multiprocess)
        self.assertEqual(cfg.num_workers, 8)
        self.assertTrue(cfg.enable_simd)

    # ── recommend_config ─────────────────────────────────────

    def test_recommend_config_balanced(self):
        """recommend_config("balanced") 返回平衡配置"""
        cfg = PerformanceTuner.recommend_config("balanced")
        self.assertIsInstance(cfg, PerformanceOptimizationConfig)
        self.assertTrue(cfg.enable_bloom_filter)

    def test_recommend_config_speed(self):
        """recommend_config("speed") 返回速度优先配置"""
        cfg = PerformanceTuner.recommend_config("speed")
        self.assertIsInstance(cfg, PerformanceOptimizationConfig)

    def test_recommend_config_memory(self):
        """recommend_config("memory") 返回内存优先配置"""
        cfg = PerformanceTuner.recommend_config("memory")
        self.assertIsInstance(cfg, PerformanceOptimizationConfig)

    def test_recommend_config_gpu(self):
        """recommend_config("gpu") 返回 GPU 配置"""
        cfg = PerformanceTuner.recommend_config("gpu")
        self.assertIsInstance(cfg, PerformanceOptimizationConfig)
        self.assertTrue(cfg.use_gpu)

    def test_recommend_config_unknown_scenario(self):
        """recommend_config("unknown") 抛出 ValueError"""
        with self.assertRaises(ValueError):
            PerformanceTuner.recommend_config("unknown")

    # ── to_dict / from_dict ──────────────────────────────────

    def test_to_dict(self):
        """to_dict() 返回字典表示"""
        cfg = PerformanceOptimizationConfig(use_gpu=True, num_workers=8)
        d = cfg.to_dict()
        self.assertEqual(d["use_gpu"], True)
        self.assertEqual(d["num_workers"], 8)
        self.assertIn("enable_simd", d)

    def test_from_dict(self):
        """from_dict() 从字典创建配置"""
        cfg = PerformanceOptimizationConfig.from_dict(
            {
                "use_gpu": True,
                "num_workers": 4,
                "enable_simd": False,
            }
        )
        self.assertTrue(cfg.use_gpu)
        self.assertEqual(cfg.num_workers, 4)
        self.assertFalse(cfg.enable_simd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
