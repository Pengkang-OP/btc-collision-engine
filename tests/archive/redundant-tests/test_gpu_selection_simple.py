#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU设备选择和切换功能全面测试 (简化版)
专注于核心功能: 厂商识别、设备评分、选择算法
"""

import sys
import os
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# 修复Windows编码
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.gpu.selector import GPUDeviceSelector, get_gpu_selector, reset_gpu_selector
from src.gpu.device import identify_vendor


class TestGPUVendorIdentification(unittest.TestCase):
    """测试1: GPU厂商识别功能"""

    def test_01_identify_nvidia(self):
        """测试1.1: 识别NVIDIA GPU"""
        print("\n📋 测试1.1: 识别NVIDIA GPU")

        test_cases = [
            ("NVIDIA GeForce RTX 3080", "NVIDIA Corporation"),
            ("GeForce GTX 1660 Ti", "NVIDIA"),
            ("RTX 4090", "NVIDIA Corporation"),
        ]

        for name, vendor in test_cases:
            result = identify_vendor(name, vendor)
            self.assertEqual(result, "nvidia")
            print(f"  ✅ {name} -> {result}")

    def test_02_identify_amd(self):
        """测试1.2: 识别AMD GPU"""
        print("\n📋 测试1.2: 识别AMD GPU")

        test_cases = [
            ("AMD Radeon RX 6800 XT", "Advanced Micro Devices, Inc."),
            ("Radeon RX 5700 XT", "AMD"),
        ]

        for name, vendor in test_cases:
            result = identify_vendor(name, vendor)
            self.assertEqual(result, "amd")
            print(f"  ✅ {name} -> {result}")

    def test_03_identify_intel(self):
        """测试1.3: 识别Intel GPU"""
        print("\n📋 测试1.3: 识别Intel GPU")

        test_cases = [
            ("Intel(R) Arc(TM) A770 Graphics", "Intel Corporation"),
            ("Intel Arc A750", "Intel"),
        ]

        for name, vendor in test_cases:
            result = identify_vendor(name, vendor)
            self.assertEqual(result, "intel")
            print(f"  ✅ {name} -> {result}")


class TestGPUDeviceScoring(unittest.TestCase):
    """测试2: GPU评分和选择算法"""

    def setUp(self):
        """测试前准备"""
        reset_gpu_selector()
        self.selector = GPUDeviceSelector()

    def test_01_score_calculation(self):
        """测试2.1: GPU评分计算"""
        print("\n📋 测试2.1: GPU评分计算")

        devices = [
            {
                "name": "NVIDIA GeForce RTX 3080",
                "vendor": "nvidia",
                "global_mem_gb": 10.0,
                "max_compute_units": 68,
                "global_index": 0,
            },
            {
                "name": "AMD Radeon RX 6800 XT",
                "vendor": "amd",
                "global_mem_gb": 16.0,
                "max_compute_units": 72,
                "global_index": 1,
            },
            {
                "name": "Intel Arc A770",
                "vendor": "intel",
                "global_mem_gb": 16.0,
                "max_compute_units": 512,
                "global_index": 2,
            },
        ]

        print("  设备评分结果:")
        for device in devices:
            score = self.selector.score_device(device)
            device["score"] = score

            # 验证评分公式: (memory*10 + CU*0.05) * vendor_factor
            vendor_factor = self.selector.VENDOR_FACTORS.get(device["vendor"], 0.8)
            expected = (
                device["global_mem_gb"] * 10.0 + device["max_compute_units"] * 0.05
            ) * vendor_factor

            self.assertAlmostEqual(score, expected, places=1)
            print(f"    {device['name']}: {score:.1f}分 (厂商系数: {vendor_factor})")

    def test_02_select_best_device(self):
        """测试2.2: 自动选择最佳GPU"""
        print("\n📋 测试2.2: 自动选择最佳GPU")

        devices = [
            {
                "name": "NVIDIA RTX 3080",
                "vendor": "nvidia",
                "global_mem_gb": 10.0,
                "max_compute_units": 68,
                "global_index": 0,
            },
            {
                "name": "AMD RX 6800 XT",
                "vendor": "amd",
                "global_mem_gb": 16.0,
                "max_compute_units": 72,
                "global_index": 1,
            },
            {
                "name": "Intel Arc A770",
                "vendor": "intel",
                "global_mem_gb": 16.0,
                "max_compute_units": 512,
                "global_index": 2,
            },
        ]

        # 计算评分
        for device in devices:
            device["score"] = self.selector.score_device(device)

        # 选择最佳
        best = self.selector.select_best_device(devices)

        self.assertIsNotNone(best)
        # Intel Arc A770应该分数最高(大量计算单元)
        self.assertIn("Arc A770", best["name"])

        print(f"  ✅ 最佳GPU: {best['name']} ({best['score']:.1f}分)")
        print(f"  所有设备排名:")
        for dev in sorted(devices, key=lambda d: d["score"], reverse=True):
            print(f"    {dev['name']}: {dev['score']:.1f}分")

    def test_03_recommend_batch_size(self):
        """测试2.3: 推荐批次大小"""
        print("\n📋 测试2.3: 推荐批次大小")

        test_cases = [
            ("NVIDIA RTX 4090", 24.0, "nvidia"),
            ("AMD RX 7900 XTX", 24.0, "amd"),
            ("Intel Arc A770", 16.0, "intel"),
            ("NVIDIA GTX 1660", 6.0, "nvidia"),
        ]

        for name, mem_gb, vendor in test_cases:
            device = {"global_mem_gb": mem_gb, "vendor": vendor}
            batch_size = self.selector.recommend_batch_size(device)

            print(f"  ✅ {name} ({mem_gb}GB, {vendor}): {batch_size:,}")

            # 验证批次大小合理
            self.assertGreater(batch_size, 0)
            self.assertLessEqual(batch_size, 131072)  # 最大128K


class TestGPUSelectorAPI(unittest.TestCase):
    """测试3: GPU选择器API功能"""

    def setUp(self):
        """测试前准备"""
        reset_gpu_selector()

    def test_01_singleton_pattern(self):
        """测试3.1: 选择器单例模式"""
        print("\n📋 测试3.1: 选择器单例模式")

        selector1 = get_gpu_selector()
        selector2 = get_gpu_selector()

        self.assertIs(selector1, selector2)
        print(f"  ✅ 单例模式正常: selector1 is selector2 = {selector1 is selector2}")

    def test_02_format_device_info(self):
        """测试3.2: 格式化设备信息"""
        print("\n📋 测试3.2: 格式化设备信息")

        device = {
            "global_index": 0,
            "name": "NVIDIA GeForce RTX 3080",
            "vendor": "nvidia",
            "global_mem_gb": 10.0,
            "max_compute_units": 68,
            "score": 103.4,
            "max_work_group_size": 1024,
            "global_mem_cache_kb": 5120,
            "local_mem_kb": 64,
            "recommended_batch_size": 131072,
            "recommended_work_group": 512,
        }

        selector = GPUDeviceSelector()

        # 简洁格式
        brief = selector.format_device_info(device, detailed=False)
        self.assertIn("RTX 3080", brief)
        self.assertIn("10.00 GB", brief)
        print(f"  ✅ 简洁格式生成成功")

        # 详细格式
        detailed = selector.format_device_info(device, detailed=True)
        self.assertIn("131,072", detailed)
        print(f"  ✅ 详细格式生成成功")

    def test_03_select_by_index(self):
        """测试3.3: 根据索引选择设备"""
        print("\n📋 测试3.3: 根据索引选择设备")

        devices = [
            {
                "global_index": 0,
                "name": "GPU 0",
                "vendor": "nvidia",
                "global_mem_gb": 10.0,
                "max_compute_units": 68,
            },
            {
                "global_index": 1,
                "name": "GPU 1",
                "vendor": "amd",
                "global_mem_gb": 16.0,
                "max_compute_units": 72,
            },
        ]

        selector = GPUDeviceSelector()

        with patch.object(selector, "detect_all_devices", return_value=devices):
            # 选择索引0
            device0 = selector.get_device_info(0)
            self.assertIsNotNone(device0)
            self.assertEqual(device0["global_index"], 0)

            # 选择不存在的索引
            device_invalid = selector.get_device_info(99)
            self.assertIsNone(device_invalid)

            print(f"  ✅ 索引选择功能正常")


def run_tests():
    """运行所有测试"""
    print("=" * 80)
    print("  GPU设备选择和切换功能测试")
    print("=" * 80)
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试类
    test_classes = [
        TestGPUVendorIdentification,
        TestGPUDeviceScoring,
        TestGPUSelectorAPI,
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出总结
    print("\n" + "=" * 80)
    print("  测试总结")
    print("=" * 80)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f"  总测试数: {result.testsRun}")
    print(f"  ✅ 通过: {passed}")
    print(f"  ❌ 失败: {len(result.failures)}")
    print(f"  💥 错误: {len(result.errors)}")

    pass_rate = (passed / result.testsRun * 100) if result.testsRun > 0 else 0
    print(f"  通过率: {pass_rate:.1f}%")

    return len(result.failures) == 0 and len(result.errors) == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
