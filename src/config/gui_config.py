"""GUI配置文件 - 存储界面尺寸和样式相关的配置

跨平台兼容版本 v2.2.1
- 支持Windows/Linux/macOS自动字体选择
- 支持DPI缩放
- 自适应窗口大小
"""

# 导入跨平台工具
try:
    from ..utils.platform_utils import PlatformUtils
    _platform_utils_available = True
except ImportError:
    _platform_utils_available = False

# 获取平台适配的字体
if _platform_utils_available:
    _ui_font = PlatformUtils.get_ui_font()
    _mono_font = PlatformUtils.get_mono_font()
else:
    # 降级到默认字体
    _ui_font = "Microsoft YaHei"
    _mono_font = "Consolas"

# 窗口配置
WINDOW_CONFIG = {
    "default_width": 800,    # 默认窗口宽度（会被自适应覆盖）
    "default_height": 1200,  # 默认窗口高度（会被自适应覆盖）
    "min_width": 600,        # 最小窗口宽度
    "min_height": 900,       # 最小窗口高度
    "title": "BTC 碰撞引擎 v2.2.0",  # 窗口标题
    "use_adaptive_size": True,  # 是否使用自适应窗口大小
    "width_ratio": 0.75,     # 窗口宽度占屏幕比例
    "height_ratio": 0.80,    # 窗口高度占屏幕比例
}

# 布局配置
# 状态: 部分配置已在代码中硬编码，计划v2.3.0实现动态布局
# TODO: v2.3.0 实现动态布局配置，使这些配置项生效
LAYOUT_CONFIG = {
    "main_padding_x": 15,    # 主容器水平边距 [计划中]
    "main_padding_y": 15,    # 主容器垂直边距 [计划中]
    "section_spacing": 10,   # 区块间距 [计划中]
    "alert_panel_ratio": 0.3,  # 告警面板默认占比（30%） [已部分实现]
    "use_paned_window": True,  # 是否使用可调整面板 [已实现]
}

# 动画和交互配置
# 状态: v2.2.0基础实现，完整功能计划v2.3.0
# TODO: v2.3.0 实现交互动画和主题切换功能
INTERACTION_CONFIG = {
    "stats_update_interval": 100,  # 统计更新间隔（毫秒） [已实现: 硬编码100ms]
    "alert_update_interval": 5000,  # 告警更新间隔（毫秒） [已实现: 硬编码5000ms]
    "button_hover_effect": True,    # 按钮悬停效果 [计划中]
    "theme_switching": True,        # 支持主题切换 [计划中]
}

# 主题配置
# 状态: v2.2.0仅实现深色主题，多主题计划v2.3.0
# TODO: v2.3.0 实现多主题切换功能
THEME_CONFIG = {
    "current_theme": "dark_catppuccin",  # 当前主题
    "available_themes": ["dark_catppuccin", "dark_material", "light_default"],  # 可用主题
    "theme_switching_enabled": False,  # 是否启用主题切换 [计划中]
}

# 组件尺寸配置
COMPONENT_CONFIG = {
    # 目标地址输入区
    "target_input": {
        "height": 6,  # 输入框高度（行数）
        "font": ("Consolas", 10)  # 字体配置
    },
    
    # 范围参数输入框
    "range_input": {
        "width": 35,  # 输入框宽度
        "font": ("Consolas", 10)  # 字体配置
    },
    
    # 批处理大小输入框
    "batch_size_input": {
        "width": 15,  # 输入框宽度
        "font": ("Consolas", 10)  # 字体配置
    },
    
    # 日志/结果区
    "log_frame": {
        "height": 12,  # 日志框高度（行数）
        "font": ("Consolas", 9)  # 字体配置
    },
    
    # GPU设备下拉框
    "gpu_combo": {
        "width": 45,
        "font": ("Microsoft YaHei", 9)
    }
}

# 字体配置 - 跨平台兼容
FONT_CONFIG = {
    "title": (_ui_font, 16, "bold"),      # 标题字体
    "subtitle": (_ui_font, 9),            # 副标题字体
    "section_title": (_ui_font, 11, "bold"),  # 区块标题字体
    "label": (_ui_font, 10),             # 标签字体
    "hint": (_ui_font, 8),              # 提示字体
    "button": (_ui_font, 9),            # 按钮字体
    "button_large": (_ui_font, 11, "bold"),  # 大按钮字体
    "monospace": (_mono_font, 10),               # 等宽字体（用于输入框和日志）
    "status_bar": (_ui_font, 9),        # 状态栏字体
}

