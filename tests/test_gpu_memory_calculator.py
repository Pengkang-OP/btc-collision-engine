# -*- coding: utf-8 -*-
"""
GPU 显存计算器单元测试

测试 GPUMemoryCalculator 类的所有静态方法，覆盖：
- calculate_batch_memory() 正常路径、零值、极大值
- calculate_batch_memory_mb() 单位换算
- estimate_max_batch_size() 边界条件和正常路径
- get_memory_breakdown() 明细字段完整性
- calculate_from_hash160_bytes() 字节串输入场景
"""

import sys
import os
import unittest
import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.gpu.memory_calculator import GPUMemoryCalculator


@pytest.mark.unit
@pytest.mark.gpu
class TestCalculateBatchMemory(unittest.TestCase):
    """测试 calculate_batch_memory() 方法"""

    def test_normal_input_returns_positive_integer(self):
        """正常输入应返回正整数字节数"""
        result = GPUMemoryCalculator.calculate_batch_memory(100_000, 320)
        self.assertIsInstance(result, int)
        self.assertGreater(result, 0)

    def test_zero_batch_size_returns_targets_bytes_only(self):
        """batch_size=0 时结果应仅包含目标地址缓冲区字节数"""
        num_targets = 100
        result = GPUMemoryCalculator.calculate_batch_memory(0, num_targets)
        expected = num_targets * GPUMemoryCalculator.HASH160_SIZE
        self.assertEqual(result, expected)

    def test_zero_targets_no_target_overhead(self):
        """num_targets=0 时结果不含目标地址缓冲区"""
        batch_size = 100_000
        result = GPUMemoryCalculator.calculate_batch_memory(batch_size, 0)
        # 仅有私钥缓冲区 + 匹配标志缓冲区 + 20% overhead，无目标地址
        key_bytes = batch_size * GPUMemoryCalculator.PRIVATE_KEY_SIZE
        flag_bytes = batch_size * GPUMemoryCalculator.MATCH_FLAG_SIZE
        overhead = int((key_bytes + flag_bytes) * GPUMemoryCalculator.KERNEL_OVERHEAD_RATIO)
        expected = key_bytes + flag_bytes + overhead
        self.assertEqual(result, expected)

    def test_both_zero_returns_zero(self):
        """两个参数均为零时应返回 0"""
        result = GPUMemoryCalculator.calculate_batch_memory(0, 0)
        self.assertEqual(result, 0)

    def test_large_batch_size(self):
        """极大 batch_size（1000 万）应能正常计算不溢出"""
        result = GPUMemoryCalculator.calculate_batch_memory(10_000_000, 100)
        self.assertGreater(result, 0)
        # 大致估算: 10M * (32+4) * 1.2 ≈ 432,000,000 字节
        expected_approx = 10_000_000 * 36 * 1.2
        self.assertAlmostEqual(result, expected_approx, delta=1_000_000)

    def test_typical_gpu_run_size(self):
        """验证典型 GPU 运行规模(100万 keys, 320 targets)的计算值合理"""
        result = GPUMemoryCalculator.calculate_batch_memory(1_000_000, 320)
        # 100万 * 32 = 32,000,000 字节 keys; 100万 * 4 = 4,000,000 字节 flags
        # 320*20=6400 字节 targets; overhead = 36,000,000 * 0.2 = 7,200,000 字节
        # 总计约 43,206,400 字节 ÷ 1024² ≈ 41.2 MiB
        result_mb = result / GPUMemoryCalculator.BYTES_PER_MB
        self.assertAlmostEqual(result_mb, 41.2, delta=1.0)

    def test_memory_formula_components(self):
        """验证各内存分量公式正确"""
        batch_size = 1000
        num_targets = 50
        result = GPUMemoryCalculator.calculate_batch_memory(batch_size, num_targets)

        pk_bytes = batch_size * 32      # PRIVATE_KEY_SIZE
        mf_bytes = batch_size * 4       # MATCH_FLAG_SIZE
        tg_bytes = num_targets * 20     # HASH160_SIZE
        oh_bytes = int((pk_bytes + mf_bytes) * 0.20)  # KERNEL_OVERHEAD_RATIO
        expected = pk_bytes + mf_bytes + tg_bytes + oh_bytes

        self.assertEqual(result, expected)


