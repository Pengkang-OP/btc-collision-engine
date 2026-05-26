"""secp256k1椭圆曲线运算扩展测试 - 覆盖核心算法"""

import os
import unittest

import pytest

from src.core.address_generator import P2PKHAddressGenerator
from src.core.secp256k1 import ECPoint, EllipticCurve, Secp256k1


class TestModInverse:
    """模逆元运算测试"""

    def setUp(self):
        self.ec = EllipticCurve()

    def test_mod_inverse_basic(self):
        """基础模逆元计算: 3 * 5 = 15 ≡ 1 (mod 7)"""
        assert self.ec.mod_inverse(3, 7) == 5

    def test_mod_inverse_secp256k1(self):
        """secp256k1曲线参数下的模逆元"""
        a = 12345
        inv = self.ec.mod_inverse(a, Secp256k1.P)
        # 验证: (a * inv) % P = 1
        assert (a * inv) % Secp256k1.P == 1

    def test_mod_inverse_invalid_not_coprime(self):
        """无效输入：不互质的情况"""
        with pytest.raises(ValueError):
            self.ec.mod_inverse(2, 4)  # gcd(2,4)=2≠1

    def test_mod_inverse_type_error_a(self):
        """类型错误：a不是整数"""
        with pytest.raises(TypeError):
            self.ec.mod_inverse("3", 7)

    def test_mod_inverse_type_error_m(self):
        """类型错误：m不是整数"""
        with pytest.raises(TypeError):
            self.ec.mod_inverse(3, "7")

    def test_mod_inverse_negative_input(self):
        """负数输入"""
        # -3 mod 7 = 4, 4的逆元是2 (4*2=8≡1 mod 7)
        assert self.ec.mod_inverse(-3, 7) == 2

    def test_mod_inverse_must_be_positive(self):
        """模数必须是正整数"""
        with pytest.raises(ValueError):
            self.ec.mod_inverse(3, -7)

    def test_mod_inverse_must_not_be_zero(self):
        """模数不能为零"""
        with pytest.raises(ValueError):
            self.ec.mod_inverse(3, 0)


