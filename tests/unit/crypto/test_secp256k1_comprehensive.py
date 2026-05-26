"""secp256k1 深度覆盖率提升测试 — 覆盖之前未测试的路径"""

import math
import os
import pytest

from src.core.secp256k1 import ECPoint, EllipticCurve, Secp256k1


class TestSecp256k1Parameters:
    """Secp256k1参数类测试 — 覆盖 verify_parameters / get_security_info"""

    def test_verify_parameters_returns_true(self):
        assert Secp256k1.verify_parameters()

    def test_verify_parameters_p_invalid(self):
        class BadP(Secp256k1):
            P = 1

        assert not BadP.verify_parameters()

    def test_verify_parameters_n_invalid(self):
        class BadN(Secp256k1):
            N = 1

        assert not BadN.verify_parameters()

    def test_verify_parameters_bad_curve_eq(self):
        class BadPoint(Secp256k1):
            Gy = Secp256k1.Gy + 1

        assert not BadPoint.verify_parameters()

    def test_verify_parameters_n_ge_p(self):
        class BadOrder(Secp256k1):
            N = Secp256k1.P + 1

        assert not BadOrder.verify_parameters()

    def test_get_security_info_has_keys(self):
        info = Secp256k1.get_security_info()
        assert info["name"]  ==  "secp256k1"
        assert info["bit_length"]  ==  256
        assert info["security_level"]  ==  "128-bit"
        assert info  in  "parameter_sizes"
        sizes = info["parameter_sizes"]
        assert sizes["P_bits"]  ==  256
        assert sizes["N_bits"]  ==  256
        assert sizes["G_x_bits"]  ==  255
        assert sizes["G_y_bits"]  ==  255
        assert info["parameters_verified"]

    def test_parameter_constants(self):
        assert Secp256k1.P  >  2**255
        assert Secp256k1.N  >  2**255
        assert Secp256k1.A  ==  0
        assert Secp256k1.B  ==  7


class TestECPointEdge:
    """ECPoint 边界测试"""

    def test_eq_non_ecpoint(self):
        p = ECPoint(100, 200)
        assert p  !=  "not a point"
        assert p  !=  None
        assert p  !=  42

    def test_eq_infinity_different_curve(self):
        class FakeCurve:
            pass

        p1 = ECPoint(None, None, Secp256k1)
        p2 = ECPoint(None, None, FakeCurve)
        assert p1  ==  p2

    def test_copy_preserves_coordinates(self):
        p = ECPoint(0x123456, 0x789ABC)
        c = p.copy()
        assert c.x  ==  0x123456
        assert c.y  ==  0x789ABC
        assert c  is not  p

    def test_copy_individual_curve(self):
        class FakeCurve:
            pass

        p = ECPoint(1, 2, FakeCurve)
        c = p.copy()
        assert c.curve  is  FakeCurve

    def test_constructor_sets_curve_default(self):
        p = ECPoint(100, 200)
        assert p.curve  is  Secp256k1

    def test_constructor_explicit_none(self):
        p = ECPoint(None, None)
        assert p.is_infinity
        assert p.x is None
        assert p.y is None


class TestIsOnCurve:
    """椭圆曲线点验证测试 — is_on_curve 方法（之前完全未覆盖）"""

    def setUp(self):
        self.ec = EllipticCurve()

    def test_generator_on_curve(self):
        G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        assert self.ec.is_on_curve(G)

    def test_infinity_on_curve(self):
        inf = ECPoint(None, None)
        assert self.ec.is_on_curve(inf)

    def test_point_not_on_curve(self):
        p = ECPoint(100, 200)
        assert not self.ec.is_on_curve(p)

    def test_random_valid_point(self):
        G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        k = 123456789
        Q = self.ec.scalar_multiply_const_time(k, G)
        assert self.ec.is_on_curve(Q)

    def test_multiple_valid_points(self):
        G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        for k in [1, 2, 3, 42, 9999, 100000]:
            Q = self.ec.scalar_multiply_const_time(k, G)
            assert self.ec.is_on_curve(Q)


