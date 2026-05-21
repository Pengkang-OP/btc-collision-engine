# -*- coding: utf-8 -*-
"""
P2-1修复: 椭圆曲线弃用警告单元测试

测试scalar_multiply()方法的DeprecationWarning是否正确触发。
"""

import unittest
import warnings
import sys
import os
import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.secp256k1 import Secp256k1, ECPoint, EllipticCurve


@pytest.mark.unit
@pytest.mark.deprecation
@pytest.mark.p2_medium
class TestScalarMultiplyDeprecation(unittest.TestCase):
    """测试标量乘法弃用警告"""

    def setUp(self):
        """测试前准备"""
        self.ec = EllipticCurve()  # 使用EllipticCurve进行运算
        # 创建生成元G点
        self.generator = ECPoint(Secp256k1.Gx, Secp256k1.Gy, Secp256k1)
        self.scalar = 12345

    def test_scalar_multiply_deprecation_warning(self):
        """测试scalar_multiply()触发弃用警告"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # 调用已弃用的方法
            result = self.ec.scalar_multiply(self.scalar, self.generator)

            # 应触发1个警告
            self.assertEqual(len(w), 1)

            # 警告类型应为DeprecationWarning
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))

            # 警告消息应包含关键信息
            warning_message = str(w[0].message)
            self.assertIn("恒定时间", warning_message)
            self.assertIn("scalar_multiply_const_time", warning_message)

            # 验证结果正确性
            self.assertIsInstance(result, ECPoint)
            self.assertFalse(result.is_infinity)

    def test_scalar_multiply_const_time_no_warning(self):
        """测试scalar_multiply_const_time()不触发警告"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # 调用推荐的恒定时间方法
            result = self.ec.scalar_multiply_const_time(self.scalar, self.generator)

            # 不应触发DeprecationWarning
            deprecation_warnings = [
                warning for warning in w if issubclass(warning.category, DeprecationWarning)
            ]
            self.assertEqual(len(deprecation_warnings), 0)

            # 验证结果正确性
            self.assertIsInstance(result, ECPoint)
            self.assertFalse(result.is_infinity)

    def test_both_methods_produce_same_result(self):
        """测试两种方法产生相同结果"""
        # 使用弃用方法
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # 忽略警告
            result_old = self.ec.scalar_multiply(self.scalar, self.generator)

        # 使用恒定时间方法
        result_new = self.ec.scalar_multiply_const_time(self.scalar, self.generator)

        # 结果应相同
        self.assertEqual(result_old.x, result_new.x)
        self.assertEqual(result_old.y, result_new.y)

    def test_deprecation_warning_stacklevel(self):
        """测试警告的stacklevel正确(指向调用者)"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            def wrapper_function():
                return self.ec.scalar_multiply(self.scalar, self.generator)

            wrapper_function()

            # 警告应指向wrapper_function,而非secp256k1.py内部
            self.assertEqual(len(w), 1)
            # filename应包含test文件路径
            self.assertIn("test_p2_1", w[0].filename)

    def test_multiple_calls_multiple_warnings(self):
        """测试多次调用触发多次警告"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # 调用3次
            for _ in range(3):
                self.ec.scalar_multiply(self.scalar, self.generator)

            # 应触发3个警告
            self.assertEqual(len(w), 3)

            # 所有警告都应为DeprecationWarning
            for warning in w:
                self.assertTrue(issubclass(warning.category, DeprecationWarning))

    def test_scalar_multiply_with_zero(self):
        """测试标量为0时的警告"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            result = self.ec.scalar_multiply(0, self.generator)

            # 应触发警告
            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))

            # 结果应为无穷远点
            self.assertTrue(result.is_infinity)

    def test_scalar_multiply_with_infinity_point(self):
        """测试输入点为无穷远点时的警告"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            infinity_point = ECPoint(None, None, Secp256k1)
            result = self.ec.scalar_multiply(self.scalar, infinity_point)

            # 应触发警告
            self.assertEqual(len(w), 1)

            # 结果应为无穷远点
            self.assertTrue(result.is_infinity)

    def test_scalar_multiply_with_large_scalar(self):
        """测试大标量时的警告"""
        large_scalar = 2**256 - 1

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            result = self.ec.scalar_multiply(large_scalar, self.generator)

            # 应触发警告
            self.assertEqual(len(w), 1)

            # 结果应有效
            self.assertFalse(result.is_infinity)


@pytest.mark.unit
@pytest.mark.deprecation
@pytest.mark.p2_medium
class TestBackwardCompatibility(unittest.TestCase):
    """测试向后兼容性"""

    def setUp(self):
        """测试前准备"""
        self.ec = EllipticCurve()
        self.generator = ECPoint(Secp256k1.Gx, Secp256k1.Gy, Secp256k1)

    def test_existing_code_still_works(self):
        """测试现有代码仍可正常工作"""
        # 忽略警告
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            # 原有代码应正常工作
            result = self.ec.scalar_multiply(100, self.generator)

            self.assertIsInstance(result, ECPoint)
            self.assertFalse(result.is_infinity)

    def test_exception_handling_unchanged(self):
        """测试异常处理未改变"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            # 测试类型错误
            with self.assertRaises(TypeError):
                self.ec.scalar_multiply("invalid", self.generator)

            with self.assertRaises(TypeError):
                self.ec.scalar_multiply(100, "invalid")


if __name__ == "__main__":
    unittest.main()
