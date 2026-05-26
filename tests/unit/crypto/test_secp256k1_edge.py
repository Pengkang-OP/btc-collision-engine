"""secp256k1.py 边界与错误路径全覆盖测试

覆盖缺失行: 62-80, 85, 141-147, 156-158, 220, 222, 224, 227, 238,
            267, 269, 275, 285, 325, 350, 352, 397, 402, 469,
            501, 506, 569, 579, 607
"""

import os
from unittest.mock import patch

import pytest

from src.core.secp256k1 import ECPoint, EllipticCurve, Secp256k1

# ===========================================================================
# Group 1: Secp256k1 classmethods (lines 62-80, 85)
# ===========================================================================


class TestSecp256k1VerifyParameters:
    """Secp256k1.verify_parameters 所有分支"""

    def test_verify_parameters_all_pass(self):
        """真实参数全部通过 → line 80"""
        assert Secp256k1.verify_parameters()

    def test_verify_parameters_P_leq_1(self):
        """P <= 1 → False → line 63"""
        with patch.object(Secp256k1, "P", 0):
            assert not Secp256k1.verify_parameters()

    def test_verify_parameters_N_leq_1(self):
        """N <= 1 → False → line 67"""
        with patch.object(Secp256k1, "N", 0):
            assert not Secp256k1.verify_parameters()

    def test_verify_parameters_G_not_on_curve(self):
        """G 不在曲线上 → False → line 73"""
        # 修改 Gy 使 G 不在曲线上
        with patch.object(Secp256k1, "Gy", 1):
            assert not Secp256k1.verify_parameters()

    def test_verify_parameters_N_geq_P(self):
        """N >= P → False → line 78"""
        with patch.object(Secp256k1, "N", Secp256k1.P + 1):
            assert not Secp256k1.verify_parameters()

    def test_get_security_info(self):
        """get_security_info 正常返回 → line 85"""
        info = Secp256k1.get_security_info()
        assert info["name"]  ==  "secp256k1"
        assert info["bit_length"]  ==  256
        assert info  in  "parameters_verified"


# ===========================================================================
# Group 2: ECPoint (lines 141-147, 156-158)
# ===========================================================================


class TestECPointEdge:
    """ECPoint 边界方法"""

    def test_eq_not_ecpoint(self):
        """与非 ECPoint 比较 → line 142"""
        p = ECPoint(1, 2)
        assert not p == "not_a_point"
        assert not p == 42

    def test_eq_both_infinity(self):
        """两个无穷远点相等 → line 144"""
        p1 = ECPoint(None, None)
        p2 = ECPoint(None, None)
        assert p1 == p2

    def test_eq_one_infinity(self):
        """一个无穷远点、一个普通点 → line 146"""
        p1 = ECPoint(None, None)
        p2 = ECPoint(1, 2)
        assert not p1 == p2

    def test_eq_same_coords(self):
        """相同坐标 → line 147"""
        p1 = ECPoint(5, 10)
        p2 = ECPoint(5, 10)
        assert p1 == p2

    def test_eq_diff_coords(self):
        """不同坐标 → line 147"""
        p1 = ECPoint(5, 10)
        p2 = ECPoint(5, 11)
        assert not p1 == p2

    def test_repr_infinity(self):
        """无穷远点 repr → line 157"""
        p = ECPoint(None, None)
        assert repr(p)  in  "Infinity"

    def test_repr_normal(self):
        """普通点 repr → line 158"""
        p = ECPoint(0xAB, 0xCD)
        r = repr(p)
        assert r  in  "ECPoint"
        assert r  in  "x="
        assert r  in  "y="


# ===========================================================================
# Group 3: mod_inverse / point_add / is_on_curve (lines 220-285, 325)
# ===========================================================================


