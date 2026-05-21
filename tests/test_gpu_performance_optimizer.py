#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU自适应性能优化器测试
"""

import sys
import os
import time
import unittest
from unittest.mock import Mock, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gpu.performance_optimizer import (
    GPUPerformanceOptimizer,
    PerformanceMetrics,
    GPUProfile,
    GPUVendor,
    get_gpu_optimizer,
)


class TestGPUPerformanceOptimizer(unittest.TestCase):
    """测试GPU性能优化器"""

    def setUp(self):
        """设置测试环境"""
        self.optimizer = GPUPerformanceOptimizer()

    def test_vendor_detection(self):
        """测试GPU厂商检测"""
        # NVIDIA
        self.assertEqual(
            self.optimizer.detect_vendor("NVIDIA GeForce RTX 3080", "NVIDIA Corporation"),
            GPUVendor.NVIDIA,
        )
        self.assertEqual(self.optimizer.detect_vendor("RTX 4090", ""), GPUVendor.NVIDIA)

        # AMD
        self.assertEqual(
            self.optimizer.detect_vendor("AMD Radeon RX 6800 XT", "Advanced Micro Devices"),
            GPUVendor.AMD,
        )

        # Intel
        self.assertEqual(
            self.optimizer.detect_vendor("Intel Arc A770", "Intel Corporation"), GPUVendor.INTEL
        )

        # Unknown
        self.assertEqual(self.optimizer.detect_vendor("Unknown GPU", "Unknown"), GPUVendor.UNKNOWN)

    def test_create_optimized_profile_nvidia(self):
        """测试NVIDIA GPU配置优化"""
        profile = self.optimizer.create_optimized_profile(
            device_name="NVIDIA GeForce RTX 3080",
            vendor_str="NVIDIA Corporation",
            global_mem_size=10 * 1024**3,  # 10GB
            compile_time_ms=15000,
        )

        self.assertEqual(profile.vendor, GPUVendor.NVIDIA)
        self.assertTrue(profile.max_batch_size >= 1048576)  # 至少1M
        self.assertTrue(profile.memory_usage_ratio >= 0.7)
        self.assertFalse(profile.use_uint32_workaround)  # NVIDIA不需要
        self.assertTrue(profile.enable_async_execution)

    def test_create_optimized_profile_intel(self):
        """测试Intel GPU配置优化"""
        profile = self.optimizer.create_optimized_profile(
            device_name="Intel Arc A770",
            vendor_str="Intel Corporation",
            global_mem_size=16 * 1024**3,  # 16GB
            compile_time_ms=22000,
        )

        self.assertEqual(profile.vendor, GPUVendor.INTEL)
        self.assertTrue(profile.use_uint32_workaround)  # Intel需要workaround
        self.assertTrue(profile.enable_async_execution)  # P3修复: Intel Arc必须开启异步执行
        self.assertEqual(profile.preferred_mode, "range_scan")

    def test_create_optimized_profile_amd(self):
        """测试AMD GPU配置优化"""
        profile = self.optimizer.create_optimized_profile(
            device_name="AMD Radeon RX 6800 XT",
            vendor_str="Advanced Micro Devices",
            global_mem_size=16 * 1024**3,  # 16GB
            compile_time_ms=18000,
        )

        self.assertEqual(profile.vendor, GPUVendor.AMD)
        self.assertTrue(profile.max_batch_size >= 524288)  # 至少512K
        self.assertTrue(profile.memory_usage_ratio >= 0.6)

    def test_record_performance(self):
        """测试性能指标记录"""
        metrics = PerformanceMetrics(
            kernel_compile_time_ms=15000,
            batch_execution_time_ms=50,
            keys_per_second=100000,
            memory_usage_mb=4096,
            error_count=0,
        )

        self.optimizer.record_performance(metrics)

        # 验证记录已保存
        self.assertEqual(len(self.optimizer._metrics_history), 1)
        self.assertEqual(self.optimizer._metrics_history[0].keys_per_second, 100000)

    def test_analyze_and_adjust_error_rate_too_high(self):
        """测试错误率过高时的调整"""
        # 先记录一些性能数据
        for i in range(10):
            self.optimizer.record_performance(
                PerformanceMetrics(
                    batch_execution_time_ms=50, keys_per_second=100000, error_count=1
                )
            )

        # 创建配置文件
        self.optimizer.create_optimized_profile(
            device_name="Test GPU", vendor_str="Test", global_mem_size=8 * 1024**3
        )

        # 测试高错误率调整
        new_batch_size, adjustments = self.optimizer.analyze_and_adjust(
            current_batch_size=100000, error_rate=0.05  # 5%错误率
        )

        # 应该减小batch_size
        self.assertLess(new_batch_size, 100000)
        self.assertIn("error_rate_too_high", adjustments)

    def test_analyze_and_adjust_execution_too_slow(self):
        """测试执行时间过长时的调整"""
        # 记录慢速性能数据
        for i in range(10):
            self.optimizer.record_performance(
                PerformanceMetrics(
                    batch_execution_time_ms=2000,  # 2秒，超过阈值
                    keys_per_second=5000,
                    error_count=0,
                )
            )

        # 创建配置文件
        self.optimizer.create_optimized_profile(
            device_name="Test GPU", vendor_str="Test", global_mem_size=8 * 1024**3
        )

        # 测试慢速调整
        new_batch_size, adjustments = self.optimizer.analyze_and_adjust(
            current_batch_size=100000, error_rate=0.0
        )

        # 应该减小batch_size
        self.assertLess(new_batch_size, 100000)
        self.assertIn("execution_too_slow", adjustments)

    def test_analyze_and_adjust_performance_good(self):
        """测试性能良好时的调整"""
        # 记录快速性能数据
        for i in range(10):
            self.optimizer.record_performance(
                PerformanceMetrics(
                    batch_execution_time_ms=10, keys_per_second=500000, error_count=0  # 10ms，很快
                )
            )

        # 创建配置文件
        self.optimizer.create_optimized_profile(
            device_name="Test GPU", vendor_str="Test", global_mem_size=8 * 1024**3
        )

        # 测试性能良好调整
        new_batch_size, adjustments = self.optimizer.analyze_and_adjust(
            current_batch_size=100000, error_rate=0.0
        )

        # 应该增大batch_size
        self.assertGreater(new_batch_size, 100000)
        self.assertIn("performance_good", adjustments)

    def test_get_optimization_report(self):
        """测试优化报告生成"""
        # 创建配置并记录数据
        self.optimizer.create_optimized_profile(
            device_name="NVIDIA RTX 3080", vendor_str="NVIDIA", global_mem_size=10 * 1024**3
        )

        for i in range(5):
            self.optimizer.record_performance(
                PerformanceMetrics(
                    batch_execution_time_ms=50, keys_per_second=100000, error_count=0
                )
            )

        report = self.optimizer.get_optimization_report()

        self.assertEqual(report["status"], "active")
        self.assertIn("profile", report)
        self.assertIn("performance", report)
        self.assertIn("recommendations", report)
        self.assertEqual(report["profile"]["vendor"], "nvidia")

    def test_singleton_pattern(self):
        """测试单例模式"""
        optimizer1 = get_gpu_optimizer()
        optimizer2 = get_gpu_optimizer()

        # 应该是同一个实例
        self.assertIs(optimizer1, optimizer2)

    def test_reset(self):
        """测试重置功能"""
        # 添加一些数据
        self.optimizer.record_performance(PerformanceMetrics())
        self.optimizer.create_optimized_profile("Test", "Test", 8 * 1024**3)

        # 重置
        self.optimizer.reset()

        # 验证数据已清空
        self.assertEqual(len(self.optimizer._metrics_history), 0)
        self.assertIsNone(self.optimizer._current_profile)
        self.assertEqual(self.optimizer._adjustment_count, 0)

    def test_memory_based_batch_adjustment(self):
        """测试基于显存的batch_size调整"""
        # 小显存（1GB）
        profile_small = self.optimizer.create_optimized_profile(
            device_name="Test GPU", vendor_str="Test", global_mem_size=1 * 1024**3
        )

        # 大显存（16GB）
        profile_large = self.optimizer.create_optimized_profile(
            device_name="Test GPU", vendor_str="Test", global_mem_size=16 * 1024**3
        )

        # 大显存应该允许更大的batch_size
        self.assertGreater(profile_large.max_batch_size, profile_small.max_batch_size)

    def test_compile_time_based_adjustment(self):
        """测试基于编译时间的调整"""
        # 快速编译
        profile_fast = self.optimizer.create_optimized_profile(
            device_name="Test GPU",
            vendor_str="Test",
            global_mem_size=8 * 1024**3,
            compile_time_ms=5000,
        )

        # 慢速编译
        profile_slow = self.optimizer.create_optimized_profile(
            device_name="Test GPU",
            vendor_str="Test",
            global_mem_size=8 * 1024**3,
            compile_time_ms=25000,
        )

        # 慢编译应该使用更小的batch_size
        self.assertGreater(profile_fast.max_batch_size, profile_slow.max_batch_size)


if __name__ == "__main__":
    unittest.main()
