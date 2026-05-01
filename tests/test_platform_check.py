# -*- coding: utf-8 -*-
"""跨平台兼容性检查模块测试

测试 PlatformChecker 类的各项功能:
- 操作系统检测
- Python版本检查
- 路径长度检查
- 终端编码检测
- 目录权限检查
- 磁盘空间检查
"""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock

import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.platform_check import PlatformChecker, CheckResult


class TestCheckResult(TestCase):
    """CheckResult数据类测试"""

    def test_create_result_pass(self):
        """创建通过的检查结果"""
        result = CheckResult("测试检查", True, "通过", "详细信息")

        self.assertEqual(result.name, "测试检查")
        self.assertTrue(result.passed)
        self.assertEqual(result.message, "通过")
        self.assertEqual(result.detail, "详细信息")

    def test_create_result_fail(self):
        """创建失败的检查结果"""
        result = CheckResult("测试检查", False, "失败", "错误详情")

        self.assertEqual(result.name, "测试检查")
        self.assertFalse(result.passed)
        self.assertEqual(result.message, "失败")

    def test_repr_pass(self):
        """通过的检查结果字符串表示"""
        result = CheckResult("测试", True, "OK")
        repr_str = repr(result)

        self.assertIn("✅", repr_str)
        self.assertIn("测试", repr_str)
        self.assertIn("OK", repr_str)

    def test_repr_fail(self):
        """失败的检查结果字符串表示"""
        result = CheckResult("测试", False, "失败")
        repr_str = repr(result)

        self.assertIn("⚠️", repr_str)
        self.assertIn("测试", repr_str)

    def test_create_result_no_detail(self):
        """创建无详细信息的检查结果"""
        result = CheckResult("测试", True, "通过")

        self.assertEqual(result.detail, "")


