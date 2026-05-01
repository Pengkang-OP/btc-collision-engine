"""GPU驱动管理器单元测试"""

import unittest
from unittest.mock import patch, Mock
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.gpu.driver_manager import DriverManager, DriverVersionParser  # noqa: E402


class TestDriverVersionParser(unittest.TestCase):
    """测试驱动版本解析器"""

    def test_parse_simple_version(self):
        """测试简单版本号解析"""
        self.assertEqual(DriverVersionParser.parse_version("520.67"), (520, 67))
        self.assertEqual(DriverVersionParser.parse_version("450.00"), (450, 0))

    def test_parse_complex_version(self):
        """测试复杂版本号解析"""
        self.assertEqual(DriverVersionParser.parse_version("31.0.101.4500"), (31, 0, 101, 4500))

    def test_parse_with_suffix(self):
        """测试带后缀的版本号"""
        self.assertEqual(DriverVersionParser.parse_version("520.67.03-beta"), (520, 67, 3))

    def test_parse_empty(self):
        """测试空版本号"""
        self.assertEqual(DriverVersionParser.parse_version(""), (0,))
        self.assertEqual(DriverVersionParser.parse_version(None), (0,))

    def test_compare_versions(self):
        """测试版本比较"""
        # 大于
        self.assertEqual(DriverVersionParser.compare_versions("520.00", "510.00"), 1)
        # 等于
        self.assertEqual(DriverVersionParser.compare_versions("520.67", "520.67"), 0)
        # 小于
        self.assertEqual(DriverVersionParser.compare_versions("510.00", "520.00"), -1)

    def test_compare_different_lengths(self):
        """测试不同长度版本号比较"""
        self.assertEqual(DriverVersionParser.compare_versions("520.67.03", "520.67"), 1)
        self.assertEqual(DriverVersionParser.compare_versions("31.0.101", "31.0.101.4500"), -1)

    def test_is_version_compatible(self):
        """测试版本兼容性检查"""
        self.assertTrue(DriverVersionParser.is_version_compatible("520.00", "510.00"))
        self.assertTrue(DriverVersionParser.is_version_compatible("520.67", "520.67"))
        self.assertFalse(DriverVersionParser.is_version_compatible("500.00", "510.00"))