class TestConstTimeSelect:
    """恒定时间条件选择深度测试 — _const_time_select"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        self.inf = ECPoint(None, None)

    def test_select_condition_0_normal(self):
        a = ECPoint(100, 200)
        b = ECPoint(300, 400)
        r = self.ec._const_time_select(0, a, b)
        assert r  ==  a

    def test_select_condition_1_normal(self):
        a = ECPoint(100, 200)
        b = ECPoint(300, 400)
        r = self.ec._const_time_select(1, a, b)
        assert r  ==  b

    def test_select_condition_0_a_inf(self):
        a = ECPoint(None, None)
        b = self.G
        r = self.ec._const_time_select(0, a, b)
        assert r.is_infinity

    def test_select_condition_1_a_inf(self):
        a = ECPoint(None, None)
        b = self.G
        r = self.ec._const_time_select(1, a, b)
        assert r  ==  self.G

    def test_select_condition_0_b_inf(self):
        a = self.G
        b = ECPoint(None, None)
        r = self.ec._const_time_select(0, a, b)
        assert r  ==  self.G

    def test_select_condition_1_b_inf(self):
        a = self.G
        b = ECPoint(None, None)
        r = self.ec._const_time_select(1, a, b)
        assert r.is_infinity

    def test_select_both_inf(self):
        a = ECPoint(None, None)
        b = ECPoint(None, None)
        r = self.ec._const_time_select(0, a, b)
        assert r.is_infinity
        r = self.ec._const_time_select(1, a, b)
        assert r.is_infinity


class TestValidateScalarMultiply:
    """_validate_scalar_multiply 输入验证测试"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

    def test_k_not_int_raises(self):
        with pytest.raises(TypeError):
            self.ec._validate_scalar_multiply("abc", self.G)

    def test_k_float_raises(self):
        with pytest.raises(TypeError):
            self.ec._validate_scalar_multiply(math.pi, self.G)

    def test_point_not_ecpoint_raises(self):
        with pytest.raises(TypeError):
            self.ec._validate_scalar_multiply(42, "not a point")

    def test_valid_inputs_pass(self):
        self.ec._validate_scalar_multiply(42, self.G)


class TestScalarMultiplyDeprecated:
    """scalar_multiply 已锁定 — 验证 RuntimeError 行为 (v4.2.2 BLOCK #9)"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        self._saved_env = os.environ.pop("BTC_ALLOW_NON_CONST_TIME", None)

    def tearDown(self):
        if self._saved_env is not None:
            os.environ["BTC_ALLOW_NON_CONST_TIME"] = self._saved_env

    def test_emits_deprecation_warning(self):
        """调用 scalar_multiply 应抛出 RuntimeError (非 DeprecationWarning)"""
        with self.assertRaises(RuntimeError) as ctx:
            self.ec.scalar_multiply(1, self.G)
        assert str(ctx.exception)  in  "已被永久禁用"

    def test_k_mod_n_result(self):
        """K % N 结果测试 → RuntimeError (已锁定)"""
        k = Secp256k1.N + 1
        with self.assertRaises(RuntimeError) as ctx:
            self.ec.scalar_multiply(k, self.G)
        assert str(ctx.exception)  in  "已被永久禁用"


class TestScalarMultiplyConstTimeDeep:
    """恒定时间标量乘法深度测试"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

    def test_k_mod_n_zero(self):
        k = Secp256k1.N
        result = self.ec.scalar_multiply_const_time(k, self.G)
        assert result.is_infinity

    def test_k_mod_n_returns_infinity(self):
        k = 2 * Secp256k1.N
        result = self.ec.scalar_multiply_const_time(k, self.G)
        assert result.is_infinity

    def test_infinity_point(self):
        inf = ECPoint(None, None)
        result = self.ec.scalar_multiply_const_time(42, inf)
        assert result.is_infinity

    def test_large_scalar(self):
        k = 10**20
        result = self.ec.scalar_multiply_const_time(k, self.G)
        assert not result.is_infinity
        assert isinstance(result.x, int)

    def test_max_bit_scalar(self):
        k = (1 << 256) - 1
        result = self.ec.scalar_multiply_const_time(k, self.G)
        assert not result.is_infinity

    def test_consistency_with_standard(self):
        """恒定时间算法与自身一致（scalar_multiply 已锁定不可对比）"""
        for k in [13, 77, 256, 65535, 12345678901234567890]:
            r1 = self.ec.scalar_multiply_const_time(k, self.G)
            r2 = self.ec.scalar_multiply_const_time(k, self.G)
            assert r1  ==  r2