class TestModInverseEdge:
    """EllipticCurve.mod_inverse 异常分支"""

    def setUp(self):
        self.ec = EllipticCurve()

    def test_a_not_int(self):
        """A 非 int → TypeError → line 220"""
        with self.assertRaises(TypeError) as ctx:
            self.ec.mod_inverse("3", 11)
        assert str(ctx.exception)  in  "a必须是整数"

    def test_m_not_int(self):
        """M 非 int → TypeError → line 222"""
        with self.assertRaises(TypeError) as ctx:
            self.ec.mod_inverse(3, "11")
        assert str(ctx.exception)  in  "m必须是整数"

    def test_m_not_positive(self):
        """M <= 0 → ValueError → line 224"""
        with self.assertRaises(ValueError) as ctx:
            self.ec.mod_inverse(3, 0)
        assert str(ctx.exception)  in  "m必须是正整数"

        with pytest.raises(ValueError):
            self.ec.mod_inverse(3, -5)

    def test_negative_a_normalized(self):
        """A < 0 被规范化 → line 227"""
        result = self.ec.mod_inverse(-3, 11)
        # -3 mod 11 = 8, inverse of 8 mod 11 is 7
        assert result  ==  7

    def test_no_inverse_raises(self):
        """逆元不存在 → ValueError → line 238"""
        with self.assertRaises(ValueError) as ctx:
            self.ec.mod_inverse(2, 4)
        assert str(ctx.exception)  in  "模逆元不存在"


class TestPointAddEdge:
    """EllipticCurve.point_add 异常/边界"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

    def test_p1_not_ecpoint(self):
        """p1 非 ECPoint → TypeError → line 267"""
        with self.assertRaises(TypeError) as ctx:
            self.ec.point_add("not_a_point", self.G)
        assert str(ctx.exception)  in  "p1必须是ECPoint"

    def test_p2_not_ecpoint(self):
        """p2 非 ECPoint → TypeError → line 269"""
        with self.assertRaises(TypeError) as ctx:
            self.ec.point_add(self.G, 42)
        assert str(ctx.exception)  in  "p2必须是ECPoint"

    def test_p2_is_infinity(self):
        """p2 是无穷远点 → 返回 p1 → line 275"""
        inf = ECPoint(None, None)
        result = self.ec.point_add(self.G, inf)
        assert result  ==  self.G

    def test_inverse_points(self):
        """互为逆元的点 → 无穷远点 → line 285"""
        # 2*G 的逆元是 -(2*G), 即 (x, P-y)
        G2 = self.ec.scalar_multiply_const_time(2, self.G)
        G2_neg = ECPoint(G2.x, Secp256k1.P - G2.y)
        result = self.ec.point_add(G2, G2_neg)
        assert result.is_infinity


class TestIsOnCurveEdge:
    """is_on_curve 边界"""

    def setUp(self):
        self.ec = EllipticCurve()

    def test_infinity_is_on_curve(self):
        """无穷远点在曲线上 → line 325"""
        inf = ECPoint(None, None)
        assert self.ec.is_on_curve(inf)


# ===========================================================================
# Group 4: _validate_scalar_multiply / scalar_multiply / _const_time_select
# / scalar_multiply_const_time (lines 350-506)
# ===========================================================================


class TestValidateScalarMultiply:
    """_validate_scalar_multiply 异常分支"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

    def test_k_not_int(self):
        """K 非 int → TypeError → line 350"""
        with self.assertRaises(TypeError) as ctx:
            self.ec._validate_scalar_multiply("123", self.G)
        assert str(ctx.exception)  in  "标量k必须是整数"

    def test_point_not_ecpoint(self):
        """Point 非 ECPoint → TypeError → line 352"""
        with self.assertRaises(TypeError) as ctx:
            self.ec._validate_scalar_multiply(5, "not_a_point")
        assert str(ctx.exception)  in  "point必须是ECPoint"


