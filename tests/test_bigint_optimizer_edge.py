# -*- coding: utf-8 -*-
"""BigIntOptimizer 全覆盖测试 (gmpy2 可用 + 不可用路径)"""

import sys
import unittest
from unittest.mock import patch

from src.core.bigint_optimizer import BigIntOptimizer, get_bigint_optimizer


class TestBigIntOptimizerNoGmpy2(unittest.TestCase):
    """模拟 gmpy2 不可用时, 测试纯 Python 回退路径"""

    @staticmethod
    def _selective_import_fail_for_gmpy2(name, *args, **kwargs):
        if name == "gmpy2":
            raise ImportError("No module named 'gmpy2'")
        return __import__(name, *args, **kwargs)

    def _create_optimizer_no_gmpy2(self):
        """在 gmpy2 不可用环境中创建 BigIntOptimizer"""
        saved = sys.modules.pop("gmpy2", None)
        try:
            with patch("builtins.__import__",
                       side_effect=self._selective_import_fail_for_gmpy2):
                with patch("src.core.bigint_optimizer.logger"):
                    optimizer = BigIntOptimizer()
        finally:
            if saved is not None:
                sys.modules["gmpy2"] = saved
        return optimizer

    def test_init_no_gmpy2(self):
        """gmpy2 不可用时初始化 (cover lines 71-72)"""
        optimizer = self._create_optimizer_no_gmpy2()
        self.assertFalse(optimizer.use_gmpy2)
        self.assertIsNone(optimizer.gmpy2)
        self.assertIsNone(optimizer.mpz)

    def test_mod_inverse_no_gmpy2(self):
        """无 gmpy2 时 mod_inverse 回退 (cover line 97)"""
        optimizer = self._create_optimizer_no_gmpy2()
        result = optimizer.mod_inverse(3, 11)
        self.assertEqual(result, 4)
        self.assertEqual((3 * result) % 11, 1)

    def test_mod_inverse_python_negative_a(self):
        """_mod_inverse_python a<0 分支 (cover line 102)"""
        optimizer = self._create_optimizer_no_gmpy2()
        result = optimizer._mod_inverse_python(-3, 11)
        self.assertEqual(result, 7)  # -3 ≡ 8 (mod 11), inverse of 8 mod 11 = 7

    def test_mod_inverse_python_no_inverse(self):
        """_mod_inverse_python r>1 逆元不存在 (cover line 113)"""
        optimizer = self._create_optimizer_no_gmpy2()
        with self.assertRaises(ValueError) as ctx:
            optimizer._mod_inverse_python(2, 4)
        self.assertIn("模逆元不存在", str(ctx.exception))

    def test_mod_mul_no_gmpy2(self):
        """无 gmpy2 时 mod_mul 回退 (cover line 139)"""
        optimizer = self._create_optimizer_no_gmpy2()
        result = optimizer.mod_mul(10, 20, 1000)
        self.assertEqual(result, 200)

    def test_mod_add_no_gmpy2(self):
        """无 gmpy2 时 mod_add 回退 (cover line 157)"""
        optimizer = self._create_optimizer_no_gmpy2()
        result = optimizer.mod_add(100, 200, 997)
        self.assertEqual(result, 300)

    def test_mod_sub_no_gmpy2(self):
        """无 gmpy2 时 mod_sub 回退 (cover line 175)"""
        optimizer = self._create_optimizer_no_gmpy2()
        result = optimizer.mod_sub(3, 5, 7)
        self.assertEqual(result, 5)  # (3-5) % 7 = -2 % 7 = 5

    def test_mod_pow_no_gmpy2(self):
        """无 gmpy2 时 mod_pow 回退 (cover line 193)"""
        optimizer = self._create_optimizer_no_gmpy2()
        result = optimizer.mod_pow(2, 10, 1000)
        self.assertEqual(result, 24)

    def test_is_optimized_no_gmpy2(self):
        """无 gmpy2 时 is_optimized 返回 False"""
        optimizer = self._create_optimizer_no_gmpy2()
        self.assertFalse(optimizer.is_optimized())

    def test_get_backend_name_no_gmpy2(self):
        """无 gmpy2 时 backend name"""
        optimizer = self._create_optimizer_no_gmpy2()
        self.assertEqual(optimizer.get_backend_name(), "Pure Python")


