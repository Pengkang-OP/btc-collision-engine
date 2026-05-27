"""secp256k1 预计算表 (precompute.py) 全覆盖测试.

覆盖: _point_add, _int_to_uint32_le, generate_secp256k1_precomp_table, get_precomp_table
"""

import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ---- 绕过 src.gpu.__init__ 导入链（架构必要：sys.modules 注入必须在 src 导入前） ----
_mock_kernel_impl = MagicMock()
_mock_kernel_impl.compile_kernel_with_retry = MagicMock()
sys.modules["src.gpu.kernel_impl"] = _mock_kernel_impl

_mock_context = MagicMock()
_mock_context.GPUContext = MagicMock()
sys.modules["src.gpu.context"] = _mock_context

from src.gpu.precompute import (  # 架构必要：sys.modules mock 注入后立即导入  # noqa: E402
    _int_to_uint32_le,
    _point_add,
    generate_secp256k1_precomp_table,
    get_precomp_table,
)

# 曲线常量（与源码一致）
_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
_GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
_EXPECTED_2G_X = 0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5
_EXPECTED_2G_Y = 0x1AE168FEA63DC339A3C58419466CEAEEF7F632653266D0E1236431A950CFE52A


# ===========================================================================
# Group 1: _point_add 测试
# ===========================================================================


class TestPointAdd:
    """测试 _point_add 椭圆曲线点加法."""

    def test_p1_is_none_returns_p2(self):
        """p1=None 时返回 p2."""
        p2 = (_GX, _GY)
        result = _point_add(None, p2)
        assert result == p2

    def test_p2_is_none_returns_p1(self):
        """p2=None 时返回 p1."""
        p1 = (_GX, _GY)
        result = _point_add(p1, None)
        assert result == p1

    def test_both_none_returns_none(self):
        """两者均为 None 时返回 None."""
        result = _point_add(None, None)
        assert result is None

    def test_opposite_points_return_none(self):
        """P + (-P) = 无穷远点 (None)."""
        # 构造 y2 = P - y1 (mod P)，使得 (x1, y1) + (x1, y2) = ∞
        y_neg = (_P - _GY) % _P
        p1 = (_GX, _GY)
        p2 = (_GX, y_neg)
        result = _point_add(p1, p2)
        assert result is None

    def test_point_doubling_g(self):
        """G + G = 2G (点倍乘)."""
        G = (_GX, _GY)
        result = _point_add(G, G)
        assert result is not None
        x2, y2 = result
        assert x2 == _EXPECTED_2G_X
        assert y2 == _EXPECTED_2G_Y

    def test_general_addition_2g_plus_g(self):
        """2G + G = 3G (一般加法)."""
        G = (_GX, _GY)
        two_G = _point_add(G, G)
        result = _point_add(two_G, G)
        assert result is not None
        # 3G 的坐标在 secp256k1 上有已知值
        expected_3G_x = 0xF9308A019258C31049344F85F89D5229B531C845836F99B08601F113BCE036F9
        expected_3G_y = 0x388F7B0F632DE8140FE337E62A37F3566500A99934C2231B6CB9FD7584B8E672
        x3, y3 = result
        assert x3 == expected_3G_x
        assert y3 == expected_3G_y

    def test_add_non_identity_different_points(self):
        """两个不同非特殊点相加."""
        G = (_GX, _GY)
        two_G = _point_add(G, G)
        three_G = _point_add(two_G, G)
        # 2G + 3G = 5G
        result = _point_add(two_G, three_G)
        assert result is not None

    def test_add_g_plus_2g_equals_3g(self):
        """G + 2G = 3G，确保交换律."""
        G = (_GX, _GY)
        two_G = _point_add(G, G)
        # G + 2G
        result1 = _point_add(G, two_G)
        # 2G + G
        result2 = _point_add(two_G, G)
        assert result1 == result2


# ===========================================================================
# Group 2: _int_to_uint32_le 测试
# ===========================================================================


