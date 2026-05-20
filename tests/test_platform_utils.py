"""PlatformUtils 跨平台工具类测试。

覆盖 PlatformUtils 类的所有方法：
- 平台检测 (is_windows/is_macos/is_linux)
- 字体选择 (get_ui_font/get_mono_font)
- DPI 缩放 (get_dpi_scale)
- 屏幕/窗口尺寸 (get_screen_size/get_optimal_window_size)
- 字体缩放 (scale_font_size)
- 完整字体配置 (get_font_config)
- 路径和系统工具 (normalize_path/get_line_ending/get_system_info)
- UTF-8 输出修复 (ensure_utf8_output)
- 目录工具 (get_temp_dir/get_config_dir)
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.platform_utils import PlatformUtils, get_platform_fonts  # noqa: E402

# ============================================================================
# 平台检测测试
# ============================================================================


class TestPlatformDetection(unittest.TestCase):
    """平台检测方法测试。"""

    def setUp(self):
        """保存原始平台值，以便 tearDown 恢复。"""
        self._orig_platform = PlatformUtils._platform

    def tearDown(self):
        """恢复原始平台值，避免污染其他测试。"""
        PlatformUtils._platform = self._orig_platform

    def test_is_windows_true(self):
        """Windows 平台下 is_windows 返回 True。"""
        PlatformUtils._platform = "Windows"
        self.assertTrue(PlatformUtils.is_windows())

    def test_is_windows_false_on_linux(self):
        """Linux 平台下 is_windows 返回 False。"""
        PlatformUtils._platform = "Linux"
        self.assertFalse(PlatformUtils.is_windows())

    def test_is_windows_false_on_darwin(self):
        """macOS 平台下 is_windows 返回 False。"""
        PlatformUtils._platform = "Darwin"
        self.assertFalse(PlatformUtils.is_windows())

    def test_is_macos_true(self):
        """macOS 平台下 is_macos 返回 True。"""
        PlatformUtils._platform = "Darwin"
        self.assertTrue(PlatformUtils.is_macos())

    def test_is_macos_false_on_windows(self):
        """Windows 平台下 is_macos 返回 False。"""
        PlatformUtils._platform = "Windows"
        self.assertFalse(PlatformUtils.is_macos())

    def test_is_linux_true(self):
        """Linux 平台下 is_linux 返回 True。"""
        PlatformUtils._platform = "Linux"
        self.assertTrue(PlatformUtils.is_linux())

    def test_is_linux_false_on_windows(self):
        """Windows 平台下 is_linux 返回 False。"""
        PlatformUtils._platform = "Windows"
        self.assertFalse(PlatformUtils.is_linux())

    def test_get_platform_name(self):
        """get_platform_name 返回类变量 _platform 的值。"""
        PlatformUtils._platform = "Windows"
        self.assertEqual(PlatformUtils.get_platform_name(), "Windows")

    def test_get_platform_name_linux(self):
        """Linux 下 get_platform_name 返回 'Linux'。"""
        PlatformUtils._platform = "Linux"
        self.assertEqual(PlatformUtils.get_platform_name(), "Linux")


# ============================================================================
# 字体选择测试
# ============================================================================


class TestFontSelection(unittest.TestCase):
    """字体选择测试。"""

    def setUp(self):
        self._orig_platform = PlatformUtils._platform

    def tearDown(self):
        PlatformUtils._platform = self._orig_platform

    # --- get_ui_font ---

    def test_get_ui_font_windows(self):
        """Windows 下返回 Microsoft YaHei。"""
        PlatformUtils._platform = "Windows"
        font = PlatformUtils.get_ui_font()
        self.assertEqual(font, "Microsoft YaHei")

    def test_get_ui_font_darwin(self):
        """macOS 下返回 PingFang SC。"""
        PlatformUtils._platform = "Darwin"
        font = PlatformUtils.get_ui_font()
        self.assertEqual(font, "PingFang SC")

    def test_get_ui_font_linux(self):
        """Linux 下返回 Noto Sans CJK SC。"""
        PlatformUtils._platform = "Linux"
        font = PlatformUtils.get_ui_font()
        self.assertEqual(font, "Noto Sans CJK SC")

    def test_get_ui_font_unknown_platform(self):
        """未知平台下返回 Arial（默认值）。"""
        PlatformUtils._platform = "FreeBSD"
        font = PlatformUtils.get_ui_font()
        self.assertEqual(font, "Arial")

    def test_get_ui_font_returns_string(self):
        """get_ui_font 始终返回字符串。"""
        for platform_name in ("Windows", "Darwin", "Linux", "Unknown"):
            PlatformUtils._platform = platform_name
            font = PlatformUtils.get_ui_font()
            self.assertIsInstance(font, str)
            self.assertGreater(len(font), 0)

    # --- get_mono_font ---

    def test_get_mono_font_windows(self):
        """Windows 下返回 Consolas。"""
        PlatformUtils._platform = "Windows"
        font = PlatformUtils.get_mono_font()
        self.assertEqual(font, "Consolas")

    def test_get_mono_font_darwin(self):
        """macOS 下返回 Menlo。"""
        PlatformUtils._platform = "Darwin"
        font = PlatformUtils.get_mono_font()
        self.assertEqual(font, "Menlo")

    def test_get_mono_font_linux(self):
        """Linux 下返回 DejaVu Sans Mono。"""
        PlatformUtils._platform = "Linux"
        font = PlatformUtils.get_mono_font()
        self.assertEqual(font, "DejaVu Sans Mono")

    def test_get_mono_font_unknown_platform(self):
        """未知平台下返回 Courier New（默认值）。"""
        PlatformUtils._platform = "SunOS"
        font = PlatformUtils.get_mono_font()
        self.assertEqual(font, "Courier New")


# ============================================================================
# DPI 缩放测试
# ============================================================================


class TestDPIScale(unittest.TestCase):
    """DPI 缩放测试。"""

    def setUp(self):
        """每次测试前重置 DPI 缓存。"""
        self._orig_dpi_scale = PlatformUtils._dpi_scale
        PlatformUtils._dpi_scale = None

    def tearDown(self):
        """恢复 DPI 缓存。"""
        PlatformUtils._dpi_scale = self._orig_dpi_scale

    def test_dpi_scale_env_override(self):
        """BTC_DPI_SCALE 环境变量覆盖 DPI 检测。"""
        with patch.dict(os.environ, {"BTC_DPI_SCALE": "2.0"}):
            scale = PlatformUtils.get_dpi_scale()
            self.assertEqual(scale, 2.0)

    def test_dpi_scale_env_override_float(self):
        """环境变量支持小数值。"""
        with patch.dict(os.environ, {"BTC_DPI_SCALE": "1.5"}):
            scale = PlatformUtils.get_dpi_scale()
            self.assertEqual(scale, 1.5)

    def test_dpi_scale_env_override_ignores_cache(self):
        """环境变量优先于缓存。"""
        PlatformUtils._dpi_scale = 1.0  # 设置缓存
        with patch.dict(os.environ, {"BTC_DPI_SCALE": "3.0"}):
            scale = PlatformUtils.get_dpi_scale()
            self.assertEqual(scale, 3.0)

    def test_dpi_scale_invalid_env_falls_through(self):
        """无效的环境变量值跳过，继续正常检测流程。"""
        with patch.dict(os.environ, {"BTC_DPI_SCALE": "invalid"}):
            with patch("src.utils.platform_utils.tk.Tk", side_effect=Exception("No display")):
                scale = PlatformUtils.get_dpi_scale()
                # 应回退到 1.0
                self.assertEqual(scale, 1.0)

    def test_dpi_scale_no_gui_fallback(self):
        """tkinter 不可用时回退到 1.0。"""
        env = {k: v for k, v in os.environ.items() if k != "BTC_DPI_SCALE"}
        with patch.dict(os.environ, env, clear=True):
            with patch("src.utils.platform_utils.tk.Tk", side_effect=Exception("No display")):
                PlatformUtils._dpi_scale = None
                scale = PlatformUtils.get_dpi_scale()
                self.assertEqual(scale, 1.0)

    def test_dpi_scale_with_tkinter_150_percent(self):
        """tkinter 正常时：144 DPI = 1.5 缩放比。"""
        mock_root = MagicMock()
        mock_root.winfo_fpixels.return_value = 144.0  # 150% DPI
        env = {k: v for k, v in os.environ.items() if k != "BTC_DPI_SCALE"}
        with patch.dict(os.environ, env, clear=True):
            with patch("src.utils.platform_utils.tk.Tk", return_value=mock_root):
                PlatformUtils._dpi_scale = None
                scale = PlatformUtils.get_dpi_scale()
                self.assertAlmostEqual(scale, 1.5, places=5)

    def test_dpi_scale_with_tkinter_96_dpi(self):
        """tkinter 正常时：96 DPI = 1.0 缩放比。"""
        mock_root = MagicMock()
        mock_root.winfo_fpixels.return_value = 96.0
        env = {k: v for k, v in os.environ.items() if k != "BTC_DPI_SCALE"}
        with patch.dict(os.environ, env, clear=True):
            with patch("src.utils.platform_utils.tk.Tk", return_value=mock_root):
                PlatformUtils._dpi_scale = None
                scale = PlatformUtils.get_dpi_scale()
                self.assertAlmostEqual(scale, 1.0, places=5)

    def test_dpi_scale_cached(self):
        """第二次调用直接返回缓存值。"""
        PlatformUtils._dpi_scale = 2.5
        env = {k: v for k, v in os.environ.items() if k != "BTC_DPI_SCALE"}
        with patch.dict(os.environ, env, clear=True):
            scale = PlatformUtils.get_dpi_scale()
            self.assertEqual(scale, 2.5)

    def test_dpi_scale_with_root_argument(self):
        """传入 root 参数时直接使用该窗口检测 DPI。"""
        mock_root = MagicMock()
        mock_root.winfo_fpixels.return_value = 192.0  # 200% DPI
        env = {k: v for k, v in os.environ.items() if k != "BTC_DPI_SCALE"}
        with patch.dict(os.environ, env, clear=True):
            PlatformUtils._dpi_scale = None
            scale = PlatformUtils.get_dpi_scale(root=mock_root)
            self.assertAlmostEqual(scale, 2.0, places=5)
            # 确保 Tk() 没有被调用（使用了传入的 root）
            mock_root.winfo_fpixels.assert_called_once_with("1i")


# ============================================================================
# 屏幕尺寸测试
# ============================================================================


class TestScreenSize(unittest.TestCase):
    """屏幕尺寸测试。"""

    def test_get_screen_size_fallback_on_error(self):
        """tkinter 不可用时返回默认 1920x1080。"""
        with patch("src.utils.platform_utils.tk.Tk", side_effect=Exception("No display")):
            w, h = PlatformUtils.get_screen_size()
            self.assertEqual(w, 1920)
            self.assertEqual(h, 1080)

    def test_get_screen_size_with_tkinter(self):
        """tkinter 正常时返回屏幕尺寸。"""
        mock_root = MagicMock()
        mock_root.winfo_screenwidth.return_value = 2560
        mock_root.winfo_screenheight.return_value = 1440
        with patch("src.utils.platform_utils.tk.Tk", return_value=mock_root):
            w, h = PlatformUtils.get_screen_size()
            self.assertEqual(w, 2560)
            self.assertEqual(h, 1440)

    def test_get_screen_size_returns_tuple(self):
        """返回值为二元组。"""
        with patch("src.utils.platform_utils.tk.Tk", side_effect=Exception("No display")):
            result = PlatformUtils.get_screen_size()
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 2)

    def test_get_screen_size_with_root_argument(self):
        """传入 root 参数时直接使用。"""
        mock_root = MagicMock()
        mock_root.winfo_screenwidth.return_value = 1280
        mock_root.winfo_screenheight.return_value = 800
        w, h = PlatformUtils.get_screen_size(root=mock_root)
        self.assertEqual(w, 1280)
        self.assertEqual(h, 800)


# ============================================================================
# 窗口尺寸测试
# ============================================================================


class TestWindowSize(unittest.TestCase):
    """窗口尺寸测试。"""

    def test_optimal_window_size_range(self):
        """返回值在约束范围 600-1920 x 900-1200 内。"""
        with patch.object(PlatformUtils, "get_screen_size", return_value=(1920, 1080)):
            width, height = PlatformUtils.get_optimal_window_size()
            self.assertGreaterEqual(width, 600)
            self.assertLessEqual(width, 1920)
            self.assertGreaterEqual(height, 900)
            self.assertLessEqual(height, 1200)

    def test_screen_size_small_clamps_to_min(self):
        """小屏幕下宽度钳制到最小值 600。"""
        with patch.object(PlatformUtils, "get_screen_size", return_value=(700, 500)):
            width, height = PlatformUtils.get_optimal_window_size()
            self.assertEqual(width, 600)  # min_width = 600
            self.assertEqual(height, 900)  # min_height = 900

    def test_screen_size_large_clamps_to_max(self):
        """超大屏幕下宽高不超过最大值 1920x1200。"""
        with patch.object(PlatformUtils, "get_screen_size", return_value=(5120, 2880)):
            width, height = PlatformUtils.get_optimal_window_size()
            self.assertLessEqual(width, 1920)
            self.assertLessEqual(height, 1200)

    def test_optimal_window_size_typical_1080p(self):
        """1920x1080 屏幕的典型窗口尺寸。"""
        with patch.object(PlatformUtils, "get_screen_size", return_value=(1920, 1080)):
            width, height = PlatformUtils.get_optimal_window_size()
            # 75% 宽 = 1440, 80% 高 = 864 → 钳制到 900
            self.assertEqual(width, 1440)
            self.assertEqual(height, 900)

    def test_optimal_window_size_returns_tuple(self):
        """返回值为二元组。"""
        with patch.object(PlatformUtils, "get_screen_size", return_value=(1920, 1080)):
            result = PlatformUtils.get_optimal_window_size()
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 2)

    def test_optimal_window_size_custom_ratio(self):
        """自定义宽高比。"""
        with patch.object(PlatformUtils, "get_screen_size", return_value=(1920, 1080)):
            width, height = PlatformUtils.get_optimal_window_size(width_ratio=0.5, height_ratio=0.9)
            self.assertEqual(width, 960)  # 1920 * 0.5
            self.assertEqual(height, 972)  # 1080 * 0.9


# ============================================================================
# 字体缩放测试
# ============================================================================


class TestScaleFontSize(unittest.TestCase):
    """字体缩放测试。"""

    def setUp(self):
        self._orig_dpi_scale = PlatformUtils._dpi_scale
        PlatformUtils._dpi_scale = None

    def tearDown(self):
        PlatformUtils._dpi_scale = self._orig_dpi_scale

    def test_scale_at_high_dpi(self):
        """DPI >= 1.5 时正确缩放字体大小。"""
        with patch.object(PlatformUtils, "get_dpi_scale", return_value=2.0):
            scaled = PlatformUtils.scale_font_size(10)
            self.assertEqual(scaled, 20)

    def test_scale_at_normal_dpi(self):
        """DPI < 1.5 时不缩放（返回原始大小）。"""
        with patch.object(PlatformUtils, "get_dpi_scale", return_value=1.0):
            scaled = PlatformUtils.scale_font_size(10)
            self.assertEqual(scaled, 10)

    def test_scale_at_boundary_1_5(self):
        """DPI 恰好为 1.5 时触发缩放。"""
        with patch.object(PlatformUtils, "get_dpi_scale", return_value=1.5):
            scaled = PlatformUtils.scale_font_size(10)
            self.assertEqual(scaled, 15)

    def test_scale_at_below_boundary(self):
        """DPI 低于 1.5 时不缩放。"""
        with patch.object(PlatformUtils, "get_dpi_scale", return_value=1.4):
            scaled = PlatformUtils.scale_font_size(12)
            self.assertEqual(scaled, 12)

    def test_scale_returns_int(self):
        """缩放结果始终为整数。"""
        with patch.object(PlatformUtils, "get_dpi_scale", return_value=1.5):
            scaled = PlatformUtils.scale_font_size(7)
            self.assertIsInstance(scaled, int)

    def test_scale_various_sizes(self):
        """不同字体大小的缩放结果。"""
        with patch.object(PlatformUtils, "get_dpi_scale", return_value=2.0):
            self.assertEqual(PlatformUtils.scale_font_size(8), 16)
            self.assertEqual(PlatformUtils.scale_font_size(11), 22)
            self.assertEqual(PlatformUtils.scale_font_size(16), 32)


# ============================================================================
# 完整字体配置测试
# ============================================================================


class TestFontConfig(unittest.TestCase):
    """完整字体配置测试。"""

    def setUp(self):
        self._orig_platform = PlatformUtils._platform
        self._orig_dpi_scale = PlatformUtils._dpi_scale

    def tearDown(self):
        PlatformUtils._platform = self._orig_platform
        PlatformUtils._dpi_scale = self._orig_dpi_scale

    def test_font_config_keys(self):
        """get_font_config 包含所有必要的键。"""
        PlatformUtils._dpi_scale = 1.0
        config = PlatformUtils.get_font_config()
        expected_keys = [
            "title",
            "subtitle",
            "section_title",
            "label",
            "hint",
            "button",
            "button_large",
            "monospace",
            "status_bar",
        ]
        for key in expected_keys:
            self.assertIn(key, config, f"缺少键: {key}")

    def test_font_config_tuple_format(self):
        """每个字体配置值都是至少包含 2 个元素的元组。"""
        PlatformUtils._dpi_scale = 1.0
        config = PlatformUtils.get_font_config()
        for key, value in config.items():
            self.assertIsInstance(value, tuple, f"键 '{key}' 的值不是元组")
            self.assertGreaterEqual(len(value), 2, f"键 '{key}' 的元组长度不足 2")

    def test_font_config_size_positive(self):
        """所有字体大小必须是正整数。"""
        PlatformUtils._dpi_scale = 1.0
        config = PlatformUtils.get_font_config()
        for key, value in config.items():
            size = value[1]
            self.assertIsInstance(size, int, f"键 '{key}' 的字体大小不是整数")
            self.assertGreater(size, 0, f"键 '{key}' 的字体大小必须为正数")

    def test_font_config_windows_fonts(self):
        """Windows 平台字体配置使用 Microsoft YaHei 和 Consolas。"""
        PlatformUtils._platform = "Windows"
        PlatformUtils._dpi_scale = 1.0
        config = PlatformUtils.get_font_config()
        self.assertEqual(config["title"][0], "Microsoft YaHei")
        self.assertEqual(config["monospace"][0], "Consolas")

    def test_font_config_darwin_fonts(self):
        """macOS 平台字体配置使用 PingFang SC 和 Menlo。"""
        PlatformUtils._platform = "Darwin"
        PlatformUtils._dpi_scale = 1.0
        config = PlatformUtils.get_font_config()
        self.assertEqual(config["title"][0], "PingFang SC")
        self.assertEqual(config["monospace"][0], "Menlo")

    def test_font_config_high_dpi_scaling(self):
        """高 DPI 下字体大小正确放大。"""
        PlatformUtils._platform = "Windows"
        PlatformUtils._dpi_scale = 2.0  # 预设缓存，避免 tkinter 调用
        with patch.object(PlatformUtils, "get_dpi_scale", return_value=2.0):
            config = PlatformUtils.get_font_config()
            # title 正常大小 16，2.0 倍缩放 = 32
            self.assertEqual(config["title"][1], 32)

    def test_font_config_normal_dpi_no_scaling(self):
        """正常 DPI 下字体大小不变。"""
        PlatformUtils._platform = "Windows"
        with patch.object(PlatformUtils, "get_dpi_scale", return_value=1.0):
            config = PlatformUtils.get_font_config()
            self.assertEqual(config["title"][1], 16)
            self.assertEqual(config["label"][1], 10)


# ============================================================================
# 路径和系统工具测试
# ============================================================================


class TestPathAndSystem(unittest.TestCase):
    """路径和系统工具测试。"""

    def test_normalize_path_removes_double_slash(self):
        """normalize_path 规范化路径（移除多余分隔符）。"""
        result = PlatformUtils.normalize_path("some/path//to/file")
        self.assertNotIn("//", result)

    def test_normalize_path_no_dotdot(self):
        """normalize_path 解析 .. 路径。"""
        result = PlatformUtils.normalize_path("some/path/../other")
        self.assertNotIn("..", result)

    def test_normalize_path_returns_string(self):
        """normalize_path 返回字符串。"""
        result = PlatformUtils.normalize_path("test/path")
        self.assertIsInstance(result, str)

    def test_normalize_path_absolute(self):
        """normalize_path 保留绝对路径前缀。"""
        abs_path = os.path.abspath("test")
        result = PlatformUtils.normalize_path(abs_path)
        self.assertTrue(os.path.isabs(result))

    def test_get_line_ending(self):
        """get_line_ending 返回有效的换行符。"""
        ending = PlatformUtils.get_line_ending()
        self.assertIn(ending, ["\n", "\r\n", "\r"])

    def test_get_line_ending_matches_os_linesep(self):
        """get_line_ending 与 os.linesep 一致。"""
        self.assertEqual(PlatformUtils.get_line_ending(), os.linesep)

    def test_get_system_info_returns_dict(self):
        """get_system_info 返回字典。"""
        info = PlatformUtils.get_system_info()
        self.assertIsInstance(info, dict)

    def test_get_system_info_required_keys(self):
        """get_system_info 包含所有必要键。"""
        info = PlatformUtils.get_system_info()
        required_keys = ["platform", "platform_version", "machine", "processor", "python_version"]
        for key in required_keys:
            self.assertIn(key, info, f"缺少键: {key}")

    def test_get_system_info_values_non_empty(self):
        """get_system_info 的值不为空（部分字段在某些环境可能为空，只验证 platform）。"""
        info = PlatformUtils.get_system_info()
        self.assertIsInstance(info["platform"], str)
        self.assertIsInstance(info["python_version"], str)
        self.assertGreater(len(info["python_version"]), 0)

    def test_get_system_info_platform_matches(self):
        """get_system_info 中的 platform 与类变量 _platform 一致。"""
        info = PlatformUtils.get_system_info()
        self.assertEqual(info["platform"], PlatformUtils._platform)


# ============================================================================
# UTF-8 输出修复测试
# ============================================================================


class TestEnsureUtf8Output(unittest.TestCase):
    """UTF-8 输出修复测试。"""

    def test_no_op_on_linux(self):
        """Linux 上 ensure_utf8_output 是无操作，不抛异常。"""
        with patch("src.utils.platform_utils.platform.system", return_value="Linux"):
            try:
                PlatformUtils.ensure_utf8_output()
            except Exception as e:
                self.fail(f"Linux 上 ensure_utf8_output 不应抛异常: {e}")

    def test_no_op_on_darwin(self):
        """macOS 上 ensure_utf8_output 是无操作，不抛异常。"""
        with patch("src.utils.platform_utils.platform.system", return_value="Darwin"):
            try:
                PlatformUtils.ensure_utf8_output()
            except Exception as e:
                self.fail(f"macOS 上 ensure_utf8_output 不应抛异常: {e}")

    def test_windows_already_utf8_no_change(self):
        """Windows 上若 stdout 已是 UTF-8，不重复包装。"""
        import io

        mock_stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        mock_stderr = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with patch("src.utils.platform_utils.platform.system", return_value="Windows"):
            with patch("sys.stdout", mock_stdout):
                with patch("sys.stderr", mock_stderr):
                    # 不应抛异常
                    try:
                        PlatformUtils.ensure_utf8_output()
                    except Exception as e:
                        self.fail(f"ensure_utf8_output 不应抛异常: {e}")


# ============================================================================
# 目录工具测试
# ============================================================================


class TestDirectoryUtils(unittest.TestCase):
    """目录工具测试。"""

    def test_get_temp_dir_returns_existing_dir(self):
        """get_temp_dir 返回存在的目录。"""
        temp_dir = PlatformUtils.get_temp_dir()
        self.assertTrue(os.path.isdir(temp_dir), f"临时目录不存在: {temp_dir}")

    def test_get_temp_dir_returns_string(self):
        """get_temp_dir 返回字符串。"""
        temp_dir = PlatformUtils.get_temp_dir()
        self.assertIsInstance(temp_dir, str)

    def test_get_config_dir_contains_app_name(self):
        """get_config_dir 返回路径中包含 app_name。"""
        config_dir = PlatformUtils.get_config_dir("test-app")
        self.assertIn("test-app", config_dir)

    def test_get_config_dir_creates_directory(self):
        """get_config_dir 确保目录被创建。"""
        import shutil

        # 使用唯一名称避免冲突
        unique_name = f"test_btc_utils_{os.getpid()}"
        try:
            config_dir = PlatformUtils.get_config_dir(unique_name)
            self.assertTrue(os.path.isdir(config_dir), f"配置目录未创建: {config_dir}")
        finally:
            # 清理
            if os.path.exists(config_dir):
                shutil.rmtree(config_dir, ignore_errors=True)

    def test_get_config_dir_default_app_name(self):
        """get_config_dir 默认 app_name 包含 btc-collision-engine。"""
        config_dir = PlatformUtils.get_config_dir()
        self.assertIn("btc-collision-engine", config_dir)

    def test_get_config_dir_returns_string(self):
        """get_config_dir 返回字符串。"""
        config_dir = PlatformUtils.get_config_dir("test-app-str")
        self.assertIsInstance(config_dir, str)


# ============================================================================
# 便捷函数测试
# ============================================================================


class TestConvenienceFunctions(unittest.TestCase):
    """便捷函数测试。"""

    def setUp(self):
        self._orig_platform = PlatformUtils._platform

    def tearDown(self):
        PlatformUtils._platform = self._orig_platform

    def test_get_platform_fonts_returns_dict(self):
        """get_platform_fonts 返回字典。"""
        fonts = get_platform_fonts()
        self.assertIsInstance(fonts, dict)

    def test_get_platform_fonts_keys(self):
        """get_platform_fonts 包含 'ui' 和 'mono' 键。"""
        fonts = get_platform_fonts()
        self.assertIn("ui", fonts)
        self.assertIn("mono", fonts)

    def test_get_platform_fonts_windows_values(self):
        """Windows 下 get_platform_fonts 返回正确字体。"""
        PlatformUtils._platform = "Windows"
        fonts = get_platform_fonts()
        self.assertEqual(fonts["ui"], "Microsoft YaHei")
        self.assertEqual(fonts["mono"], "Consolas")

    def test_get_platform_fonts_linux_values(self):
        """Linux 下 get_platform_fonts 返回正确字体。"""
        PlatformUtils._platform = "Linux"
        fonts = get_platform_fonts()
        self.assertEqual(fonts["ui"], "Noto Sans CJK SC")
        self.assertEqual(fonts["mono"], "DejaVu Sans Mono")


if __name__ == "__main__":
    unittest.main()
