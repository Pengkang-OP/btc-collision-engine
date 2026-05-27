"""预计算点表优化模块单元测试."""

import time

import pytest

from src.core.precomputed_table import (
    PrecomputedPointTable,
    PrecomputedTableManager,
    get_precomputed_table,
    precomputed_table_manager,
)
from src.core.secp256k1 import ECPoint, Secp256k1


class TestPrecomputedPointTable:
    """预计算点表测试类."""

    def test_initialization_default(self):
        """测试默认初始化(window_size=8)."""
        table = PrecomputedPointTable(window_size=8)
        assert table.window_size == 8
        assert table.num_points == 256  # 2^8
        assert len(table.table) == 256

    def test_initialization_custom_window(self):
        """测试自定义窗口大小."""
        for w in [4, 5, 6, 7, 8]:
            table = PrecomputedPointTable(window_size=w)
            assert table.window_size == w
            assert table.num_points == (1 << w)
            assert len(table.table) == (1 << w)

    def test_invalid_window_size(self):
        """测试无效窗口大小."""
        with pytest.raises(ValueError):
            PrecomputedPointTable(window_size=3)

        with pytest.raises(ValueError):
            PrecomputedPointTable(window_size=9)

    def test_table_content_validity(self):
        """测试预计算表内容正确性."""
        table = PrecomputedPointTable(window_size=4)
        ec = table.ec

        # 验证table[0] = G
        G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        assert table.table[0].x == G.x
        assert table.table[0].y == G.y

        # 验证table[1] = 2G
        two_g = ec.point_add(G, G)
        assert table.table[1].x == two_g.x
        assert table.table[1].y == two_g.y

        # 验证table[2] = 3G = 2G + G
        three_g = ec.point_add(two_g, G)
        assert table.table[2].x == three_g.x
        assert table.table[2].y == three_g.y

    def test_scalar_multiply_correctness(self):
        """测试标量乘法正确性."""
        table = PrecomputedPointTable(window_size=6)
        ec = table.ec

        # 测试已知值
        test_cases = [1, 2, 100, 1000, 123456789, Secp256k1.N - 1]  # 最大有效私钥

        for k in test_cases:
            # 使用预计算表
            result_table = table.scalar_multiply_with_table(k)

            # 使用标准方法（恒定时间版本）
            G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
            result_standard = ec.scalar_multiply_const_time(k, G)

            # 结果应该相同
            assert result_table.x == result_standard.x
            assert result_table.y == result_standard.y

    def test_scalar_multiply_edge_cases(self):
        """测试标量乘法边界情况."""
        table = PrecomputedPointTable(window_size=4)

        # k=0 应该返回无穷远点
        result = table.scalar_multiply_with_table(0)
        assert result.is_infinity

        # k=N 应该返回无穷远点
        result = table.scalar_multiply_with_table(Secp256k1.N)
        assert result.is_infinity

        # k>N 应该取模
        result1 = table.scalar_multiply_with_table(Secp256k1.N + 1)
        result2 = table.scalar_multiply_with_table(1)
        assert result1.x == result2.x
        assert result1.y == result2.y

    def test_performance_improvement(self):
        """测试性能提升(预计算表 vs 标准方法)."""
        table = PrecomputedPointTable(window_size=8)
        ec = table.ec
        G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

        k = 12345678901234567890123456789012345678
        iterations = 100

        # 测试预计算表方法
        start = time.perf_counter()
        for _ in range(iterations):
            _ = table.scalar_multiply_with_table(k)
        elapsed_table = time.perf_counter() - start

        # 测试恒定时间方法（替代已禁用的非恒定时间 scalar_multiply）
        start = time.perf_counter()
        for _ in range(iterations):
            _ = ec.scalar_multiply_const_time(k, G)
        elapsed_standard = time.perf_counter() - start

        # 预计算表应该更快
        speedup = elapsed_standard / elapsed_table
        print(f"\n预计算表性能提升: {speedup:.2f}x")
        print(f"  预计算表: {elapsed_table:.4f}s")
        print(f"  标准方法: {elapsed_standard:.4f}s")

        # 至少应该有1.2x的提升(保守估计)
        assert speedup > 1.2

    def test_memory_usage(self):
        """测试内存占用."""
        for w in [4, 6, 8]:
            table = PrecomputedPointTable(window_size=w)
            memory_bytes = table.get_memory_usage()
            memory_kb = memory_bytes / 1024

            print(f"\nwindow_size={w}: 预计内存={memory_kb:.1f}KB")

            # w=8时应该<=50KB
            if w == 8:
                assert memory_kb <= 50

    def test_speedup_estimate(self):
        """测试加速比估算."""
        for w in [4, 6, 8]:
            table = PrecomputedPointTable(window_size=w)
            speedup = table.get_speedup_estimate()

            print(f"\nwindow_size={w}: 估算加速比={speedup:.2f}x")

            # 窗口越大,加速比应该越高
            if w > 4:
                prev_table = PrecomputedPointTable(window_size=w - 1)
                prev_speedup = prev_table.get_speedup_estimate()
                assert speedup > prev_speedup

    def test_init_with_custom_ec_has_G(self):
        """使用自定义 ec (有 curve.G) 初始化 (cover lines 88-90)."""
        from src.core.secp256k1 import EllipticCurve

        ec = EllipticCurve()
        # 临时给 ec.curve 动态添加 G 属性触发 hasattr 分支
        # 注意: 测试完必须清理, 避免污染其他测试
        saved_G = getattr(ec.curve, "G", None)
        ec.curve.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        try:
            table = PrecomputedPointTable(window_size=4, ec=ec)
            assert table.ec is ec
            assert len(table.table) > 0
        finally:
            if saved_G is None:
                del ec.curve.G
            else:
                ec.curve.G = saved_G

    def test_init_with_custom_ec_no_G(self):
        """使用自定义 ec (无 curve.G) 初始化 (cover lines 91-94)."""
        from src.core.secp256k1 import EllipticCurve

        ec = EllipticCurve()
        # 确保没有 test pollution
        saved_G = getattr(ec.curve, "G", None)
        if hasattr(ec.curve, "G"):
            del ec.curve.G
        try:
            table = PrecomputedPointTable(window_size=4, ec=ec)
            assert table.ec is ec
            assert len(table.table) > 0
        finally:
            if saved_G is not None:
                ec.curve.G = saved_G

    def test_scalar_multiply_with_custom_ec(self):
        """标量乘法传入自定义 ec (cover scalar_multiply_with_table ec 非 None 分支)."""
        table = PrecomputedPointTable(window_size=6)
        # 使用独立的 EllipticCurve 实例
        from src.core.secp256k1 import EllipticCurve

        custom_ec = EllipticCurve()
        G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

        result_table = table.scalar_multiply_with_table(100, ec=custom_ec)
        result_std = custom_ec.scalar_multiply_const_time(100, G)
        assert result_table.x == result_std.x
        assert result_table.y == result_std.y