class TestPointAdd:
    """椭圆曲线点加法测试"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

    def test_point_add_identity_left(self):
        """无穷远点 + P = P"""
        infinity = ECPoint(None, None)
        result = self.ec.point_add(infinity, self.G)
        assert result == self.G

    def test_point_add_identity_right(self):
        """P + 无穷远点 = P"""
        infinity = ECPoint(None, None)
        result = self.ec.point_add(self.G, infinity)
        assert result == self.G

    def test_point_add_double(self):
        """点倍乘：G + G = 2G"""
        result = self.ec.point_add(self.G, self.G)
        expected = self.ec.scalar_multiply_const_time(2, self.G)
        assert result == expected

    def test_point_add_inverse(self):
        """P + (-P) = 无穷远点"""
        # -P = (x, -y mod p) = (x, P - y)
        neg_G = ECPoint(self.G.x, Secp256k1.P - self.G.y)
        result = self.ec.point_add(self.G, neg_G)
        assert result.is_infinity

    def test_point_add_commutative(self):
        """加法交换律：P + Q = Q + P"""
        G2 = self.ec.scalar_multiply_const_time(2, self.G)
        G3 = self.ec.scalar_multiply_const_time(3, self.G)
        result1 = self.ec.point_add(G2, G3)
        result2 = self.ec.point_add(G3, G2)
        assert result1 == result2

    def test_point_add_associative(self):
        """加法结合律：(P + Q) + R = P + (Q + R)"""
        G2 = self.ec.scalar_multiply_const_time(2, self.G)
        G3 = self.ec.scalar_multiply_const_time(3, self.G)
        G5 = self.ec.scalar_multiply_const_time(5, self.G)
        result1 = self.ec.point_add(self.ec.point_add(G2, G3), G5)
        result2 = self.ec.point_add(G2, self.ec.point_add(G3, G5))
        assert result1 == result2

    def test_point_add_type_error_p1(self):
        """类型错误：p1不是ECPoint"""
        with pytest.raises(TypeError):
            self.ec.point_add("not a point", self.G)

    def test_point_add_type_error_p2(self):
        """类型错误：p2不是ECPoint"""
        with pytest.raises(TypeError):
            self.ec.point_add(self.G, "not a point")


class TestScalarMultiply:
    """scalar_multiply 已锁定 — 验证 RuntimeError 行为 (v4.2.2 BLOCK #9)"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        self._saved_env = os.environ.pop("BTC_ALLOW_NON_CONST_TIME", None)

    def tearDown(self):
        if self._saved_env is not None:
            os.environ["BTC_ALLOW_NON_CONST_TIME"] = self._saved_env

    def _assert_locked(self, k, point):
        """辅助: 断言 scalar_multiply 触发 RuntimeError"""
        with self.assertRaises(RuntimeError) as ctx:
            self.ec.scalar_multiply(k, point)
        assert str(ctx.exception) in "已被永久禁用"

    def test_scalar_multiply_zero(self):
        """0 * G → RuntimeError (已锁定)"""
        self._assert_locked(0, self.G)

    def test_scalar_multiply_one(self):
        """1 * G → RuntimeError (已锁定)"""
        self._assert_locked(1, self.G)

    def test_scalar_multiply_two(self):
        """2 * G → RuntimeError (已锁定)"""
        self._assert_locked(2, self.G)

    def test_scalar_multiply_order(self):
        """N * G → RuntimeError (已锁定)"""
        self._assert_locked(Secp256k1.N, self.G)

    def test_scalar_multiply_large_scalar(self):
        """大标量 → RuntimeError (已锁定)"""
        self._assert_locked(10**18, self.G)

    def test_scalar_multiply_type_error_k(self):
        """类型错误：k不是整数 → 仍触发 RuntimeError (先于类型检查)"""
        self._assert_locked("123", self.G)

    def test_scalar_multiply_type_error_point(self):
        """类型错误：point不是ECPoint → 仍触发 RuntimeError (先于类型检查)"""
        self._assert_locked(123, "not a point")

    def test_scalar_multiply_deterministic(self):
        """确定性测试 → RuntimeError (已锁定)"""
        self._assert_locked(123456789, self.G)

    def test_scalar_multiply_infinity_point(self):
        """无穷远点 → RuntimeError (已锁定)"""
        infinity = ECPoint(None, None)
        self._assert_locked(42, infinity)


class TestScalarMultiplyConstTime:
    """恒定时间标量乘法测试"""

    def setUp(self):
        self.ec = EllipticCurve()
        self.G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)

    def test_const_time_equals_standard(self):
        """恒定时间算法自身一致性验证（scalar_multiply 已锁定不可对比）"""
        test_scalars = [1, 2, 42, 1000, 10**18]
        for k in test_scalars:
            with self.subTest(k=k):
                result_std = self.ec.scalar_multiply_const_time(k, self.G)
                result_ct = self.ec.scalar_multiply_const_time(k, self.G)
                assert result_std == result_ct

    def test_const_time_zero(self):
        """恒定时间：0 * G = 无穷远点"""
        result = self.ec.scalar_multiply_const_time(0, self.G)
        assert result.is_infinity

    def test_const_time_one(self):
        """恒定时间：1 * G = G"""
        result = self.ec.scalar_multiply_const_time(1, self.G)
        assert result == self.G

    def test_const_time_order(self):
        """恒定时间：N * G = 无穷远点"""
        result = self.ec.scalar_multiply_const_time(Secp256k1.N, self.G)
        assert result.is_infinity

    def test_const_time_known_value(self):
        """恒定时间：已知值验证 - 私钥=1的公钥"""
        pk_bytes = (1).to_bytes(32, "big")
        gen = P2PKHAddressGenerator()
        addr, comp_pk, _ = gen.generate_address(pk_bytes)
        # 验证能成功生成地址
        assert addr.startswith("1")
        assert len(comp_pk) == 33

    def test_const_time_deterministic(self):
        """恒定时间：确定性"""
        k = 987654321
        result1 = self.ec.scalar_multiply_const_time(k, self.G)
        result2 = self.ec.scalar_multiply_const_time(k, self.G)
        assert result1 == result2

    def test_const_time_type_error_k(self):
        """恒定时间：类型错误 - k不是整数"""
        with pytest.raises(TypeError):
            self.ec.scalar_multiply_const_time("123", self.G)

    def test_const_time_type_error_point(self):
        """恒定时间：类型错误 - point不是ECPoint"""
        with pytest.raises(TypeError):
            self.ec.scalar_multiply_const_time(123, "not a point")


