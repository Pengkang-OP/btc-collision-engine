# -*- coding: utf-8 -*-
"""
P1-3修复: 熵池健康检查单元测试

测试SecureKeyGenerator的熵池检测功能,验证在不同熵池状态下的行为。
"""

import unittest
from unittest.mock import patch, mock_open, MagicMock
import sys
import os
import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.key_generator import SecureKeyGenerator


@pytest.mark.unit
@pytest.mark.entropy
@pytest.mark.p1_high
class TestEntropyHealthCheck(unittest.TestCase):
    """测试熵池健康检查功能"""

    def setUp(self):
        """测试前准备"""
        self.key_gen = SecureKeyGenerator(config={"batch_size": 100})

    def test_low_entropy_linux(self):
        """测试Linux低熵场景(< 1000 bits)"""
        # Mock熵池文件读取
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="500")):
                result = self.key_gen._check_entropy_health()

                # 低熵应返回False
                self.assertFalse(result)

                # 应记录统计
                self.assertEqual(self.key_gen.stats.get("low_entropy_count", 0), 1)

    def test_medium_entropy_linux(self):
        """测试Linux中等熵场景(1000-2000 bits)"""
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="1500")):
                result = self.key_gen._check_entropy_health()

                # 中等熵应返回True
                self.assertTrue(result)

    def test_high_entropy_linux(self):
        """测试Linux高熵场景(> 2000 bits)"""
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="3000")):
                result = self.key_gen._check_entropy_health()

                # 高熵应返回True
                self.assertTrue(result)

    def test_very_high_entropy_linux(self):
        """测试Linux极高熵场景(> 4000 bits)"""
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="4096")):
                result = self.key_gen._check_entropy_health()

                self.assertTrue(result)

    def test_entropy_file_not_exists(self):
        """测试熵池文件不存在场景(Windows/macOS)"""
        with patch("os.path.exists", return_value=False):
            result = self.key_gen._check_entropy_health()

            # 无法检查时应假设健康
            self.assertTrue(result)

    def test_entropy_file_read_error(self):
        """测试熵池文件读取错误"""
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", side_effect=IOError("Permission denied")):
                result = self.key_gen._check_entropy_health()

                # 错误时应假设健康
                self.assertTrue(result)

    def test_entropy_file_invalid_data(self):
        """测试熵池文件数据格式错误"""
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="invalid")):
                result = self.key_gen._check_entropy_health()

                # 解析错误时应假设健康
                self.assertTrue(result)

    def test_generate_batch_with_low_entropy(self):
        """测试低熵环境下生成密钥(应警告但不阻塞)"""
        with patch.object(self.key_gen, "_check_entropy_health", return_value=False):
            with patch("secrets.token_bytes", return_value=b"\x01" * 32):
                # 低熵时应能继续生成
                keys = self.key_gen.generate_batch(5)

                # 应生成5个密钥
                self.assertEqual(len(keys), 5)

    def test_generate_batch_with_high_entropy(self):
        """测试高熵环境下生成密钥"""
        with patch.object(self.key_gen, "_check_entropy_health", return_value=True):
            with patch("secrets.token_bytes", return_value=b"\x01" * 32):
                keys = self.key_gen.generate_batch(5)

                self.assertEqual(len(keys), 5)

    def test_multiple_low_entropy_warnings(self):
        """测试多次低熵警告统计"""
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="800")):
                # 连续检查3次
                self.key_gen._check_entropy_health()
                self.key_gen._check_entropy_health()
                self.key_gen._check_entropy_health()

                # 应累计3次低熵计数
                self.assertEqual(self.key_gen.stats.get("low_entropy_count", 0), 3)

    def test_entropy_boundary_1000(self):
        """测试熵值边界条件(1000)"""
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="1000")):
                result = self.key_gen._check_entropy_health()

                # 1000应该返回True(>= 1000)
                self.assertTrue(result)

    def test_entropy_boundary_999(self):
        """测试熵值边界条件(999)"""
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="999")):
                result = self.key_gen._check_entropy_health()

                # 999应该返回False(< 1000)
                self.assertFalse(result)

    def test_entropy_boundary_2000(self):
        """测试熵值边界条件(2000)"""
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="2000")):
                result = self.key_gen._check_entropy_health()

                self.assertTrue(result)

    def test_entropy_boundary_1999(self):
        """测试熵值边界条件(1999)"""
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="1999")):
                result = self.key_gen._check_entropy_health()

                self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