class TestPrecomputedTableManager:
    """预计算表管理器测试类."""

    def test_singleton_pattern(self):
        """测试单例模式."""
        manager1 = PrecomputedTableManager()
        manager2 = PrecomputedTableManager()
        assert manager1 is manager2

    def test_get_table_caching(self):
        """测试表缓存."""
        manager = PrecomputedTableManager()
        manager.clear_cache()

        # 第一次获取应该创建新表
        table1 = manager.get_table(window_size=6)

        # 第二次获取应该返回缓存的表
        table2 = manager.get_table(window_size=6)

        assert table1 is table2

    def test_different_window_sizes(self):
        """测试不同窗口大小."""
        manager = PrecomputedTableManager()
        manager.clear_cache()

        table4 = manager.get_table(window_size=4)
        table6 = manager.get_table(window_size=6)
        table8 = manager.get_table(window_size=8)

        assert table4 is not table6
        assert table6 is not table8
        assert table4.window_size == 4
        assert table6.window_size == 6
        assert table8.window_size == 8

    def test_clear_cache(self):
        """测试清空缓存."""
        manager = PrecomputedTableManager()
        manager.clear_cache()

        # 创建一些表
        manager.get_table(window_size=4)
        manager.get_table(window_size=6)

        # 清空缓存
        manager.clear_cache()

        # 重新获取应该是新表
        table1 = manager.get_table(window_size=4)
        table2 = manager.get_table(window_size=4)
        assert table1 is table2  # 新的缓存


class TestGlobalFunctions:
    """全局函数测试类."""

    def test_get_precomputed_table(self):
        """测试全局获取函数."""
        precomputed_table_manager.clear_cache()

        table = get_precomputed_table(window_size=6)
        assert isinstance(table, PrecomputedPointTable)
        assert table.window_size == 6

    def test_global_manager_singleton(self):
        """测试全局管理器单例."""
        from src.core.precomputed_table import precomputed_table_manager

        table1 = precomputed_table_manager.get_table(window_size=4)
        table2 = get_precomputed_table(window_size=4)

        assert table1 is table2