@pytest.mark.unit
@pytest.mark.gpu
class TestCalculateBatchMemoryMb(unittest.TestCase):
    """测试 calculate_batch_memory_mb() 方法"""

    def test_returns_float(self):
        """应返回浮点数"""
        result = GPUMemoryCalculator.calculate_batch_memory_mb(100_000, 100)
        self.assertIsInstance(result, float)

    def test_zero_inputs_returns_zero(self):
        """两个参数均为零时应返回 0.0"""
        result = GPUMemoryCalculator.calculate_batch_memory_mb(0, 0)
        self.assertEqual(result, 0.0)

    def test_consistent_with_byte_method(self):
        """MB 结果应与字节结果一致（相差 BYTES_PER_MB 倍）"""
        batch_size = 200_000
        num_targets = 500
        byte_result = GPUMemoryCalculator.calculate_batch_memory(batch_size, num_targets)
        mb_result = GPUMemoryCalculator.calculate_batch_memory_mb(batch_size, num_targets)
        self.assertAlmostEqual(mb_result, byte_result / (1024 * 1024), places=10)

    def test_one_mb_boundary(self):
        """验证接近 1MB 的结果精度"""
        # 约 1MB 的计算场景
        result = GPUMemoryCalculator.calculate_batch_memory_mb(0, 1024 * 1024 // 20)
        # targets_bytes = (1024*1024//20) * 20 = 1MB
        self.assertAlmostEqual(result, 1.0, delta=0.01)


@pytest.mark.unit
@pytest.mark.gpu
class TestEstimateMaxBatchSize(unittest.TestCase):
    """测试 estimate_max_batch_size() 方法"""

    def test_normal_returns_multiple_of_10000(self):
        """正常可用显存场景应返回 10000 的整数倍"""
        available = 8 * 1024 ** 3  # 8GB
        result = GPUMemoryCalculator.estimate_max_batch_size(available, 320)
        self.assertGreater(result, 0)
        self.assertEqual(result % 10_000, 0)

    def test_minimum_value_is_10000(self):
        """最小返回值应为 10000"""
        # 极小可用显存
        available = 1024  # 1KB
        result = GPUMemoryCalculator.estimate_max_batch_size(available, 0)
        self.assertGreaterEqual(result, 10_000)

    def test_insufficient_memory_for_targets_returns_minimum(self):
        """可用显存不足以容纳目标地址时应返回最小安全值 10000"""
        # 目标地址 100万个，每个 20 字节 = 20MB；可用显存仅 1MB
        available = 1 * 1024 * 1024  # 1MB
        num_targets = 1_000_000
        result = GPUMemoryCalculator.estimate_max_batch_size(available, num_targets)
        self.assertEqual(result, 10_000)

    def test_default_memory_ratio_0_7(self):
        """默认显存比例为 0.7，验证估算基于 70% 可用显存"""
        available = 1 * 1024 ** 3  # 1GB
        # 使用默认 ratio=0.7
        result_default = GPUMemoryCalculator.estimate_max_batch_size(available, 0)
        # 显式传入 ratio=0.7
        result_explicit = GPUMemoryCalculator.estimate_max_batch_size(available, 0, memory_ratio=0.7)
        self.assertEqual(result_default, result_explicit)

    def test_higher_memory_ratio_gives_larger_batch(self):
        """更高的显存比例应给出更大的 batch_size"""
        available = 4 * 1024 ** 3  # 4GB
        result_70 = GPUMemoryCalculator.estimate_max_batch_size(available, 100, memory_ratio=0.7)
        result_90 = GPUMemoryCalculator.estimate_max_batch_size(available, 100, memory_ratio=0.9)
        self.assertGreater(result_90, result_70)

    def test_more_targets_reduces_batch_size(self):
        """更多目标地址消耗更多显存，应导致更小的 batch_size"""
        available = 2 * 1024 ** 3  # 2GB
        result_small = GPUMemoryCalculator.estimate_max_batch_size(available, 100)
        result_large = GPUMemoryCalculator.estimate_max_batch_size(available, 1_000_000)
        self.assertGreaterEqual(result_small, result_large)

    def test_result_is_integer(self):
        """应返回整数类型"""
        result = GPUMemoryCalculator.estimate_max_batch_size(4 * 1024 ** 3, 320)
        self.assertIsInstance(result, int)

    def test_zero_targets_uses_full_remaining_memory(self):
        """无目标地址时可用于 keys 的内存更多，结果应更大"""
        available = 2 * 1024 ** 3
        result_zero = GPUMemoryCalculator.estimate_max_batch_size(available, 0)
        result_many = GPUMemoryCalculator.estimate_max_batch_size(available, 100_000)
        self.assertGreaterEqual(result_zero, result_many)


@pytest.mark.unit
@pytest.mark.gpu
class TestGetMemoryBreakdown(unittest.TestCase):
    """测试 get_memory_breakdown() 方法"""

    def test_returns_dict_with_required_keys(self):
        """应返回包含所有必需键的字典"""
        result = GPUMemoryCalculator.get_memory_breakdown(100_000, 100)
        required_keys = {
            'private_keys_mb',
            'match_flags_mb',
            'targets_mb',
            'overhead_mb',
            'total_mb',
        }
        self.assertEqual(set(result.keys()), required_keys)

    def test_all_values_are_float(self):
        """所有值应为浮点数"""
        result = GPUMemoryCalculator.get_memory_breakdown(100_000, 100)
        for key, val in result.items():
            self.assertIsInstance(val, float, f"{key} should be float, got {type(val)}")

    def test_total_equals_sum_of_components(self):
        """total_mb 应等于各分量之和"""
        result = GPUMemoryCalculator.get_memory_breakdown(500_000, 500)
        expected_total = (
            result['private_keys_mb'] +
            result['match_flags_mb'] +
            result['targets_mb'] +
            result['overhead_mb']
        )
        self.assertAlmostEqual(result['total_mb'], expected_total, places=10)

    def test_zero_inputs_all_zero(self):
        """两个参数均为零时所有值应为 0.0"""
        result = GPUMemoryCalculator.get_memory_breakdown(0, 0)
        for key, val in result.items():
            self.assertEqual(val, 0.0, f"{key} should be 0.0")

    def test_consistent_with_mb_method(self):
        """total_mb 应与 calculate_batch_memory_mb() 结果一致"""
        batch_size = 1_000_000
        num_targets = 320
        breakdown = GPUMemoryCalculator.get_memory_breakdown(batch_size, num_targets)
        mb_method = GPUMemoryCalculator.calculate_batch_memory_mb(batch_size, num_targets)
        self.assertAlmostEqual(breakdown['total_mb'], mb_method, places=10)

    def test_overhead_is_20_percent_of_keys_and_flags(self):
        """overhead_mb 应为 (private_keys + match_flags) * 20%"""
        result = GPUMemoryCalculator.get_memory_breakdown(200_000, 200)
        expected_overhead = (result['private_keys_mb'] + result['match_flags_mb']) * 0.20
        self.assertAlmostEqual(result['overhead_mb'], expected_overhead, places=6)


@pytest.mark.unit
@pytest.mark.gpu
class TestCalculateFromHash160Bytes(unittest.TestCase):
    """测试 calculate_from_hash160_bytes() 方法"""

    def test_normal_bytes_returns_float(self):
        """正常字节串输入应返回浮点数"""
        hash160_bytes = b'\x00' * (100 * 20)  # 100 个目标，每个 20 字节
        result = GPUMemoryCalculator.calculate_from_hash160_bytes(100_000, hash160_bytes)
        self.assertIsInstance(result, float)
        self.assertGreater(result, 0.0)

    def test_none_hash160_bytes_treats_as_zero_targets(self):
        """hash160_bytes=None 时目标缓冲区大小应计为 0"""
        result_none = GPUMemoryCalculator.calculate_from_hash160_bytes(100_000, None)
        result_zero = GPUMemoryCalculator.calculate_from_hash160_bytes(100_000, b'')
        self.assertAlmostEqual(result_none, result_zero, places=10)

    def test_empty_bytes_equals_no_targets(self):
        """空字节串的结果应等于无目标地址场景"""
        result_empty = GPUMemoryCalculator.calculate_from_hash160_bytes(50_000, b'')
        # 手动计算预期值
        bpMB = GPUMemoryCalculator.BYTES_PER_MB
        pk_mb = (50_000 * 32) / bpMB
        mf_mb = (50_000 * 4) / bpMB
        oh_mb = (pk_mb + mf_mb) * 0.20
        expected = pk_mb + mf_mb + oh_mb
        self.assertAlmostEqual(result_empty, expected, places=10)

    def test_larger_bytes_gives_larger_result(self):
        """更大的 hash160_bytes 应给出更大的内存估算"""
        small_bytes = b'\x00' * 200   # 200 字节
        large_bytes = b'\x00' * 2000  # 2000 字节
        result_small = GPUMemoryCalculator.calculate_from_hash160_bytes(100_000, small_bytes)
        result_large = GPUMemoryCalculator.calculate_from_hash160_bytes(100_000, large_bytes)
        self.assertGreater(result_large, result_small)

    def test_zero_keys_with_bytes(self):
        """num_keys=0 时仅有目标地址内存占用"""
        hash160_bytes = b'\xff' * 200
        result = GPUMemoryCalculator.calculate_from_hash160_bytes(0, hash160_bytes)
        expected = len(hash160_bytes) / GPUMemoryCalculator.BYTES_PER_MB
        self.assertAlmostEqual(result, expected, places=10)


if __name__ == '__main__':
    unittest.main()