class TestDriverManager(unittest.TestCase):
    """测试驱动管理器"""

    @patch("src.gpu.driver_manager.platform.system")
    @patch("src.gpu.driver_manager.subprocess.run")
    def test_detect_nvidia_driver(self, mock_run, mock_platform):
        """测试NVIDIA驱动检测"""
        mock_platform.return_value = "Windows"  # Mock平台为Windows

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "520.67.03\n"
        mock_run.return_value = mock_result

        version = DriverManager.detect_nvidia_driver_version()
        self.assertEqual(version, "520.67.03")

    @patch("src.gpu.driver_manager.platform.system")
    @patch("src.gpu.driver_manager.subprocess.run")
    def test_detect_nvidia_driver_not_found(self, mock_run, mock_platform):
        """测试NVIDIA驱动未找到"""
        mock_platform.return_value = "Windows"
        mock_run.side_effect = FileNotFoundError()

        version = DriverManager.detect_nvidia_driver_version()
        self.assertIsNone(version)

    @patch("src.gpu.driver_manager.platform.system")
    @patch("src.gpu.driver_manager.subprocess.run")
    def test_detect_amd_driver(self, mock_run, mock_platform):
        """测试AMD驱动检测"""
        mock_platform.return_value = "Windows"  # Mock平台为Windows

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "23.10.1.0\n"
        mock_run.return_value = mock_result

        version = DriverManager.detect_amd_driver_version()  # 使用公共方法
        self.assertEqual(version, "23.10.1.0")

    def test_detect_driver_by_vendor(self):
        """测试根据厂商检测驱动"""
        with patch.object(DriverManager, "detect_nvidia_driver_version") as mock:
            mock.return_value = "520.67"
            version = DriverManager.detect_driver_version("NVIDIA Corporation")
            self.assertEqual(version, "520.67")

    def test_check_driver_health_good(self):
        """测试驱动健康检查 - 正常"""
        result = DriverManager.check_driver_health(
            "NVIDIA",
            "520.67",
            {"min_driver_version": "450.00", "recommended_driver_version": "520.00"},
        )

        self.assertEqual(result["status"], "good")
        self.assertEqual(len(result["recommendations"]), 0)

    def test_check_driver_health_warning(self):
        """测试驱动健康检查 - 警告"""
        result = DriverManager.check_driver_health(
            "NVIDIA",
            "510.00",
            {"min_driver_version": "450.00", "recommended_driver_version": "520.00"},
        )

        self.assertEqual(result["status"], "warning")
        self.assertIn("推荐", result["message"])

    def test_check_driver_health_critical(self):
        """测试驱动健康检查 - 严重"""
        result = DriverManager.check_driver_health(
            "NVIDIA",
            "400.00",
            {"min_driver_version": "450.00", "recommended_driver_version": "520.00"},
        )

        self.assertEqual(result["status"], "critical")
        self.assertIn("最低要求", result["message"])

    def test_check_driver_health_unstable(self):
        """测试驱动健康检查 - 不稳定版本"""
        result = DriverManager.check_driver_health("NVIDIA", "450.50", None)  # 在不稳定范围内

        self.assertEqual(result["status"], "warning")
        self.assertIn("不稳定", result["message"])

    def test_check_driver_health_no_version(self):
        """测试驱动健康检查 - 无法检测版本"""
        result = DriverManager.check_driver_health("NVIDIA", None, None)

        self.assertEqual(result["status"], "warning")
        self.assertIn("无法检测", result["message"])

    def test_get_optimization_flags_new_driver(self):
        """测试新驱动的优化标志"""
        flags = DriverManager.get_driver_optimization_flags("NVIDIA", "520.67", {})

        self.assertTrue(flags["enable_async_compute"])
        self.assertTrue(flags["enable_fast_math"])
        self.assertTrue(flags["enable_shader_cache"])
        self.assertFalse(flags["conservative_mode"])

    def test_get_optimization_flags_old_driver(self):
        """测试旧驱动的优化标志"""
        flags = DriverManager.get_driver_optimization_flags("NVIDIA", "460.00", {})  # 旧于470.00

        self.assertFalse(flags["enable_async_compute"])
        self.assertTrue(flags["conservative_mode"])

    def test_get_optimization_flags_no_version(self):
        """测试无版本信息的优化标志"""
        flags = DriverManager.get_driver_optimization_flags("NVIDIA", None, {})

        self.assertTrue(flags["conservative_mode"])

    def test_get_optimization_flags_amd(self):
        """测试AMD驱动优化标志"""
        # 新驱动
        flags = DriverManager.get_driver_optimization_flags("AMD", "23.10.1", {})
        self.assertTrue(flags["enable_fast_math"])

        # 旧驱动
        flags = DriverManager.get_driver_optimization_flags("AMD", "22.5.1", {})  # 旧于22.10.0
        self.assertFalse(flags["enable_fast_math"])

    def test_get_optimization_flags_intel(self):
        """测试Intel驱动优化标志"""
        # 新驱动
        flags = DriverManager.get_driver_optimization_flags("Intel", "31.0.101.4500", {})
        self.assertFalse(flags["conservative_mode"])

        # 旧驱动
        flags = DriverManager.get_driver_optimization_flags(
            "Intel", "31.0.100.9000", {}  # 旧于31.0.101.0
        )
        self.assertTrue(flags["conservative_mode"])
        self.assertFalse(flags["enable_async_compute"])


