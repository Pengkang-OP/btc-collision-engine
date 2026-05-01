#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UTF-8编码支持单元测试

测试Windows控制台UTF-8编码修复的正确性和跨平台兼容性
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestUTF8Helper(unittest.TestCase):
    """UTF-8辅助功能测试"""

    def test_function_exists(self):
        """测试setup_windows_utf8函数存在"""
        from tools.utf8_helper import setup_windows_utf8

        self.assertTrue(callable(setup_windows_utf8), "setup_windows_utf8应该是可调用的")

    def test_module_has_version(self):
        """测试模块有版本信息"""
        from tools import utf8_helper

        self.assertTrue(hasattr(utf8_helper, "__version__"), "模块应该有__version__")
        self.assertTrue(hasattr(utf8_helper, "__author__"), "模块应该有__author__")
        self.assertTrue(hasattr(utf8_helper, "__date__"), "模块应该有__date__")

    def test_module_has_docstring(self):
        """测试模块有文档字符串"""
        from tools import utf8_helper

        self.assertIsNotNone(utf8_helper.__doc__, "模块应该有文档字符串")
        self.assertIn("UTF-8", utf8_helper.__doc__, "文档应该提到UTF-8")

    def test_helper_functions_exist(self):
        """测试所有辅助函数都存在"""
        from tools.utf8_helper import setup_windows_utf8, is_utf8_setup_needed, get_console_encoding

        self.assertTrue(callable(setup_windows_utf8))
        self.assertTrue(callable(is_utf8_setup_needed))
        self.assertTrue(callable(get_console_encoding))


class TestUTF8HelperMock(unittest.TestCase):
    """使用mock的UTF-8测试（不修改真实的stdout）"""

    def test_windows_api_called_on_windows(self):
        """测试Windows平台调用Windows API"""
        from tools import utf8_helper
        import unittest.mock as mock

        with mock.patch.object(utf8_helper.sys, "platform", "win32"):
            with mock.patch.object(
                utf8_helper.ctypes.windll.kernel32, "SetConsoleOutputCP"
            ) as mock_output:
                with mock.patch.object(
                    utf8_helper.ctypes.windll.kernel32, "SetConsoleCP"
                ) as mock_input:
                    with mock.patch.object(utf8_helper.io, "TextIOWrapper"):
                        utf8_helper.setup_windows_utf8()

                        mock_output.assert_called_once_with(65001)
                        mock_input.assert_called_once_with(65001)

    def test_windows_api_not_called_on_linux(self):
        """测试Linux平台不调用Windows API"""
        from tools import utf8_helper
        import unittest.mock as mock

        with mock.patch.object(utf8_helper.sys, "platform", "linux"):
            with mock.patch.object(
                utf8_helper.ctypes.windll.kernel32, "SetConsoleOutputCP"
            ) as mock_output:
                with mock.patch.object(
                    utf8_helper.ctypes.windll.kernel32, "SetConsoleCP"
                ) as mock_input:
                    with mock.patch.object(utf8_helper.io, "TextIOWrapper") as mock_wrapper:
                        utf8_helper.setup_windows_utf8()

                        mock_output.assert_not_called()
                        mock_input.assert_not_called()
                        mock_wrapper.assert_not_called()

    def test_handles_api_failure_gracefully(self):
        """测试API调用失败时不抛出异常并记录日志"""
        from tools import utf8_helper
        import unittest.mock as mock

        with mock.patch.object(utf8_helper.sys, "platform", "win32"):
            with mock.patch.object(
                utf8_helper.ctypes.windll.kernel32,
                "SetConsoleOutputCP",
                side_effect=OSError("Access denied"),
            ):
                with mock.patch.object(utf8_helper.ctypes.windll.kernel32, "SetConsoleCP"):
                    with mock.patch.object(utf8_helper.io, "TextIOWrapper"):
                        with mock.patch.object(utf8_helper.logging, "debug") as mock_log:
                            utf8_helper.setup_windows_utf8()
                            mock_log.assert_called()

    def test_handles_wrapper_failure_gracefully(self):
        """测试TextIOWrapper创建失败时不抛出异常"""
        from tools import utf8_helper
        import unittest.mock as mock

        with mock.patch.object(utf8_helper.sys, "platform", "win32"):
            with mock.patch.object(utf8_helper.ctypes.windll.kernel32, "SetConsoleOutputCP"):
                with mock.patch.object(utf8_helper.ctypes.windll.kernel32, "SetConsoleCP"):
                    with mock.patch.object(
                        utf8_helper.io, "TextIOWrapper", side_effect=OSError("IO Error")
                    ):
                        with mock.patch.object(utf8_helper.logging, "debug") as mock_log:
                            utf8_helper.setup_windows_utf8()
                            mock_log.assert_called()


class TestUTF8HelperAuxiliary(unittest.TestCase):
    """测试辅助函数"""

    def test_is_utf8_setup_needed_returns_true_when_gbk(self):
        """测试GBK编码时需要设置UTF-8"""
        from tools import utf8_helper
        import unittest.mock as mock

        # 创建一个mock stdout对象
        mock_stdout = mock.MagicMock()
        mock_stdout.encoding = "gbk"

        with mock.patch.object(utf8_helper.sys, "platform", "win32"):
            with mock.patch.object(utf8_helper.sys, "stdout", mock_stdout):
                self.assertTrue(utf8_helper.is_utf8_setup_needed())

    def test_is_utf8_setup_needed_returns_false_when_utf8(self):
        """测试UTF-8编码时不需要设置"""
        from tools import utf8_helper
        import unittest.mock as mock

        mock_stdout = mock.MagicMock()
        mock_stdout.encoding = "utf-8"

        with mock.patch.object(utf8_helper.sys, "platform", "win32"):
            with mock.patch.object(utf8_helper.sys, "stdout", mock_stdout):
                self.assertFalse(utf8_helper.is_utf8_setup_needed())

    def test_is_utf8_setup_needed_returns_false_on_linux(self):
        """测试Linux平台不需要设置"""
        from tools import utf8_helper
        import unittest.mock as mock

        with mock.patch.object(utf8_helper.sys, "platform", "linux"):
            self.assertFalse(utf8_helper.is_utf8_setup_needed())

    def test_get_console_encoding_returns_encoding(self):
        """测试获取控制台编码"""
        from tools import utf8_helper
        import unittest.mock as mock

        mock_stdout = mock.MagicMock()
        mock_stdout.encoding = "utf-8"

        with mock.patch.object(utf8_helper.sys, "stdout", mock_stdout):
            self.assertEqual(utf8_helper.get_console_encoding(), "utf-8")

    def test_get_console_encoding_returns_none(self):
        """测试无法获取编码时返回None"""
        from tools import utf8_helper
        import unittest.mock as mock

        # 创建一个没有encoding属性的mock对象
        mock_stdout = mock.MagicMock()
        del mock_stdout.encoding

        with mock.patch.object(utf8_helper.sys, "stdout", mock_stdout):
            self.assertIsNone(utf8_helper.get_console_encoding())


if __name__ == "__main__":
    unittest.main(verbosity=2)
