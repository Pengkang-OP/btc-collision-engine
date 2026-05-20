"""SIMD哈希优化模块单元测试"""

import time

import pytest

from src.core.simd_hash import SIMDHashOptimizer, get_simd_hash_optimizer, simd_hash_optimizer


class TestSIMDHashOptimizer:
    """SIMD哈希优化器测试类"""

    def test_initialization(self):
        """测试初始化"""
        optimizer = SIMDHashOptimizer()
        assert hasattr(optimizer, "use_pycryptodome")
        assert isinstance(optimizer.use_pycryptodome, bool)

    def test_batch_sha256_correctness(self):
        """测试批量SHA256正确性"""
        optimizer = SIMDHashOptimizer()
        import hashlib

        data_list = [b"hello", b"world", b"test", b"data"]

        # 使用优化器
        results_opt = optimizer.batch_sha256(data_list)

        # 使用hashlib验证
        results_ref = [hashlib.sha256(data).digest() for data in data_list]

        assert len(results_opt) == len(results_ref)
        for opt, ref in zip(results_opt, results_ref, strict=False):
            assert opt == ref

    def test_batch_ripemd160_correctness(self):
        """测试批量RIPEMD160正确性"""
        optimizer = SIMDHashOptimizer()
        import hashlib

        data_list = [b"test1", b"test2", b"test3"]

        results_opt = optimizer.batch_ripemd160(data_list)
        results_ref = [hashlib.new("ripemd160", data).digest() for data in data_list]

        assert len(results_opt) == len(results_ref)
        for opt, ref in zip(results_opt, results_ref, strict=False):
            assert opt == ref

    def test_batch_hash160_correctness(self):
        """测试批量Hash160正确性"""
        optimizer = SIMDHashOptimizer()
        import hashlib

        # 测试数据(模拟公钥)
        data_list = [b"public_key_1" * 5, b"public_key_2" * 5]

        results_opt = optimizer.batch_hash160(data_list)

        # 验证每个结果都是20字节
        for result in results_opt:
            assert len(result) == 20

        # 验证正确性
        for i, data in enumerate(data_list):
            expected = hashlib.new("ripemd160", hashlib.sha256(data).digest()).digest()
            assert results_opt[i] == expected

    def test_batch_sha256_performance(self):
        """测试批量SHA256性能"""
        optimizer = SIMDHashOptimizer()

        if not optimizer.use_pycryptodome:
            pytest.skip("pycryptodome未安装,跳过性能测试")

        # 准备测试数据
        data_list = [f"data{i}".encode() * 100 for i in range(10000)]

        # 使用pycryptodome
        start = time.perf_counter()
        _ = optimizer.batch_sha256(data_list)
        elapsed_crypto = time.perf_counter() - start

        # 使用hashlib
        import hashlib

        start = time.perf_counter()
        _ = [hashlib.sha256(data).digest() for data in data_list]
        elapsed_hashlib = time.perf_counter() - start

        speedup = elapsed_hashlib / elapsed_crypto
        print(f"\nSHA256批量性能提升: {speedup:.2f}x")
        print(f"  pycryptodome: {elapsed_crypto:.4f}s")
        print(f"  hashlib: {elapsed_hashlib:.4f}s")
        print(f"  后端: {optimizer.get_backend_name()}")

    def test_empty_input(self):
        """测试空输入"""
        optimizer = SIMDHashOptimizer()

        assert optimizer.batch_sha256([]) == []
        assert optimizer.batch_ripemd160([]) == []
        assert optimizer.batch_hash160([]) == []

    def test_is_optimized(self):
        """测试优化状态检测"""
        optimizer = SIMDHashOptimizer()
        assert isinstance(optimizer.is_optimized(), bool)

    def test_get_backend_name(self):
        """测试后端名称获取"""
        optimizer = SIMDHashOptimizer()
        name = optimizer.get_backend_name()
        assert isinstance(name, str)
        assert len(name) > 0

        if optimizer.use_pycryptodome:
            assert "pycryptodome" in name.lower()
        else:
            assert "hashlib" in name.lower()


class TestGlobalSIMDHashOptimizer:
    """全局SIMD哈希优化器测试类"""

    def test_singleton_pattern(self):
        """测试单例模式"""
        optimizer1 = get_simd_hash_optimizer()
        optimizer2 = simd_hash_optimizer
        assert optimizer1 is optimizer2

    def test_global_optimizer_functional(self):
        """测试全局优化器功能"""
        optimizer = get_simd_hash_optimizer()

        # 应该能正常执行
        results = optimizer.batch_sha256([b"test"])
        assert len(results) == 1
        assert len(results[0]) == 32  # SHA256输出32字节