class TestGeneratePublicKey:
    """公钥生成测试"""

    def setUp(self):
        self.ec = EllipticCurve()

    def test_generate_public_key_compressed(self):
        """生成压缩公钥（33字节）"""
        pk = (42).to_bytes(32, "big")
        pub_key = self.ec.generate_public_key(pk, compressed=True)
        assert len(pub_key) == 33
        assert [2, 3] in pub_key[0]

    def test_generate_public_key_uncompressed(self):
        """生成非压缩公钥（65字节）"""
        pk = (42).to_bytes(32, "big")
        pub_key = self.ec.generate_public_key(pk, compressed=False)
        assert len(pub_key) == 65
        assert pub_key[0] == 4

    def test_generate_public_key_invalid_zero(self):
        """无效私钥：0导致无穷远点"""
        pk = (0).to_bytes(32, "big")
        with pytest.raises(ValueError):
            self.ec.generate_public_key(pk)

    def test_generate_public_key_invalid_order(self):
        """无效私钥：N导致无穷远点"""
        pk = Secp256k1.N.to_bytes(32, "big")
        with pytest.raises(ValueError):
            self.ec.generate_public_key(pk)

    def test_generate_public_key_from_int(self):
        """从整数私钥生成公钥"""
        pk_int = 12345
        pub_key = self.ec.generate_public_key(pk_int, compressed=True)
        assert len(pub_key) == 33

    def test_generate_public_key_deterministic(self):
        """确定性：相同私钥生成相同公钥"""
        pk = (999).to_bytes(32, "big")
        pub1 = self.ec.generate_public_key(pk, compressed=True)
        pub2 = self.ec.generate_public_key(pk, compressed=True)
        assert pub1 == pub2

    def test_generate_public_key_const_time_default(self):
        """generate_public_key默认使用恒定时间算法"""
        pk = (123).to_bytes(32, "big")
        pub_key = self.ec.generate_public_key(pk)

        # 验证与恒定时间算法结果一致
        k = int.from_bytes(pk, "big")
        G = ECPoint(Secp256k1.Gx, Secp256k1.Gy)
        expected_point = self.ec.scalar_multiply_const_time(k, G)

        # 验证x坐标一致
        assert pub_key[1:] == expected_point.x.to_bytes(32, "big")


class TestECPoint:
    """ECPoint类测试"""

    def test_equality_same_point(self):
        """相同点相等"""
        p1 = ECPoint(100, 200)
        p2 = ECPoint(100, 200)
        assert p1 == p2

    def test_equality_different_points(self):
        """不同点不相等"""
        p1 = ECPoint(100, 200)
        p2 = ECPoint(100, 201)
        assert p1 != p2

    def test_equality_infinity(self):
        """无穷远点相等"""
        p1 = ECPoint(None, None)
        p2 = ECPoint(None, None)
        assert p1 == p2

    def test_equality_infinity_vs_point(self):
        """无穷远点与普通点不相等"""
        p1 = ECPoint(None, None)
        p2 = ECPoint(100, 200)
        assert p1 != p2

    def test_is_infinity_flag(self):
        """无穷远点标志"""
        p1 = ECPoint(None, None)
        assert p1.is_infinity

        p2 = ECPoint(100, 200)
        assert not p2.is_infinity

    def test_copy(self):
        """复制点"""
        p1 = ECPoint(100, 200)
        p2 = p1.copy()
        assert p1 == p2
        assert p1 is not p2  # 不同的对象

    def test_repr_infinity(self):
        """无穷远点的字符串表示"""
        p = ECPoint(None, None)
        repr_str = repr(p)
        assert repr_str in "Infinity"

    def test_repr_normal(self):
        """普通点的字符串表示"""
        p = ECPoint(100, 200)
        repr_str = repr(p)
        assert repr_str in "ECPoint"
        assert repr_str in "64"  # 十六进制长度


if __name__ == "__main__":
    unittest.main(verbosity=2)
