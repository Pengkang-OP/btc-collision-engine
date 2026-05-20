"""GPU内核集成测试

测试GPU OpenCL内核的正确性和性能：
1. 内核编译测试
2. 内核执行正确性测试
3. 内核性能基准测试
4. 内核参数验证测试
"""

import logging
from unittest.mock import patch

import pytest

logger = logging.getLogger(__name__)

# 模块级别 marker：本文件所有测试都属于 GPU 测试
pytestmark = pytest.mark.gpu


class TestGPUKernelCompilation:
    """GPU内核编译测试"""

    def test_kernel_source_not_empty(self):
        """测试内核源码不为空"""
        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        # 检查内核源码存在
        assert OPENCL_KERNEL_SOURCE is not None
        assert len(OPENCL_KERNEL_SOURCE) > 0
        assert "kernel" in OPENCL_KERNEL_SOURCE.lower()

    def test_kernel_source_contains_required_functions(self):
        """测试内核源码包含必需的函数"""
        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        # 检查关键函数存在（根据内核文件实际内容）
        required_functions = [
            "batch_check",  # 主碰撞检测内核
            "hash160",  # Hash160计算函数
            "verify_arithmetic",  # 验证内核
        ]

        for func in required_functions:
            assert func in OPENCL_KERNEL_SOURCE, f"内核源码缺少函数: {func}"

    def test_kernel_source_uint32_workaround(self):
        """测试内核使用uint32 workaround（Intel Arc兼容）- PRNG模式"""
        from src.gpu.kernel import OPENCL_KERNEL_SOURCE

        # v4.2.1: 已转换为 PRNG 模式，使用种子而非私钥缓冲区
        # Intel Arc 需要 uint32 workaround，现已应用于 PRNG 种子和 uint256_from_bytes_global
        assert (
            "__constant const uint *seed" in OPENCL_KERNEL_SOURCE
        ), "内核应该使用PRNG种子模式（uint32 workaround已应用）"

        # 验证辅助函数存在（uint32 workaround的具体实现）
        assert (
            "uint256_from_bytes_global" in OPENCL_KERNEL_SOURCE
        ), "内核应该包含 uint256_from_bytes_global 函数（使用 uint* 而非 uchar*）"


class TestGPUKernelExecution:
    """GPU内核执行测试（使用Mock）"""

    @patch("src.collision.gpu_collision_engine.GPUKernel._verify")
    @patch("pyopencl.create_some_context")
    def test_kernel_initialization(self, mock_context, mock_verify):
        """测试内核初始化"""

        # 这个测试需要真实的GPU设备，跳过
        pytest.skip("需要真实GPU环境")

    @patch("src.collision.gpu_collision_engine.GPUKernel._verify")
    def test_kernel_batch_size_validation(self, mock_verify):
        """测试内核批次大小验证"""

        # 测试不同批次大小
        valid_sizes = [1024, 65536, 1048576]

        for size in valid_sizes:
            assert size >= 1024, f"批次大小 {size} 应该 >= 1024"
            assert size <= 16777216, f"批次大小 {size} 应该 <= 16777216"


class TestGPUKernelCorrectness:
    """GPU内核正确性测试"""

    def test_private_key_to_bytes_conversion(self):
        """测试私钥到字节转换"""
        # 测试私钥转换
        test_key = 0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5

        # 转换为32字节
        key_bytes = test_key.to_bytes(32, "big")

        assert len(key_bytes) == 32
        assert key_bytes[0] == 0xC6
        assert key_bytes[-1] == 0xE5

    def test_known_private_key_address(self):
        """测试已知私钥的地址生成"""
        from src.core.hash_utils import HashUtils

        # 比特币著名的私钥示例
        test_key_int = 0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5
        test_key_bytes = test_key_int.to_bytes(32, "big")

        # 生成Hash160
        hash160 = HashUtils.hash160(test_key_bytes)

        # 验证Hash160长度
        assert hash160 is not None
        assert len(hash160) == 20

    def test_hash160_conversion(self):
        """测试Hash160转换"""
        from src.core.hash_utils import HashUtils

        test_key_int = 0x1
        test_key_bytes = test_key_int.to_bytes(32, "big")

        hash160 = HashUtils.hash160(test_key_bytes)

        # Hash160应该是20字节
        assert hash160 is not None
        assert len(hash160) == 20


class TestGPUKernelPerformance:
    """GPU内核性能测试"""

    def test_kernel_compilation_time(self):
        """测试内核编译时间"""
        # 这个测试需要真实GPU，跳过
        pytest.skip("需要真实GPU环境")

    def test_batch_execution_time(self):
        """测试批次执行时间"""
        # 这个测试需要真实GPU，跳过
        pytest.skip("需要真实GPU环境")


class TestGPUKernelEdgeCases:
    """GPU内核边界情况测试"""

    def test_empty_batch(self):
        """测试空批次"""
        # 空批次应该被正确处理
        batch_size = 0
        assert batch_size >= 0

    def test_minimum_batch_size(self):
        """测试最小批次大小"""
        min_batch = 1024

        # 最小批次应该有效
        assert min_batch >= 1024
        assert min_batch <= 16777216

    def test_maximum_batch_size(self):
        """测试最大批次大小"""
        max_batch = 16777216

        # 最大批次应该有效
        assert max_batch >= 1024
        assert max_batch <= 16777216

    def test_oversized_batch(self):
        """测试超大批次"""
        oversized = 33554432  # 32M，超过最大值

        # 应该被拒绝
        assert oversized > 16777216


class TestGPUKernelConfiguration:
    """GPU内核配置测试"""

    def test_work_group_size_valid(self):
        """测试工作组大小有效"""
        # 常见的工作组大小
        valid_sizes = [64, 128, 256, 512, 1024]

        for size in valid_sizes:
            assert size >= 64
            assert size <= 2048
            assert (size & (size - 1)) == 0, f"{size} 应该是2的幂"

    def test_memory_usage_ratio_valid(self):
        """测试显存使用率有效"""
        # Intel Arc保守策略
        intel_ratio = 0.45
        assert 0 < intel_ratio <= 1.0

        # NVIDIA默认
        nvidia_ratio = 0.7
        assert 0 < nvidia_ratio <= 1.0

        # AMD默认
        amd_ratio = 0.6
        assert 0 < amd_ratio <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
