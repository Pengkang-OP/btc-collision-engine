"""secp256k1 深度覆盖率提升测试 — 覆盖之前未测试的路径"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.secp256k1 import ECPoint, EllipticCurve, Secp256k1  # noqa: E402


class TestSecp256k1Parameters(unittest.TestCase):
    """Secp256k1参数类测试 — 覆盖 verify_parameters / get_security_info"""

    def test_verify_parameters_returns_true(self):
        self.assertTrue(Secp256k1.verify_parameters())

    def test_verify_parameters_p_invalid(self):
        class BadP(Secp256k1):
            P = 1
        self.assertFalse(BadP.verify_parameters())

    def test_verify_parameters_n_invalid(self):
        class BadN(Secp256k1):
            N = 1
        self.assertFalse(BadN.verify_parameters())

    def test_verify_parameters_bad_curve_eq(self):
        class BadPoint(Secp256k1):
            Gy = Secp256k1.Gy + 1
        self.assertFalse(BadPoint.verify_parameters())

    def test_verify_parameters_n_ge_p(self):
        class BadOrder(Secp256k1):
            N = Secp256k1.P + 1
        self.assertFalse(BadOrder.verify_parameters())

    def test_get_security_info_has_keys(self):
        info = Secp256k1.get_security_info()
        self.assertEqual(info["name"], "secp256k1")
        self.assertEqual(info["bit_length"], 256)
        self.assertEqual(info["security_level"], "128-bit")
        self.assertIn("parameter_sizes", info)
        sizes = info["parameter_sizes"]
        self.assertEqual(sizes["P_bits"], 256)
        self.assertEqual(sizes["N_bits"], 256)
        self.assertEqual(sizes["G_x_bits"], 255)
        self.assertEqual(sizes["G_y_bits"], 255)
        self.assertTrue(info["parameters_verified"])

    def test_parameter_constants(self):
        self.assertGreater(Secp256k1.P, 2**255)
        self.assertGreater(Secp256k1.N, 2**255)
        self.assertEqual(Secp256k1.A, 0)
        self.assertEqual(Secp256k1.B, 7)


class TestECPointEdge(unittest.TestCase):
    """ECPoint 边界测试"""

    def test_eq_non_ecpoint(self):
        p = ECPoint(100, 200)
        self.assertNotEqual(p, "not a point")
        self.assertNotEqual(p, None)
        self.assertNotEqual(p, 42)

    def test_eq_infinity_different_curve(self):
        class FakeCurve:
            pass
        p1 = ECPoint(None, None, Secp256k1)
        p2 = ECPoint(None, None, FakeCurve)
        self.assertEqual(p1, p2)

    def test_copy_preserves_coordinates(self):
        p = ECPoint(0x123456, 0x789ABC)
        c = p.copy()
        self.assertEqual(c.x, 0x123456)
        self.assertEqual(c.y, 0x789ABC)
        self.assertIsNot(c, p)

    def test_copy_individual_curve(self):
        class FakeCurve:
            pass
        p = ECPoint(1, 2, FakeCurve)
        c = p.copy()
        self.assertIs(c.curve, FakeCurve)

    def test_constructor_sets_curve_default(self):
        p = ECPoint(100, 200)
        self.assertIs(p.curve, Secp256k1)

    def test_constructor_explicit_none(self):
        p = ECPoint(None, None)
        self.assertTrue(p.is_infinity)
        self.assertIsNone(p.x)
        self.assertIsNone(p.y)


class TestIsOnCurve(unittest.TestCase):
    """椭圆曲线点验证测试 — is_on_curve 方法（之前完全未覆盖）"""

    def setUp(self):
        self.ec = EllipticCurve()

    def test_generator_on_curve(self):
        G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        self.assertTrue(self.ec.is_on_curve(G))

    def test_infinity_on_curve(self):
        inf = ECPoint(None, None)
        self.assertTrue(self.ec.is_on_curve(inf))

    def test_point_not_on_curve(self):
        p = ECPoint(100, 200)
        self.assertFalse(self.ec.is_on_curve(p))

    def test_random_valid_point(self):
        G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        k = 123456789
        Q = self.ec.scalar_multiply_const_time(k, G)
        self.assertTrue(self.ec.is_on_curve(Q))

    def test_multiple_valid_points(self):
        G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        for k in [1, 2, 3, 42, 9999, 100000]:
            Q = self.ec.scalar_multiply_const_time(k, G)
            self.assertTrue(self.ec.is_on_curve(Q))


class TestConstTimeSelect(unittest.TestCase):
    """恒定时间条件选择深度测试 — _const_time_select"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        self.inf = ECPoint(None, None)

    def test_select_condition_0_normal(self):
        a = ECPoint(100, 200)
        b = ECPoint(300, 400)
        r = self.ec._const_time_select(0, a, b)
        self.assertEqual(r, a)

    def test_select_condition_1_normal(self):
        a = ECPoint(100, 200)
        b = ECPoint(300, 400)
        r = self.ec._const_time_select(1, a, b)
        self.assertEqual(r, b)

    def test_select_condition_0_a_inf(self):
        a = ECPoint(None, None)
        b = self.G
        r = self.ec._const_time_select(0, a, b)
        self.assertTrue(r.is_infinity)

    def test_select_condition_1_a_inf(self):
        a = ECPoint(None, None)
        b = self.G
        r = self.ec._const_time_select(1, a, b)
        self.assertEqual(r, self.G)

    def test_select_condition_0_b_inf(self):
        a = self.G
        b = ECPoint(None, None)
        r = self.ec._const_time_select(0, a, b)
        self.assertEqual(r, self.G)

    def test_select_condition_1_b_inf(self):
        a = self.G
        b = ECPoint(None, None)
        r = self.ec._const_time_select(1, a, b)
        self.assertTrue(r.is_infinity)

    def test_select_both_inf(self):
        a = ECPoint(None, None)
        b = ECPoint(None, None)
        r = self.ec._const_time_select(0, a, b)
        self.assertTrue(r.is_infinity)
        r = self.ec._const_time_select(1, a, b)
        self.assertTrue(r.is_infinity)