class TestBigIntOptimizerWithGmpy2(unittest.TestCase):
    """模拟 gmpy2 可用时, 测试 gmpy2 优化路径"""

    def setUp(self):
        """创建 gmpy2 优化器 (真实 gmpy2 路径)"""
        # gmpy2 在当前环境中已安装, 直接创建正常优化器
        self.opt = BigIntOptimizer()
        # 确保 gmpy2 确实可用
        self.assertTrue(self.opt.use_gmpy2, "gmpy2 应在此环境中可用")

    # ---- mod_inverse (lines 89-94) ----

    def test_mod_inverse_with_gmpy2(self):
        """gmpy2 路径 mod_inverse 正常计算 → lines 89-93"""
        result = self.opt.mod_inverse(3, 11)
        self.assertEqual(result, 4)
        self.assertEqual((3 * result) % 11, 1)

    def test_mod_inverse_with_gmpy2_no_inverse(self):
        """gmpy2.invert 抛 ZeroDivisionError → ValueError → line 94"""
        import gmpy2
        with patch.object(gmpy2, "invert", side_effect=ZeroDivisionError("inverse does not exist")):
            with self.assertRaises(ValueError) as ctx:
                self.opt.mod_inverse(2, 4)
            self.assertIn("模逆元不存在", str(ctx.exception))

    # ---- mod_mul (lines 135-137) ----

    def test_mod_mul_with_gmpy2(self):
        """gmpy2 路径模乘法 → lines 135-137"""
        result = self.opt.mod_mul(10, 20, 997)
        self.assertEqual(result, (10 * 20) % 997)

    def test_mod_mul_with_gmpy2_wraparound(self):
        """gmpy2 路径模乘法(大数环绕) → line 137"""
        result = self.opt.mod_mul(10**20, 10**20, 10**8 + 7)
        self.assertEqual(result, (10**20 * 10**20) % (10**8 + 7))

    # ---- mod_add (lines 154-155) ----

    def test_mod_add_with_gmpy2(self):
        """gmpy2 路径模加法 → lines 154-155"""
        result = self.opt.mod_add(500, 600, 997)
        self.assertEqual(result, (500 + 600) % 997)

    # ---- mod_sub (lines 172-173) ----

    def test_mod_sub_with_gmpy2(self):
        """gmpy2 路径模减法 → lines 172-173"""
        result = self.opt.mod_sub(3, 5, 7)
        self.assertEqual(result, (3 - 5) % 7)

    # ---- mod_pow (lines 190-191) ----

    def test_mod_pow_with_gmpy2(self):
        """gmpy2 路径模幂 → lines 190-191"""
        result = self.opt.mod_pow(2, 10, 1000)
        self.assertEqual(result, pow(2, 10, 1000))

    # ---- get_backend_name ----

    def test_get_backend_name_with_gmpy2(self):
        """gmpy2 可用时 backend name"""
        self.assertEqual(self.opt.get_backend_name(), "gmpy2 (Comba乘法)")

    def test_is_optimized_with_gmpy2(self):
        """gmpy2 可用时 is_optimized 返回 True"""
        self.assertTrue(self.opt.is_optimized())


class TestGetBigIntOptimizer(unittest.TestCase):
    """get_bigint_optimizer 函数 → line 210"""

    def test_returns_bigint_optimizer_instance(self):
        """get_bigint_optimizer 返回 BigIntOptimizer 实例"""
        optimizer = get_bigint_optimizer()
        self.assertIsInstance(optimizer, BigIntOptimizer)

    def test_returns_same_instance(self):
        """多次调用返回同一个全局实例"""
        opt1 = get_bigint_optimizer()
        opt2 = get_bigint_optimizer()
        self.assertIs(opt1, opt2)


if __name__ == "__main__":
    unittest.main()