class TestIntToUint32LE:
    """测试 _int_to_uint32_le 整数→小端序 uint32 数组转换."""

    def test_converts_gx(self):
        """将 GX 转为 8 个 uint32 小端序."""
        limbs = _int_to_uint32_le(_GX)
        assert isinstance(limbs, np.ndarray)
        assert limbs.dtype == np.uint32
        assert len(limbs) == 8
        # 验证小端序：sum(limb[i] << 32i) == _GX
        reconstructed = sum(int(limbs[i]) << (32 * i) for i in range(8))
        assert reconstructed == _GX

    def test_converts_gy(self):
        """将 GY 转为 8 个 uint32 小端序."""
        limbs = _int_to_uint32_le(_GY)
        assert len(limbs) == 8
        reconstructed = sum(int(limbs[i]) << (32 * i) for i in range(8))
        assert reconstructed == _GY

    def test_converts_zero(self):
        """0 的正确转换."""
        limbs = _int_to_uint32_le(0)
        assert len(limbs) == 8
        assert np.all(limbs == 0)

    def test_le_ordering(self):
        """验证小端序：limb[0] 是最低 32 位."""
        value = 0xDEADBEEFCAFEBABE123456789ABCDEF0F0E0D0C0B0A0908070605040302010
        limbs = _int_to_uint32_le(value)
        # 最低 32 位
        assert int(limbs[0]) == (value & 0xFFFFFFFF)
        # 次低 32 位
        assert int(limbs[1]) == ((value >> 32) & 0xFFFFFFFF)

    def test_max_256bit_value(self):
        """最大 256-bit 值的转换."""
        max_val = (1 << 256) - 1
        limbs = _int_to_uint32_le(max_val)
        assert len(limbs) == 8
        # 所有 limb 应为 0xFFFFFFFF
        assert np.all(limbs == 0xFFFFFFFF)
        reconstructed = sum(int(limbs[i]) << (32 * i) for i in range(8))
        assert reconstructed == max_val


# ===========================================================================
# Group 3: generate_secp256k1_precomp_table 测试
# ===========================================================================


class TestGeneratePrecompTable:
    """测试 generate_secp256k1_precomp_table."""

    def test_generates_correct_shape_and_dtype(self):
        """生成正确的 shape 和 dtype."""
        table = generate_secp256k1_precomp_table()
        assert isinstance(table, np.ndarray)
        assert table.dtype == np.uint32
        assert table.shape == (496,)

    def test_first_point_is_g(self):
        """第一个点是基点 G."""
        table = generate_secp256k1_precomp_table()
        gx = sum(int(table[j]) << (32 * j) for j in range(8))
        gy = sum(int(table[8 + j]) << (32 * j) for j in range(8))
        assert gx == _GX
        assert gy == _GY

    def test_second_point_is_2g(self):
        """第二个点是 2G."""
        table = generate_secp256k1_precomp_table()
        g2x = sum(int(table[16 + j]) << (32 * j) for j in range(8))
        g2y = sum(int(table[24 + j]) << (32 * j) for j in range(8))
        assert g2x == _EXPECTED_2G_X
        assert g2y == _EXPECTED_2G_Y

    def test_all_31_points_are_valid(self):
        """所有 31 个点都在曲线上."""
        table = generate_secp256k1_precomp_table()
        for i in range(31):
            offset = i * 16
            x = sum(int(table[offset + j]) << (32 * j) for j in range(8))
            y = sum(int(table[offset + 8 + j]) << (32 * j) for j in range(8))
            # 验证 (x, y) 在 secp256k1 上: y^2 ≡ x^3 + 7 (mod P)
            lhs = (y * y) % _P
            rhs = (x * x * x + 7) % _P
            assert lhs == rhs, f"点 {i + 1}G 不在曲线上"

    def test_1g_validation_raises_on_corruption(self):
        """1G 验证失败时抛出 RuntimeError."""
        original = _int_to_uint32_le
        bad_limbs = np.array([0] * 8, dtype=np.uint32)
        call_count = [0]

        def side_effect(val):
            call_count[0] += 1
            if call_count[0] == 1:
                return bad_limbs  # 1G.x 返回全 0
            return original(val)

        with patch("src.gpu.precompute._int_to_uint32_le", side_effect=side_effect):
            with pytest.raises(RuntimeError, match="1G.x 验证失败"):
                generate_secp256k1_precomp_table()

    def test_2g_x_validation_raises_on_corruption(self):
        """2G.x 验证失败时抛出 RuntimeError."""
        original = _int_to_uint32_le
        bad_limbs = np.array([0] * 8, dtype=np.uint32)
        call_count = [0]

        def side_effect(val):
            call_count[0] += 1
            # call 3 = 2G.x (每点 2 次调用: x 一次, y 一次)
            if call_count[0] == 3:
                return bad_limbs
            return original(val)

        with patch("src.gpu.precompute._int_to_uint32_le", side_effect=side_effect):
            with pytest.raises(RuntimeError, match="2G.x 验证失败"):
                generate_secp256k1_precomp_table()

    def test_2g_y_validation_raises_on_corruption(self):
        """2G.y 验证失败时抛出 RuntimeError."""
        original = _int_to_uint32_le
        bad_limbs = np.array([0] * 8, dtype=np.uint32)
        call_count = [0]

        def side_effect(val):
            call_count[0] += 1
            # call 4 = 2G.y (每点 2 次调用: x 一次, y 一次)
            if call_count[0] == 4:
                return bad_limbs
            return original(val)

        with patch("src.gpu.precompute._int_to_uint32_le", side_effect=side_effect):
            with pytest.raises(RuntimeError, match="2G.y 验证失败"):
                generate_secp256k1_precomp_table()

    def test_1g_y_validation_raises_on_corruption(self):
        """1G.y 验证失败时抛出 RuntimeError (line 115)."""
        original = _int_to_uint32_le
        bad_limbs = np.array([0] * 8, dtype=np.uint32)
        call_count = [0]

        def side_effect(val):
            call_count[0] += 1
            # call 2 = 1G.y，1G.x 保持正确
            if call_count[0] == 2:
                return bad_limbs
            return original(val)

        with patch("src.gpu.precompute._int_to_uint32_le", side_effect=side_effect):
            with pytest.raises(RuntimeError, match="1G.y 验证失败"):
                generate_secp256k1_precomp_table()

    def test_point_at_infinity_raises(self):
        """点加返回无穷远点时抛出 RuntimeError (line 96)."""
        with patch("src.gpu.precompute._point_add", return_value=None):
            with pytest.raises(RuntimeError, match="无穷远点"):
                generate_secp256k1_precomp_table()