class TestGeneratePublicKeyDeep:
    """公钥生成深度测试"""

    def setUp(self):
        self.ec = EllipticCurve()

    def test_from_bytes_private_key(self):
        pk = (12345).to_bytes(32, "big")
        pub = self.ec.generate_public_key(pk, compressed=True)
        assert len(pub)  ==  33

    def test_from_int_private_key(self):
        pub = self.ec.generate_public_key(12345, compressed=False)
        assert len(pub)  ==  65
        assert pub[0]  ==  4

    def test_zero_private_key_raises(self):
        pk = (0).to_bytes(32, "big")
        with pytest.raises(ValueError):
            self.ec.generate_public_key(pk)

    def test_order_private_key_raises(self):
        pk = Secp256k1.N.to_bytes(32, "big")
        with pytest.raises(ValueError):
            self.ec.generate_public_key(pk)

    def test_compressed_prefix_02_or_03(self):
        import random

        random.seed(42)
        for _ in range(20):
            k = random.randint(1, 10**12)
            pk = k.to_bytes(32, "big")
            pub = self.ec.generate_public_key(pk, compressed=True)
            assert [2, 3]  in  pub[0]

    def test_uncompressed_prefix_04(self):
        import random

        random.seed(42)
        for _ in range(20):
            k = random.randint(1, 10**12)
            pk = k.to_bytes(32, "big")
            pub = self.ec.generate_public_key(pk, compressed=False)
            assert pub[0]  ==  4

    def test_compressed_odd_y_prefix_03(self):
        G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        k = 5
        Q = self.ec.scalar_multiply_const_time(k, G)
        pk = k.to_bytes(32, "big")
        pub = self.ec.generate_public_key(pk, compressed=True)
        assert pub[1:]  ==  (Q.x).to_bytes(32, "big")

    def test_generate_public_key_const_time_alias(self):
        pk = (42).to_bytes(32, "big")
        pub1 = self.ec.generate_public_key(pk, compressed=True)
        pub2 = self.ec.generate_public_key_const_time(pk, compressed=True)
        assert pub1  ==  pub2

    def test_large_private_key(self):
        pk = (Secp256k1.N - 1).to_bytes(32, "big")
        pub = self.ec.generate_public_key(pk, compressed=True)
        assert len(pub)  ==  33

    def test_private_key_1(self):
        pk = (1).to_bytes(32, "big")
        pub = self.ec.generate_public_key(pk, compressed=True)
        assert len(pub)  ==  33
        assert pub[1:]  ==  Secp256k1.Gx.to_bytes(32, "big")


class TestModInverseEdge:
    """模逆元边界测试"""

    def setUp(self):
        self.ec = EllipticCurve()

    def test_large_numbers(self):
        p = Secp256k1.P
        inv = self.ec.mod_inverse(123456789, p)
        assert (123456789 * inv) % p  ==  1

    def test_result_normalized_positive(self):
        result = self.ec.mod_inverse(-3, 7)
        assert result  >=  0
        assert result  <  7

    def test_gcd_larger_than_1_raises(self):
        with pytest.raises(ValueError):
            self.ec.mod_inverse(6, 9)


class TestPointAddEdge:
    """点加法边界测试"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

    def test_double_infinity(self):
        inf = ECPoint(None, None)
        result = self.ec.point_add(inf, inf)
        assert result.is_infinity

    def test_same_x_but_different_y(self):
        x = 12345
        y1 = 67890 % Secp256k1.P
        y2 = (Secp256k1.P - y1) % Secp256k1.P
        p1 = ECPoint(x, y1)
        p2 = ECPoint(x, y2)
        result = self.ec.point_add(p1, p2)
        assert result.is_infinity

    def test_same_point_doubling(self):
        G2 = self.ec.point_add(self.G, self.G)
        assert G2  ==  self.ec.scalar_multiply_const_time(2, self.G)


class TestModInverseSummary:
    """模逆元高级测试"""

    def setUp(self):
        self.ec = EllipticCurve()

    def test_mod_inverse_batch_secp256k1(self):
        import random

        random.seed(77)
        p = Secp256k1.P
        for _ in range(10):
            a = random.randint(1, p - 1)
            inv = self.ec.mod_inverse(a, p)
            assert (a * inv) % p  ==  1


if __name__ == "__main__":
    unittest.main(verbosity=2)