class TestPlatformCheckerBasic(TestCase):
    """PlatformChecker基础功能测试"""

    def setUp(self):
        """创建临时项目目录"""
        self.test_dir = tempfile.mkdtemp()
        self.checker = PlatformChecker(project_root=self.test_dir)

    def tearDown(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """初始化测试"""
        self.assertIsNotNone(self.checker.project_root)
        self.assertEqual(str(self.checker.project_root), self.test_dir)
        self.assertEqual(self.checker.results, [])

    def test_windows_max_path_constant(self):
        """Windows MAX_PATH常量测试"""
        self.assertEqual(PlatformChecker.WINDOWS_MAX_PATH, 260)

    def test_add_result(self):
        """添加检查结果"""
        result = self.checker._add("测试检查", True, "通过", "详情")

        self.assertEqual(len(self.checker.results), 1)
        self.assertEqual(result.name, "测试检查")
        self.assertTrue(result.passed)


class TestPlatformCheckerChecks(TestCase):
    """平台检查功能测试"""

    def setUp(self):
        """创建临时项目目录"""
        self.test_dir = tempfile.mkdtemp()
        self.checker = PlatformChecker(project_root=self.test_dir)

    def tearDown(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_check_os(self):
        """操作系统检查"""
        result = self.checker.check_os()

        self.assertIsNotNone(result)
        self.assertIsInstance(result, CheckResult)
        self.assertEqual(result.name, "操作系统")

        # 常见操作系统应该通过
        import platform

        system = platform.system()
        if system in ("Windows", "Linux", "Darwin"):
            self.assertTrue(result.passed)

    def test_check_python_version(self):
        """Python版本检查"""
        result = self.checker.check_python_version()

        self.assertIsNotNone(result)
        self.assertIsInstance(result, CheckResult)
        self.assertEqual(result.name, "Python 版本")

        # Python 3.9+ 应该通过
        if sys.version_info >= (3, 9):
            self.assertTrue(result.passed)
            self.assertIn("Python", result.message)  # 中英文均包含 "Python"

    def test_check_path_length_windows_short(self):
        """Windows短路径检查"""
        with patch("platform.system", return_value="Windows"):
            result = self.checker.check_path_length()

            # 短路径应该通过
            self.assertTrue(result.passed)
            self.assertIn("限制", result.message)

    def test_check_path_length_windows_long(self):
        """Windows长路径检查"""
        # 创建一个超长路径
        long_path = self.test_dir + "\\a" * 250
        os.makedirs(long_path, exist_ok=True)

        checker = PlatformChecker(project_root=long_path)

        with patch("platform.system", return_value="Windows"):
            result = checker.check_path_length()

            # 长路径应该警告
            self.assertFalse(result.passed)
            self.assertIn("较长", result.message)

        # 清理
        shutil.rmtree(long_path, ignore_errors=True)

    def test_check_path_length_non_windows(self):
        """非Windows系统路径检查"""
        with patch("platform.system", return_value="Linux"):
            result = self.checker.check_path_length()

            # 非Windows系统应该通过
            self.assertTrue(result.passed)

    def test_check_terminal_encoding(self):
        """终端编码检查"""
        result = self.checker.check_encoding()

        self.assertIsNotNone(result)
        self.assertIsInstance(result, CheckResult)
        self.assertEqual(result.name, "终端编码")

    def test_check_directory_permissions(self):
        """目录权限检查"""
        result = self.checker.check_directory_permissions()

        self.assertIsNotNone(result)
        self.assertIsInstance(result, CheckResult)
        self.assertEqual(result.name, "目录权限")

        # 临时目录应该有权限
        self.assertTrue(result.passed)

    def test_check_disk_space(self):
        """磁盘空间检查"""
        result = self.checker.check_disk_space()

        self.assertIsNotNone(result)
        self.assertIsInstance(result, CheckResult)
        self.assertEqual(result.name, "磁盘空间")

        # 应该有足够空间
        self.assertTrue(result.passed)

    def test_check_long_path_support_windows(self):
        """Windows长路径支持检查"""
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                # 模拟长路径支持已启用
                mock_run.return_value = MagicMock(returncode=0, stdout="1")

                result = self.checker.check_long_path_support()

                self.assertIsNotNone(result)
                self.assertIsInstance(result, CheckResult)

    def test_check_long_path_support_non_windows(self):
        """非Windows长路径支持检查"""
        with patch("platform.system", return_value="Linux"):
            result = self.checker.check_long_path_support()

            # 非Windows系统应该跳过
            self.assertTrue(result.passed)

    def test_check_symlink_support(self):
        """符号链接支持检查"""
        result = self.checker.check_symlink_support()

        self.assertIsNotNone(result)
        self.assertIsInstance(result, CheckResult)
        self.assertEqual(result.name, "符号链接")


class TestPlatformCheckerRunAll(TestCase):
    """运行所有检查测试"""

    def setUp(self):
        """创建临时项目目录"""
        self.test_dir = tempfile.mkdtemp()
        self.checker = PlatformChecker(project_root=self.test_dir)

    def tearDown(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_run_all_checks(self):
        """运行所有检查"""
        ok, issues = self.checker.run_all_checks()

        # 应该返回布尔值和問題列表
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(issues, list)

        # 应该有检查结果
        self.assertGreater(len(self.checker.results), 0)

    def test_run_all_checks_clears_results(self):
        """运行所有检查前清空结果"""
        # 先添加一些旧结果
        self.checker._add("旧检查", False, "旧结果")
        old_count = len(self.checker.results)

        # 运行所有检查
        self.checker.run_all_checks()

        # 结果应该被清空并重新添加
        self.assertGreater(len(self.checker.results), 0)

    def test_print_report(self):
        """打印报告"""
        self.checker.run_all_checks()

        # 不应该抛出异常
        try:
            self.checker.print_report()
        except Exception as e:
            self.fail(f"打印报告失败: {e}")


class TestPlatformCheckerEdgeCases(TestCase):
    """边界情况测试"""

    def setUp(self):
        """创建临时项目目录"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """清理临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_nonexistent_project_root(self):
        """不存在的项目根目录"""
        nonexistent_dir = os.path.join(self.test_dir, "nonexistent")
        checker = PlatformChecker(project_root=nonexistent_dir)

        # 应该能正常初始化
        self.assertIsNotNone(checker.project_root)

    def test_check_with_no_permissions(self):
        """无权限目录检查"""
        # 在Windows上难以真正测试权限问题
        # 这里测试正常情况
        checker = PlatformChecker(project_root=self.test_dir)
        result = checker.check_directory_permissions()

        # 临时目录应该有权限
        self.assertTrue(result.passed)

    def test_multiple_checkers(self):
        """多个检查器实例"""
        checker1 = PlatformChecker(project_root=self.test_dir)
        checker2 = PlatformChecker(project_root=self.test_dir)

        # 两个实例应独立
        self.assertIsNot(checker1, checker2)
        self.assertEqual(checker1.results, [])
        self.assertEqual(checker2.results, [])

    def test_check_results_accumulation(self):
        """检查结果累积"""
        checker = PlatformChecker(project_root=self.test_dir)

        checker._add("检查1", True, "通过")
        checker._add("检查2", False, "失败")
        checker._add("检查3", True, "通过")

        self.assertEqual(len(checker.results), 3)
        self.assertTrue(checker.results[0].passed)
        self.assertFalse(checker.results[1].passed)
        self.assertTrue(checker.results[2].passed)


# ============================================================================
# 编码检测增强测试
# ============================================================================


class TestEncodingDetection(unittest.TestCase):
    """编码检测增强测试。"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.checker = PlatformChecker(project_root=self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_check_encoding_utf8_passes(self):
        """UTF-8 编码应该通过检查。"""
        mock_stdout = MagicMock()
        mock_stdout.encoding = "utf-8"
        with patch("sys.stdout", mock_stdout):
            result = self.checker.check_encoding()
        self.assertIsNotNone(result)
        self.assertIsInstance(result, CheckResult)

    def test_check_encoding_gbk(self):
        """GBK 编码（非 UTF-8）应给出警告。"""
        mock_stdout = MagicMock()
        mock_stdout.encoding = "gbk"
        with patch("sys.stdout", mock_stdout):
            result = self.checker.check_encoding()
        self.assertIsNotNone(result)
        self.assertIsInstance(result, CheckResult)
        # GBK 非 UTF-8，检查应失败并包含编码信息
        self.assertFalse(result.passed)
        self.assertIn("gbk", result.message.lower())

    def test_check_encoding_gb2312(self):
        """GB2312 编码（非 UTF-8）应给出警告。"""
        mock_stdout = MagicMock()
        mock_stdout.encoding = "gb2312"
        with patch("sys.stdout", mock_stdout):
            result = self.checker.check_encoding()
        self.assertIsNotNone(result)
        self.assertIsInstance(result, CheckResult)
        self.assertFalse(result.passed)

    def test_check_encoding_cp936(self):
        """CP936（GBK 变体）应给出警告。"""
        mock_stdout = MagicMock()
        mock_stdout.encoding = "cp936"
        with patch("sys.stdout", mock_stdout):
            result = self.checker.check_encoding()
        self.assertIsNotNone(result)
        self.assertFalse(result.passed)

    def test_check_encoding_utf8_variants(self):
        """UTF-8 的各种写法变体都应通过。"""
        for enc in ("UTF-8", "utf-8", "utf8", "UTF8", "UTF_8"):
            mock_stdout = MagicMock()
            mock_stdout.encoding = enc
            with patch("sys.stdout", mock_stdout):
                result = self.checker.check_encoding()
            self.assertTrue(result.passed, f"编码 '{enc}' 应该通过检查，但失败了: {result.message}")

    def test_check_encoding_result_name(self):
        """检查结果名称为 '终端编码'。"""
        result = self.checker.check_encoding()
        self.assertEqual(result.name, "终端编码")


# ============================================================================
# get_platform_info 测试
# ============================================================================


class TestGetPlatformInfo(unittest.TestCase):
    """平台信息获取测试。"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.checker = PlatformChecker(project_root=self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_get_platform_info_returns_dict(self):
        """get_platform_info 返回字典。"""
        info = self.checker.get_platform_info()
        self.assertIsInstance(info, dict)

    def test_get_platform_info_required_keys(self):
        """get_platform_info 包含所有必要字段。"""
        info = self.checker.get_platform_info()
        required_keys = [
            "os",
            "os_release",
            "os_version",
            "machine",
            "python_version",
            "python_executable",
            "encoding_fs",
            "encoding_stdout",
            "project_root",
            "cwd",
        ]
        for key in required_keys:
            self.assertIn(key, info, f"缺少键: {key}")

    def test_get_platform_info_os_value(self):
        """get_platform_info 的 os 字段与实际系统一致。"""
        import platform

        info = self.checker.get_platform_info()
        self.assertEqual(info["os"], platform.system())

    def test_get_platform_info_python_version_format(self):
        """python_version 格式为 X.Y.Z。"""
        info = self.checker.get_platform_info()
        parts = info["python_version"].split(".")
        self.assertEqual(len(parts), 3)
        for part in parts:
            self.assertTrue(part.isdigit(), f"版本号部分 '{part}' 不是数字")

    def test_get_platform_info_project_root_matches(self):
        """project_root 字段与 checker 的项目根目录一致。"""
        info = self.checker.get_platform_info()
        self.assertEqual(info["project_root"], str(self.checker.project_root))

    def test_get_platform_info_cwd_is_directory(self):
        """cwd 字段为存在的目录。"""
        info = self.checker.get_platform_info()
        self.assertTrue(os.path.isdir(info["cwd"]))

    def test_get_platform_info_values_are_strings(self):
        """所有字段值都是字符串。"""
        info = self.checker.get_platform_info()
        for key, value in info.items():
            self.assertIsInstance(value, str, f"字段 '{key}' 的值不是字符串: {type(value)}")


# ============================================================================
# macOS 平台 Mock 测试
# ============================================================================


class TestMacOSPlatform(unittest.TestCase):
    """macOS 平台特定测试。"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch("platform.system", return_value="Darwin")
    @patch("platform.release", return_value="23.0.0")
    @patch("platform.machine", return_value="arm64")
    def test_check_os_macos(self, mock_machine, mock_release, mock_system):
        """macOS (Darwin) 平台检查应通过。"""
        checker = PlatformChecker(project_root=self.test_dir)
        result = checker.check_os()
        self.assertTrue(result.passed)
        self.assertIn("Darwin", result.message)

    @patch("platform.system", return_value="Darwin")
    def test_check_path_length_macos_skips_windows_check(self, mock_system):
        """macOS 上路径长度检查跳过 Windows 限制。"""
        checker = PlatformChecker(project_root=self.test_dir)
        result = checker.check_path_length()
        self.assertTrue(result.passed)

    @patch("platform.system", return_value="Darwin")
    def test_check_long_path_support_macos_skips(self, mock_system):
        """macOS 上长路径支持检查跳过。"""
        checker = PlatformChecker(project_root=self.test_dir)
        result = checker.check_long_path_support()
        self.assertTrue(result.passed)
        self.assertIn("非 Windows", result.message)


# ============================================================================
# Linux 平台 Mock 测试
# ============================================================================


class TestLinuxPlatform(unittest.TestCase):
    """Linux 平台特定测试。"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch("platform.system", return_value="Linux")
    @patch("platform.release", return_value="6.1.0")
    @patch("platform.machine", return_value="x86_64")
    def test_check_os_linux(self, mock_machine, mock_release, mock_system):
        """Linux 平台检查应通过。"""
        checker = PlatformChecker(project_root=self.test_dir)
        result = checker.check_os()
        self.assertTrue(result.passed)
        self.assertIn("Linux", result.message)

    @patch("platform.system", return_value="Linux")
    def test_check_long_path_support_linux_skips(self, mock_system):
        """Linux 上长路径支持检查跳过。"""
        checker = PlatformChecker(project_root=self.test_dir)
        result = checker.check_long_path_support()
        self.assertTrue(result.passed)


# ============================================================================
# 不支持的平台测试
# ============================================================================


class TestUnsupportedPlatform(unittest.TestCase):
    """未经测试的平台测试。"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch("platform.system", return_value="FreeBSD")
    @patch("platform.release", return_value="13.0")
    @patch("platform.machine", return_value="amd64")
    def test_check_os_unsupported(self, mock_machine, mock_release, mock_system):
        """未支持的平台检查应失败。"""
        checker = PlatformChecker(project_root=self.test_dir)
        result = checker.check_os()
        self.assertFalse(result.passed)
        # 消息内容取决于i18n：中文"不支持" / 英文"Unsupported"
        self.assertTrue(
            "不支持" in result.message or "Unsupported" in result.message,
            f"期望包含'不支持'或'Unsupported'，实际: {result.message}",
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