# ===========================================================================
# Group 4: get_precomp_table 测试
# ===========================================================================


class TestGetPrecompTable:
    """测试 get_precomp_table 缓存机制."""

    def test_returns_valid_table(self):
        """返回正确的预计算表."""
        import src.gpu.precompute as pc

        # 重置缓存
        pc._cached_table = None
        table = get_precomp_table()
        assert isinstance(table, np.ndarray)
        assert table.shape == (496,)

    def test_caching_returns_same_object(self):
        """缓存生效：第二次调用返回同一对象."""
        import src.gpu.precompute as pc

        pc._cached_table = None
        t1 = get_precomp_table()
        t2 = get_precomp_table()
        assert t1 is t2

    def test_cache_persists_across_calls(self):
        """缓存跨多次调用持久化."""
        import src.gpu.precompute as pc

        pc._cached_table = None
        t1 = get_precomp_table()
        t2 = get_precomp_table()
        t3 = get_precomp_table()
        assert t1 is t2 is t3

    def test_clear_cache_regenerates(self):
        """清除缓存后重新生成."""
        import src.gpu.precompute as pc

        pc._cached_table = None
        t1 = get_precomp_table()
        assert pc._cached_table is not None

        # 清除后重新获取
        pc._cached_table = None
        t2 = get_precomp_table()
        assert t2 is not None
        # 不同对象（因为重新生成）
        assert t1 is not t2
        # 但值相同
        assert np.array_equal(t1, t2)


# ===========================================================================
# Group 5: 模块级常量验证
# ===========================================================================


class TestConstants:
    """验证模块级曲线常量."""

    def test_p_is_secp256k1_prime(self):
        """_P 是 secp256k1 素数."""
        assert _P == 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F

    def test_g_point_is_on_curve(self):
        """基点 G 在曲线上."""
        lhs = (_GY * _GY) % _P
        rhs = (_GX * _GX * _GX + 7) % _P
        assert lhs == rhs

    def test_expected_2g_is_on_curve(self):
        """已知 2G 在曲线上."""
        lhs = (_EXPECTED_2G_Y * _EXPECTED_2G_Y) % _P
        rhs = (_EXPECTED_2G_X * _EXPECTED_2G_X * _EXPECTED_2G_X + 7) % _P
        assert lhs == rhs

    def test_gx_in_range(self):
        """GX 在有效范围内."""
        assert 0 < _GX < _P

    def test_gy_in_range(self):
        """GY 在有效范围内."""
        assert 0 < _GY < _P