class TestDriverVersionEdgeCases(unittest.TestCase):
    """测试驱动版本边界情况"""

    def test_parse_malformed_version(self):
        """测试畸形版本号"""
        result = DriverVersionParser.parse_version("abc.def")
        self.assertEqual(result, (0,))

    def test_compare_with_build_number(self):
        """测试带编译号的版本比较"""
        self.assertEqual(DriverVersionParser.compare_versions("31.0.101.4500", "31.0.101.4600"), -1)

    def test_health_check_intel_arc(self):
        """测试Intel Arc特殊建议"""
        result = DriverManager.check_driver_health("Intel", "31.0.101.4500", {})

        # 应该包含Arc驱动更新频繁的建议
        self.assertTrue(any("Arc" in rec for rec in result["recommendations"]))

    def test_parse_zero_version(self):
        """测试零版本号"""
        result = DriverVersionParser.parse_version("0.0.0.0")
        self.assertEqual(result, (0, 0, 0, 0))

    def test_health_check_multiple_issues(self):
        """测试健康检查多个问题同时存在"""
        # 不稳定版本 + 低于最低要求
        result = DriverManager.check_driver_health(
            "NVIDIA",
            "450.50",  # 在不稳定范围内
            {"min_driver_version": "460.00", "recommended_driver_version": "520.00"},
        )

        # 应该标记为critical(最低要求不满足优先)
        self.assertEqual(result["status"], "critical")

    def test_optimization_flags_conservative_default(self):
        """测试优化标志默认保守模式"""
        flags = DriverManager.get_driver_optimization_flags("NVIDIA", None, {})  # 无版本信息

        # 默认应该是保守模式
        self.assertTrue(flags["conservative_mode"])
        self.assertFalse(flags["enable_async_compute"])
        self.assertFalse(flags["enable_shader_cache"])

    def test_optimization_flags_nvidia_modern(self):
        """测试NVIDIA现代驱动优化标志"""
        flags = DriverManager.get_driver_optimization_flags("NVIDIA", "520.67", {})  # 现代驱动

        self.assertTrue(flags["enable_async_compute"])
        self.assertTrue(flags["enable_shader_cache"])
        self.assertTrue(flags["enable_shader_reordering"])
        self.assertFalse(flags["conservative_mode"])

    def test_optimization_flags_amd_modern(self):
        """测试AMD现代驱动优化标志"""
        flags = DriverManager.get_driver_optimization_flags("AMD", "23.10.1", {})  # 现代驱动

        self.assertTrue(flags["enable_async_compute"])
        self.assertTrue(flags["enable_fast_math"])
        self.assertFalse(flags["conservative_mode"])

    def test_optimization_flags_intel_modern(self):
        """测试Intel现代驱动优化标志"""
        flags = DriverManager.get_driver_optimization_flags(
            "Intel", "31.0.101.4500", {}  # 现代驱动
        )

        self.assertTrue(flags["enable_async_compute"])
        self.assertFalse(flags["conservative_mode"])

    def test_detection_timeout_config(self):
        """测试检测超时配置"""
        self.assertTrue(hasattr(DriverManager, "DETECTION_TIMEOUT"))
        self.assertIsInstance(DriverManager.DETECTION_TIMEOUT, (int, float))
        self.assertGreater(DriverManager.DETECTION_TIMEOUT, 0)


class TestDriverCache(unittest.TestCase):
    """测试驱动缓存机制"""

    def setUp(self):
        """清除缓存"""
        DriverManager.clear_driver_cache()

    def tearDown(self):
        """清除缓存"""
        DriverManager.clear_driver_cache()

    @patch("src.gpu.driver_manager.platform.system")
    @patch("src.gpu.driver_manager.subprocess.run")
    def test_driver_version_caching(self, mock_run, mock_platform):
        """测试驱动版本缓存"""
        mock_platform.return_value = "Windows"
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "520.67.03\n"
        mock_run.return_value = mock_result

        # 第一次调用 - 应该执行检测
        version1 = DriverManager.detect_driver_version("NVIDIA")
        self.assertEqual(version1, "520.67.03")
        self.assertEqual(mock_run.call_count, 1)

        # 第二次调用 - 应该使用缓存
        version2 = DriverManager.detect_driver_version("NVIDIA")
        self.assertEqual(version2, "520.67.03")
        self.assertEqual(mock_run.call_count, 1)  # 不应该增加

    @patch("src.gpu.driver_manager.platform.system")
    @patch("src.gpu.driver_manager.subprocess.run")
    def test_driver_cache_ttl(self, mock_run, mock_platform):
        """测试缓存过期机制"""

        mock_platform.return_value = "Windows"
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "520.67.03\n"
        mock_run.return_value = mock_result

        # 第一次检测
        version1 = DriverManager.detect_driver_version("NVIDIA")
        self.assertEqual(version1, "520.67.03")

        # 修改缓存时间使其过期
        vendor_key = "nvidia"
        if vendor_key in DriverManager._driver_version_cache:
            old_version, old_time = DriverManager._driver_version_cache[vendor_key]
            # 设置时间为TTL之前
            DriverManager._driver_version_cache[vendor_key] = (
                old_version,
                old_time - DriverManager._cache_ttl - 1,
            )

        # 再次调用 - 应该重新检测
        version2 = DriverManager.detect_driver_version("NVIDIA")
        self.assertEqual(version2, "520.67.03")
        self.assertEqual(mock_run.call_count, 2)  # 应该增加

    def test_clear_driver_cache(self):
        """测试清除缓存"""
        # 添加一些缓存数据
        DriverManager._driver_version_cache["nvidia"] = ("520.67.03", 1000)

        # 清除缓存
        DriverManager.clear_driver_cache()

        # 验证缓存已清空
        self.assertEqual(len(DriverManager._driver_version_cache), 0)


