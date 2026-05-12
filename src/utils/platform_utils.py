"""跨平台兼容工具类

提供跨平台字体选择、DPI检测、窗口尺寸计算等功能，
确保UI在Windows/Linux/macOS上都有良好的显示效果。
"""

import os
import platform
import sys
import tkinter as tk

from . import get_configured_logger, init_logging

# 初始化日志
init_logging()
logger = get_configured_logger("PlatformUtils")


class PlatformUtils:
    """跨平台兼容工具类

    提供:
    - 平台检测
    - 字体选择
    - DPI缩放
    - 窗口尺寸计算
    - 路径规范化

    示例:
        >>> from src.utils.platform_utils import PlatformUtils
        >>> font = PlatformUtils.get_ui_font()
        >>> width, height = PlatformUtils.get_optimal_window_size()
    """

    _platform = platform.system()
    _dpi_scale = None

    @classmethod
    def is_windows(cls) -> bool:
        """是否Windows平台"""
        return cls._platform == "Windows"

    @classmethod
    def is_macos(cls) -> bool:
        """是否macOS平台"""
        return cls._platform == "Darwin"

    @classmethod
    def is_linux(cls) -> bool:
        """是否Linux平台"""
        return cls._platform == "Linux"

    @classmethod
    def get_platform_name(cls) -> str:
        """获取平台名称"""
        return cls._platform

    @classmethod
    def get_ui_font(cls) -> str:
        """获取适合当前系统的UI字体

        返回:
            字体名称字符串

        字体选择策略:
        - Windows: Microsoft YaHei (微软雅黑)
        - macOS: PingFang SC (苹方)
        - Linux: Noto Sans CJK SC (思源黑体)
        - 其他: Arial (通用)
        """
        fonts = {"Windows": "Microsoft YaHei", "Darwin": "PingFang SC", "Linux": "Noto Sans CJK SC"}

        font = fonts.get(cls._platform, "Arial")
        logger.debug("UI字体: %s (平台: %s)", font, cls._platform)
        return font

    @classmethod
    def get_mono_font(cls) -> str:
        """获取适合当前系统的等宽字体

        返回:
            字体名称字符串

        字体选择策略:
        - Windows: Consolas
        - macOS: Menlo
        - Linux: DejaVu Sans Mono
        - 其他: Courier New
        """
        fonts = {"Windows": "Consolas", "Darwin": "Menlo", "Linux": "DejaVu Sans Mono"}

        font = fonts.get(cls._platform, "Courier New")
        logger.debug("等宽字体: %s (平台: %s)", font, cls._platform)
        return font

    @staticmethod
    def ensure_utf8_output() -> None:
        """确保 Windows 终端输出使用 UTF-8 编码。

        使用 sys.stdout/stderr.reconfigure() 安全配置 UTF-8 编码。
        Python 3.7+ 原生支持，项目最低要求 Python 3.9+。
        在其他系统上无操作。可安全多次调用。

        Task #31: 移除了 io.TextIOWrapper 回退，避免 Python 3.14 中
        TextIOWrapper.close() 关闭底层 fd 导致的 capture 崩溃。
        """
        if platform.system() != "Windows":
            return

        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    @staticmethod
    def get_temp_dir() -> str:
        """获取跨平台临时目录路径。"""
        import tempfile

        return tempfile.gettempdir()

    @staticmethod
    def get_config_dir(app_name: str = "btc-collision-engine") -> str:
        """获取跨平台应用配置目录。

        Windows: %APPDATA%/app_name
        Linux/macOS: ~/.config/app_name
        """
        if platform.system() == "Windows":
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
        else:
            base = os.path.join(os.path.expanduser("~"), ".config")
        config_dir = os.path.join(base, app_name)
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

    @classmethod
    def get_dpi_scale(cls, root: tk.Tk | None = None) -> float:
        """获取DPI缩放比例

        参数:
            root: Tk根窗口（可选，如果为None会创建临时窗口）

        返回:
            DPI缩放比例（1.0 = 96 DPI标准）

        示例:
            >>> scale = PlatformUtils.get_dpi_scale()
            >>> if scale > 1.5:  # 高分屏
            ...     # 调整字体大小
        """
        # 支持环境变量覆盖
        env_scale = os.environ.get("BTC_DPI_SCALE")
        if env_scale:
            try:
                return float(env_scale)
            except ValueError:
                pass

        if cls._dpi_scale is not None:
            return cls._dpi_scale

        try:
            if root is None:
                temp_root = tk.Tk()
                temp_root.withdraw()  # 隐藏窗口
                dpi = temp_root.winfo_fpixels("1i")
                temp_root.destroy()
            else:
                dpi = root.winfo_fpixels("1i")

            cls._dpi_scale = dpi / 96.0
            logger.info("DPI缩放比例: %.2f (%.0f DPI)", cls._dpi_scale, dpi)
            return cls._dpi_scale

        except Exception as e:
            logger.warning("无法检测DPI，使用默认值1.0: %s", str(e))
            cls._dpi_scale = 1.0
            return cls._dpi_scale

    @classmethod
    def get_screen_size(cls, root: tk.Tk | None = None) -> tuple[int, int]:
        """获取屏幕尺寸

        参数:
            root: Tk根窗口（可选）

        返回:
            (width, height) 元组
        """
        try:
            if root is None:
                temp_root = tk.Tk()
                temp_root.withdraw()
                width = temp_root.winfo_screenwidth()
                height = temp_root.winfo_screenheight()
                temp_root.destroy()
            else:
                width = root.winfo_screenwidth()
                height = root.winfo_screenheight()

            logger.debug("屏幕尺寸: %dx%d", width, height)
            return width, height

        except Exception as e:
            logger.warning("无法获取屏幕尺寸，使用默认值: %s", str(e))
            return 1920, 1080

    @classmethod
    def get_optimal_window_size(
        cls, root: tk.Tk | None = None, width_ratio: float = 0.75, height_ratio: float = 0.80
    ) -> tuple[int, int]:
        """根据屏幕分辨率计算最佳窗口尺寸

        参数:
            root: Tk根窗口（可选）
            width_ratio: 窗口宽度占屏幕宽度的比例（默认0.75 = 75%）
            height_ratio: 窗口高度占屏幕高度的比例（默认0.80 = 80%）

        返回:
            (width, height) 元组

        策略:
        - 使用屏幕的75%宽度和80%高度
        - 最小600x900
        - 最大1920x1200
        """
        screen_width, screen_height = cls.get_screen_size(root)

        # 计算比例尺寸
        width = int(screen_width * width_ratio)
        height = int(screen_height * height_ratio)

        # 限制范围
        min_width, min_height = 600, 900
        max_width, max_height = 1920, 1200

        width = max(min_width, min(width, max_width))
        height = max(min_height, min(height, max_height))

        logger.info("最优窗口尺寸: %dx%d (屏幕: %dx%d)", width, height, screen_width, screen_height)

        return width, height

    @classmethod
    def scale_font_size(cls, size: int, root: tk.Tk | None = None) -> int:
        """根据DPI缩放字体大小

        参数:
            size: 原始字体大小
            root: Tk根窗口（可选）

        返回:
            缩放后的字体大小
        """
        dpi_scale = cls.get_dpi_scale(root)

        # DPI >= 1.5时才缩放
        if dpi_scale >= 1.5:
            scaled_size = int(size * dpi_scale)
            logger.debug("字体缩放: %d -> %d (DPI: %.2f)", size, scaled_size, dpi_scale)
            return scaled_size

        return size

    @classmethod
    def get_font_config(cls, root: tk.Tk | None = None) -> dict:
        """获取完整的字体配置（跨平台+DPI适配）

        参数:
            root: Tk根窗口（可选）

        返回:
            字体配置字典
        """
        ui_font = cls.get_ui_font()
        mono_font = cls.get_mono_font()

        # 高分屏调整字体大小
        dpi_scale = cls.get_dpi_scale(root)
        font_scale = dpi_scale if dpi_scale >= 1.5 else 1.0

        config = {
            "title": (ui_font, int(16 * font_scale), "bold"),
            "subtitle": (ui_font, int(9 * font_scale)),
            "section_title": (ui_font, int(11 * font_scale), "bold"),
            "label": (ui_font, int(10 * font_scale)),
            "hint": (ui_font, int(8 * font_scale)),
            "button": (ui_font, int(9 * font_scale)),
            "button_large": (ui_font, int(11 * font_scale), "bold"),
            "monospace": (mono_font, int(10 * font_scale)),
            "status_bar": (ui_font, int(9 * font_scale)),
        }

        logger.info("字体配置生成完成 (DPI缩放: %.2f)", font_scale)
        return config

    @classmethod
    def normalize_path(cls, path: str) -> str:
        """规范化文件路径（跨平台）

        参数:
            path: 文件路径

        返回:
            规范化后的路径
        """
        return os.path.normpath(path)

    @classmethod
    def get_line_ending(cls) -> str:
        """获取当前平台的换行符

        返回:
            换行符字符串
        """
        return os.linesep

    @classmethod
    def get_system_info(cls) -> dict:
        """获取系统信息

        返回:
            系统信息字典
        """
        return {
            "platform": cls._platform,
            "platform_version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        }


# 便捷函数
def get_platform_fonts() -> dict:
    """获取当前平台的字体配置（便捷函数）

    返回:
        {"ui": UI字体, "mono": 等宽字体}
    """
    return {"ui": PlatformUtils.get_ui_font(), "mono": PlatformUtils.get_mono_font()}
