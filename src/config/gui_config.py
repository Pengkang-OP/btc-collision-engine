"""GUI配置文件 - 存储界面尺寸和样式相关的配置"""

# 窗口配置
WINDOW_CONFIG = {
    "default_width": 800,    # 默认窗口宽度
    "default_height": 1200,  # 默认窗口高度
    "min_width": 600,        # 最小窗口宽度
    "min_height": 900,       # 最小窗口高度
    "title": "BTC 碰撞引擎 v2.2.0"  # 窗口标题
}

# 布局配置
LAYOUT_CONFIG = {
    "main_padding_x": 15,    # 主容器水平边距
    "main_padding_y": 15,    # 主容器垂直边距
    "section_spacing": 10,   # 区块间距
    "alert_panel_ratio": 0.3,  # 告警面板默认占比（30%）
    "use_paned_window": True,  # 是否使用可调整面板
}

# 动画和交互配置
INTERACTION_CONFIG = {
    "stats_update_interval": 100,  # 统计更新间隔（毫秒）
    "alert_update_interval": 5000,  # 告警更新间隔（毫秒）
    "button_hover_effect": True,    # 按钮悬停效果
    "theme_switching": True,        # 支持主题切换
}

# 主题配置
THEME_CONFIG = {
    "current_theme": "dark_catppuccin",  # 当前主题
    "available_themes": ["dark_catppuccin", "dark_material", "light_default"],  # 可用主题
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

# 字体配置
FONT_CONFIG = {
    "title": ("Microsoft YaHei", 16, "bold"),      # 标题字体
    "subtitle": ("Microsoft YaHei", 9),            # 副标题字体
    "section_title": ("Microsoft YaHei", 11, "bold"),  # 区块标题字体
    "label": ("Microsoft YaHei", 10),             # 标签字体
    "hint": ("Microsoft YaHei", 8),              # 提示字体
    "button": ("Microsoft YaHei", 9),            # 按钮字体
    "button_large": ("Microsoft YaHei", 11, "bold"),  # 大按钮字体
    "monospace": ("Consolas", 10),               # 等宽字体（用于输入框和日志）
    "status_bar": ("Microsoft YaHei", 9),        # 状态栏字体
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
PADDING_CONFIG = {
    "window_padx": 15,    # 窗口内边距（水平）
    "window_pady": 15,    # 窗口内边距（垂直）
    "section_pady": 10,   # 区块间距
    "element_padx": 8,    # 元素间距（水平）
    "element_pady": 3     # 元素间距（垂直）
}