class TestScalarMultiplyEdge:
    """scalar_multiply 已锁定 — 验证 RuntimeError 行为 (v4.2.2 BLOCK #9)"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        # 确保环境变量未设置，以测试锁定行为
        self._saved_env = os.environ.pop("BTC_ALLOW_NON_CONST_TIME", None)

    def tearDown(self):
        if self._saved_env is not None:
            os.environ["BTC_ALLOW_NON_CONST_TIME"] = self._saved_env

    def test_k_zero(self):
        """k==0 → RuntimeError (已锁定)"""
        with self.assertRaises(RuntimeError) as ctx:
            self.ec.scalar_multiply(0, self.G)
        assert str(ctx.exception)  in  "已被永久禁用"

    def test_point_infinity(self):
        """Point 无穷远点 → RuntimeError (已锁定)"""
        inf = ECPoint(None, None)
        with self.assertRaises(RuntimeError) as ctx:
            self.ec.scalar_multiply(5, inf)
        assert str(ctx.exception)  in  "已被永久禁用"

    def test_k_mod_N_zero(self):
        """K % N == 0 → RuntimeError (已锁定)"""
        k = Secp256k1.N * 2
        with self.assertRaises(RuntimeError) as ctx:
            self.ec.scalar_multiply(k, self.G)
        assert str(ctx.exception)  in  "已被永久禁用"

    def test_normal_scalar_multiply(self):
        """正常标量乘法 → RuntimeError (已锁定)"""
        with self.assertRaises(RuntimeError) as ctx:
            self.ec.scalar_multiply(5, self.G)
        assert str(ctx.exception)  in  "已被永久禁用"


class TestConstTimeSelectEdge:
    """_const_time_select 边界"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

    def test_select_infinity_result(self):
        """选择结果为无穷远点 → line 469"""
        # 两个无穷远点，选哪个都是无穷远点
        inf_a = ECPoint(None, None)
        inf_b = ECPoint(None, None)
        result = self.ec._const_time_select(0, inf_a, inf_b)
        assert result.is_infinity

        result = self.ec._const_time_select(1, inf_a, inf_b)
        assert result.is_infinity

    def test_select_normal_points(self):
        """普通点选择"""
        a = self.ec.scalar_multiply_const_time(2, self.G)
        b = self.ec.scalar_multiply_const_time(3, self.G)
        # condition=0 → select a
        r0 = self.ec._const_time_select(0, a, b)
        assert r0  ==  a
        # condition=1 → select b
        r1 = self.ec._const_time_select(1, a, b)
        assert r1  ==  b


class TestScalarMultiplyConstTimeEdge:
    """scalar_multiply_const_time 边界"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

    def test_k_zero_const_time(self):
        """k==0 → 无穷远点 → line 501"""
        result = self.ec.scalar_multiply_const_time(0, self.G)
        assert result.is_infinity

    def test_point_infinity_const_time(self):
        """Point 无穷远点 → line 501"""
        inf = ECPoint(None, None)
        result = self.ec.scalar_multiply_const_time(5, inf)
        assert result.is_infinity

    def test_k_mod_N_zero_const_time(self):
        """K % N == 0 → 无穷远点 → line 506"""
        k = Secp256k1.N * 3
        result = self.ec.scalar_multiply_const_time(k, self.G)
        assert result.is_infinity

    def test_normal_const_time(self):
        """正常恒定时间标量乘法"""
        result = self.ec.scalar_multiply_const_time(5, self.G)
        assert not result.is_infinity
        assert self.ec.is_on_curve(result)


# ===========================================================================
# Group 5: generate_public_key / generate_public_key_const_time
# (lines 569, 579, 607)
# ===========================================================================


class TestGeneratePublicKeyEdge:
    """generate_public_key 回退路径"""

    def setUp(self):
        self.ec = EllipticCurve()
        # 私钥 1
        self.pk = (1).to_bytes(32, "big")

    def test_generate_public_key_int_input(self):
        """Int 型私钥输入 → line 569"""
        result = self.ec.generate_public_key(1, compressed=True)
        assert len(result)  ==  33
        assert [2, 3]  in  result[0]

    def test_generate_public_key_infinity_raises(self):
        """公钥无穷远点 → ValueError → line 579"""
        # N * G = 无穷远点
        with self.assertRaises(ValueError) as ctx:
            self.ec.generate_public_key(Secp256k1.N.to_bytes(32, "big"))
        assert str(ctx.exception)  in  "无穷远点"

    def test_generate_public_key_const_time_alias(self):
        """generate_public_key_const_time 别名 → line 607"""
        result1 = self.ec.generate_public_key(self.pk, compressed=True)
        result2 = self.ec.generate_public_key_const_time(self.pk, compressed=True)
        assert result1  ==  result2

    def test_generate_public_key_const_time_uncompressed(self):
        """非压缩公钥"""
        result = self.ec.generate_public_key_const_time(self.pk, compressed=False)
        assert len(result)  ==  65
        assert result[0]  ==  0x04


if __name__ == "__main__":
    unittest.main(verbosity=2)
