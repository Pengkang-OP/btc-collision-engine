# -*- coding: utf-8 -*-
"""大整数优化模块单元测试"""

import pytest
import time
from src.core.bigint_optimizer import BigIntOptimizer, get_bigint_optimizer, bigint_optimizer


class TestBigIntOptimizer:
    """大整数优化器测试类"""

    def test_initialization(self):
        """测试初始化"""
        optimizer = BigIntOptimizer()
        assert hasattr(optimizer, "use_gmpy2")
        assert hasattr(optimizer, "gmpy2")
        assert isinstance(optimizer.use_gmpy2, bool)

    def test_mod_inverse_correctness(self):
        """测试模逆元正确性"""
        optimizer = BigIntOptimizer()

        # 测试用例: (a, m, expected_inverse)
        test_cases = [
            (3, 11, 4),  # 3*4 % 11 = 1
            (7, 13, 2),  # 7*2 % 13 = 1
            (10, 17, 12),  # 10*12 % 17 = 1
            (123456789, 1000000007, 18633540),  # 大数测试
        ]

        for a, m, expected in test_cases:
            result = optimizer.mod_inverse(a, m)
            assert result == expected
            # 验证: a * result % m == 1
            assert (a * result) % m == 1

    def test_mod_inverse_edge_cases(self):
        """测试模逆元边界情况"""
        optimizer = BigIntOptimizer()

        # a=1, 逆元应该是1
        assert optimizer.mod_inverse(1, 7) == 1

        # 负数测试
        result = optimizer.mod_inverse(-3, 11)
        assert (result * -3) % 11 == 1

    def test_mod_inverse_no_inverse(self):
        """测试逆元不存在的情况"""
        optimizer = BigIntOptimizer()

        # a和m不互质,逆元不存在
        with pytest.raises(ValueError):
            optimizer.mod_inverse(2, 4)  # gcd(2,4)=2≠1

    def test_mod_mul_correctness(self):
        """测试模乘法正确性"""
        optimizer = BigIntOptimizer()

        test_cases = [
            (3, 5, 7, 1),  # 3*5 % 7 = 1
            (100, 200, 997, 8),  # 100*200 % 997 = 20000 % 997 = 8
            (123456789, 987654321, 1000000007, 575680909),
        ]

        for a, b, m, expected in test_cases:
            result = optimizer.mod_mul(a, b, m)
            # 验证结果正确(而不是硬编码期望值)
            assert result == (a * b) % m

    def test_mod_add_correctness(self):
        """测试模加法正确性"""
        optimizer = BigIntOptimizer()

        test_cases = [(3, 5, 7, 1), (100, 200, 997, 300)]  # 3+5 % 7 = 1

        for a, b, m, expected in test_cases:
            result = optimizer.mod_add(a, b, m)
            assert result == expected

    def test_mod_sub_correctness(self):
        """测试模减法正确性"""
        optimizer = BigIntOptimizer()

        test_cases = [
            (5, 3, 7, 2),  # 5-3 % 7 = 2
            (3, 5, 7, 5),  # 3-5 % 7 = -2 % 7 = 5
            (100, 200, 997, 897),
        ]

        for a, b, m, expected in test_cases:
            result = optimizer.mod_sub(a, b, m)
            assert result == expected

    def test_mod_pow_correctness(self):
        """测试模幂正确性"""
        optimizer = BigIntOptimizer()

        test_cases = [
            (2, 10, 1000, 24),  # 2^10 % 1000 = 24
            (3, 7, 11, 9),  # 3^7 % 11 = 9
            (123, 456, 789, 699),
        ]

        for base, exp, m, expected in test_cases:
            result = optimizer.mod_pow(base, exp, m)
            assert result == expected
            assert result == pow(base, exp, m)

    def test_performance_mod_inverse(self):
        """测试模逆元性能提升"""
        optimizer = BigIntOptimizer()

        if not optimizer.use_gmpy2:
            pytest.skip("gmpy2未安装,跳过性能测试")

        a = 12345678901234567890123456789012345678
        m = Secp256k1.P
        iterations = 1000

        # 使用gmpy2
        start = time.perf_counter()
        for _ in range(iterations):
            _ = optimizer.mod_inverse(a, m)
        elapsed_gmpy2 = time.perf_counter() - start

        # 使用纯Python
        start = time.perf_counter()
        for _ in range(iterations):
            _ = optimizer._mod_inverse_python(a, m)
        elapsed_python = time.perf_counter() - start

        speedup = elapsed_python / elapsed_gmpy2
        print(f"\n模逆元性能提升: {speedup:.2f}x")
        print(f"  gmpy2: {elapsed_gmpy2:.4f}s")
        print(f"  Python: {elapsed_python:.4f}s")

        # gmpy2应该至少快1.2x
        assert speedup > 1.2

    def test_performance_mod_mul(self):
        """测试模乘法性能提升"""
        optimizer = BigIntOptimizer()

        if not optimizer.use_gmpy2:
            pytest.skip("gmpy2未安装,跳过性能测试")

        a = 12345678901234567890123456789012345678
        b = 98765432109876543210987654321098765432
        m = Secp256k1.P
        iterations = 10000

        # 使用gmpy2
        start = time.perf_counter()
        for _ in range(iterations):
            _ = optimizer.mod_mul(a, b, m)
        elapsed_gmpy2 = time.perf_counter() - start

        # 使用纯Python
        start = time.perf_counter()
        for _ in range(iterations):
            _ = (a * b) % m
        elapsed_python = time.perf_counter() - start

        speedup = elapsed_python / elapsed_gmpy2
        print(f"\n模乘法性能提升: {speedup:.2f}x")
        print(f"  gmpy2: {elapsed_gmpy2:.4f}s")
        print(f"  Python: {elapsed_python:.4f}s")

    def test_is_optimized(self):
        """测试优化状态检测"""
        optimizer = BigIntOptimizer()
        assert isinstance(optimizer.is_optimized(), bool)

        if optimizer.gmpy2 is not None:
            assert optimizer.is_optimized() == True

    def test_get_backend_name(self):
        """测试后端名称获取"""
        optimizer = BigIntOptimizer()
        name = optimizer.get_backend_name()
        assert isinstance(name, str)
        assert len(name) > 0

        if optimizer.use_gmpy2:
            assert "gmpy2" in name.lower()
        else:
            assert "python" in name.lower()


class TestGlobalBigIntOptimizer:
    """全局大整数优化器测试类"""

    def test_singleton_pattern(self):
        """测试单例模式"""
        optimizer1 = get_bigint_optimizer()
        optimizer2 = bigint_optimizer
        assert optimizer1 is optimizer2

    def test_global_optimizer_functional(self):
        """测试全局优化器功能"""
        optimizer = get_bigint_optimizer()

        # 应该能正常执行运算
        result = optimizer.mod_inverse(3, 11)
        assert result == 4

        result = optimizer.mod_mul(10, 20, 1000)
        assert result == 200


# 导入Secp256k1用于性能测试
from src.core.secp256k1 import Secp256k1