# 平台信息
PLATFORM_INFO = {
    "current_platform": PlatformUtils.get_platform_name() if _platform_utils_available else "Unknown",
    "ui_font": _ui_font,
    "mono_font": _mono_font,
    "dpi_scale": PlatformUtils.get_dpi_scale() if _platform_utils_available else 1.0,
}

# 颜色配置 - Catppuccin Mocha 主题
COLOR_CONFIG = {
    "bg": "#1e1e2e",           # 背景色 (Base)
    "surface": "#313244",     # 表面色 (Surface0)
    "surface1": "#45475a",    # 表面色1 (Surface1)
    "surface2": "#585b70",    # 表面色2 (Surface2)
    "fg": "#cdd6f4",          # 前景文字色 (Text)
    "subtext0": "#a6adc8",    # 次级文字 (Subtext0)
    "subtext1": "#bac2de",    # 次级文字1 (Subtext1)
    "accent": "#f9e2af",      # 强调色（金色/Yellow）
    "blue": "#89b4fa",        # 蓝色
    "lavender": "#b4befe",    # 薰衣草色
    "sapphire": "#74c7ec",    # 蓝宝石色
    "sky": "#89dceb",         # 天空色
    "teal": "#94e2d5",        # 青色 (Teal)
    "green": "#a6e3a1",       # 绿色
    "yellow": "#f9e2af",      # 黄色
    "peach": "#fab387",       # 桃色
    "maroon": "#eba0ac",      # 栗色
    "red": "#f38ba8",         # 红色
    "mauve": "#cba6f7",       # 紫红色
    "pink": "#f5c2e7",        # 粉色
    "flamingo": "#f2cdcd",    # 火烈鸟色
    "rosewater": "#f5e0dc",   # 玫瑰水色
    # 兼容旧版配置
    "success": "#a6e3a1",     # 成功色（绿色）
    "error": "#f38ba8",       # 错误色（红色）
    "info": "#94e2d5",        # 信息色（青色）
    "warning": "#fab387",     # 警告色（桃色）
    "button_bg": "#45475a",   # 按钮背景色
    "button_hover": "#585b70",  # 按钮悬停色
    "text_bg": "#1e1e2e",     # 文本框背景色
    "text_fg": "#cdd6f4"      # 文本框前景色
}

# 间距配置
# 状态: 已在v2.2.1统一使用
# 说明: 所有UI组件应使用PADDING_CONFIG中的配置值
PADDING_CONFIG = {
    "window_padx": 10,    # 窗口内边距（水平） [已使用]
    "window_pady": 10,    # 窗口内边距（垂直） [已使用]
    "section_pady": 5,    # 区块间距 [已使用]
    "element_padx": 5,    # 元素间距（水平） [已使用]
    "element_pady": 2     # 元素间距（垂直） [已使用]
}

# 便捷访问
WINDOW_PADX = PADDING_CONFIG["window_padx"]
WINDOW_PADY = PADDING_CONFIG["window_pady"]
SECTION_PADY = PADDING_CONFIG["section_pady"]
ELEMENT_PADX = PADDING_CONFIG["element_padx"]
ELEMENT_PADY = PADDING_CONFIG["element_pady"]


# 配置验证函数
def validate_color_config():
    """
    验证颜色配置格式是否正确
    
    Raises:
        ValueError: 如果颜色格式不正确
    """
    import re
    hex_pattern = re.compile(r'^#[0-9a-fA-F]{6}$')
    
    for key, value in COLOR_CONFIG.items():
        if not isinstance(value, str):
            raise ValueError(f"颜色配置 {key} 必须是字符串，当前类型: {type(value).__name__}")
        if not hex_pattern.match(value):
            raise ValueError(
                f"颜色配置 {key} 格式错误: {value}\n"
                f"预期格式: #RRGGBB (例如: #1e1e2e)"
            )
    
    return True


def validate_all_configs():
    """
    验证所有配置项的有效性
    
    Returns:
        bool: 验证是否通过
    """
    # 验证窗口配置
    if WINDOW_CONFIG["default_width"] < WINDOW_CONFIG["min_width"]:
        raise ValueError("窗口默认宽度不能小于最小宽度")
    if WINDOW_CONFIG["default_height"] < WINDOW_CONFIG["min_height"]:
        raise ValueError("窗口默认高度不能小于最小高度")
    
    # 验证组件配置
    for component_name, config in COMPONENT_CONFIG.items():
        if "font" in config:
            font = config["font"]
            if not isinstance(font, tuple) or len(font) < 2:
                raise ValueError(f"组件 {component_name} 的字体配置格式错误")
    
    # 验证颜色配置
    validate_color_config()
    
    return True