class TestUnstableDriverBlacklist(unittest.TestCase):
    """测试不稳定驱动黑名单"""

    def test_unstable_driver_report(self):
        """测试获取不稳定驱动报告"""
        report = DriverManager.get_unstable_driver_report()

        self.assertIn("last_updated", report)
        self.assertIn("total_unstable_versions", report)
        self.assertIn("vendors", report)
        self.assertIn("recommendations", report)

        self.assertEqual(report["last_updated"], "2026-04-20")
        self.assertGreater(report["total_unstable_versions"], 0)
        self.assertEqual(len(report["vendors"]), 3)  # nvidia, amd, intel
        self.assertGreater(len(report["recommendations"]), 0)

    def test_add_unstable_driver(self):
        """测试添加不稳定驱动"""
        initial_count = len(DriverManager.UNSTABLE_DRIVERS.get("nvidia", []))

        # 添加新的不稳定驱动
        DriverManager.add_unstable_driver("nvidia", "999.00", "999.99", "测试用不稳定驱动")

        # 验证添加成功
        new_count = len(DriverManager.UNSTABLE_DRIVERS["nvidia"])
        self.assertEqual(new_count, initial_count + 1)

        # 清理
        DriverManager.UNSTABLE_DRIVERS["nvidia"].pop()

    def test_health_check_with_blacklist(self):
        """测试健康检查使用黑名单"""
        # 测试黑名单中的驱动版本
        result = DriverManager.check_driver_health("NVIDIA", "450.50", {})  # 在黑名单中

        self.assertEqual(result["status"], "warning")
        self.assertIn("不稳定", result["message"])


class TestLinuxDriverDetection(unittest.TestCase):
    """测试Linux平台驱动检测(模拟)"""

    @patch("src.gpu.driver_manager.platform.system")
    @patch("src.gpu.driver_manager.subprocess.run")
    def test_nvidia_linux_proc_detection(self, mock_run, mock_platform):
        """测试Linux NVIDIA驱动检测(/proc方式)"""
        mock_platform.return_value = "Linux"

        # 第一次调用nvidia-smi失败,第二次/proc成功
        mock_run.side_effect = [
            FileNotFoundError(),  # nvidia-smi不可用
            Mock(
                returncode=0,
                stdout="NVRM version: NVIDIA UNIX x86_64 Kernel Module  520.67.03  ...",
            ),
        ]

        version = DriverManager.detect_nvidia_driver_version()
        self.assertEqual(version, "520.67.03")
        self.assertEqual(mock_run.call_count, 2)  # 尝试了两次

    @patch("src.gpu.driver_manager.platform.system")
    @patch("src.gpu.driver_manager.subprocess.run")
    def test_amd_linux_sysfs_detection(self, mock_run, mock_platform):
        """测试Linux AMD驱动检测(/sys方式)"""
        mock_platform.return_value = "Linux"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "6.2.0"
        mock_run.return_value = mock_result

        version = DriverManager._detect_amd_linux()
        self.assertEqual(version, "6.2.0")
        # 应该调用cat /sys/module/amdgpu/version
        self.assertIn("/sys/module/amdgpu/version", str(mock_run.call_args))

    @patch("src.gpu.driver_manager.platform.system")
    @patch("src.gpu.driver_manager.subprocess.run")
    def test_intel_linux_detection(self, mock_run, mock_platform):
        """测试Linux Intel驱动检测"""
        mock_platform.return_value = "Linux"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "2023.12.12"
        mock_run.return_value = mock_result

        version = DriverManager._detect_intel_linux()
        self.assertEqual(version, "2023.12.12")


if __name__ == "__main__":
    unittest.main()