class TestValidateScalarMultiply(unittest.TestCase):
    """_validate_scalar_multiply 输入验证测试"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

    def test_k_not_int_raises(self):
        with self.assertRaises(TypeError):
            self.ec._validate_scalar_multiply("abc", self.G)

    def test_k_float_raises(self):
        with self.assertRaises(TypeError):
            self.ec._validate_scalar_multiply(3.14, self.G)

    def test_point_not_ecpoint_raises(self):
        with self.assertRaises(TypeError):
            self.ec._validate_scalar_multiply(42, "not a point")

    def test_valid_inputs_pass(self):
        self.ec._validate_scalar_multiply(42, self.G)


class TestScalarMultiplyDeprecated(unittest.TestCase):
    """scalar_multiply 弃用方法边界测试"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

    def test_emits_deprecation_warning(self):
        with self.assertWarns(DeprecationWarning):
            self.ec.scalar_multiply(1, self.G)

    def test_k_mod_n_result(self):
        k = Secp256k1.N + 1
        result = self.ec.scalar_multiply(k, self.G)
        self.assertFalse(result.is_infinity)


class TestScalarMultiplyConstTimeDeep(unittest.TestCase):
    """恒定时间标量乘法深度测试"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

    def test_k_mod_n_zero(self):
        k = Secp256k1.N
        result = self.ec.scalar_multiply_const_time(k, self.G)
        self.assertTrue(result.is_infinity)

    def test_k_mod_n_returns_infinity(self):
        k = 2 * Secp256k1.N
        result = self.ec.scalar_multiply_const_time(k, self.G)
        self.assertTrue(result.is_infinity)

    def test_infinity_point(self):
        inf = ECPoint(None, None)
        result = self.ec.scalar_multiply_const_time(42, inf)
        self.assertTrue(result.is_infinity)

    def test_large_scalar(self):
        k = 10**20
        result = self.ec.scalar_multiply_const_time(k, self.G)
        self.assertFalse(result.is_infinity)
        self.assertIsInstance(result.x, int)

    def test_max_bit_scalar(self):
        k = (1 << 256) - 1
        result = self.ec.scalar_multiply_const_time(k, self.G)
        self.assertFalse(result.is_infinity)

    def test_consistency_with_standard(self):
        for k in [13, 77, 256, 65535, 12345678901234567890]:
            r1 = self.ec.scalar_multiply_const_time(k, self.G)
            r2 = self.ec.scalar_multiply(k, self.G)
            self.assertEqual(r1, r2)


class TestGeneratePublicKeyDeep(unittest.TestCase):
    """公钥生成深度测试"""

    def setUp(self):
        self.ec = EllipticCurve()

    def test_from_bytes_private_key(self):
        pk = (12345).to_bytes(32, "big")
        pub = self.ec.generate_public_key(pk, compressed=True)
        self.assertEqual(len(pub), 33)

    def test_from_int_private_key(self):
        pub = self.ec.generate_public_key(12345, compressed=False)
        self.assertEqual(len(pub), 65)
        self.assertEqual(pub[0], 4)

    def test_zero_private_key_raises(self):
        pk = (0).to_bytes(32, "big")
        with self.assertRaises(ValueError):
            self.ec.generate_public_key(pk)

    def test_order_private_key_raises(self):
        pk = Secp256k1.N.to_bytes(32, "big")
        with self.assertRaises(ValueError):
            self.ec.generate_public_key(pk)

    def test_compressed_prefix_02_or_03(self):
        import random
        random.seed(42)
        for _ in range(20):
            k = random.randint(1, 10**12)
            pk = k.to_bytes(32, "big")
            pub = self.ec.generate_public_key(pk, compressed=True)
            self.assertIn(pub[0], [2, 3])

    def test_uncompressed_prefix_04(self):
        import random
        random.seed(42)
        for _ in range(20):
            k = random.randint(1, 10**12)
            pk = k.to_bytes(32, "big")
            pub = self.ec.generate_public_key(pk, compressed=False)
            self.assertEqual(pub[0], 4)

    def test_compressed_odd_y_prefix_03(self):
        G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        k = 5
        Q = self.ec.scalar_multiply_const_time(k, G)
        pk = k.to_bytes(32, "big")
        pub = self.ec.generate_public_key(pk, compressed=True)
        self.assertEqual(pub[1:], (Q.x).to_bytes(32, "big"))

    def test_generate_public_key_const_time_alias(self):
        pk = (42).to_bytes(32, "big")
        pub1 = self.ec.generate_public_key(pk, compressed=True)
        pub2 = self.ec.generate_public_key_const_time(pk, compressed=True)
        self.assertEqual(pub1, pub2)

    def test_large_private_key(self):
        pk = (Secp256k1.N - 1).to_bytes(32, "big")
        pub = self.ec.generate_public_key(pk, compressed=True)
        self.assertEqual(len(pub), 33)

    def test_private_key_1(self):
        pk = (1).to_bytes(32, "big")
        pub = self.ec.generate_public_key(pk, compressed=True)
        self.assertEqual(len(pub), 33)
        self.assertEqual(pub[1:], Secp256k1.Gx.to_bytes(32, "big"))


class TestModInverseEdge(unittest.TestCase):
    """模逆元边界测试"""

    def setUp(self):
        self.ec = EllipticCurve()

    def test_large_numbers(self):
        p = Secp256k1.P
        inv = self.ec.mod_inverse(123456789, p)
        self.assertEqual((123456789 * inv) % p, 1)

    def test_result_normalized_positive(self):
        result = self.ec.mod_inverse(-3, 7)
        self.assertGreaterEqual(result, 0)
        self.assertLess(result, 7)

    def test_gcd_larger_than_1_raises(self):
        with self.assertRaises(ValueError):
            self.ec.mod_inverse(6, 9)


class TestPointAddEdge(unittest.TestCase):
    """点加法边界测试"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

    def test_double_infinity(self):
        inf = ECPoint(None, None)
        result = self.ec.point_add(inf, inf)
        self.assertTrue(result.is_infinity)

    def test_same_x_but_different_y(self):
        x = 12345
        y1 = 67890 % Secp256k1.P
        y2 = (Secp256k1.P - y1) % Secp256k1.P
        p1 = ECPoint(x, y1)
        p2 = ECPoint(x, y2)
        result = self.ec.point_add(p1, p2)
        self.assertTrue(result.is_infinity)

    def test_same_point_doubling(self):
        G2 = self.ec.point_add(self.G, self.G)
        self.assertEqual(G2, self.ec.scalar_multiply(2, self.G))


class TestModInverseSummary(unittest.TestCase):
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
            self.assertEqual((a * inv) % p, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
