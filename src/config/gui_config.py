"""GUI配置文件 - 存储界面尺寸和样式相关的配置"""

# 窗口配置
WINDOW_CONFIG = {
    "default_width": 600,    # 默认窗口宽度
    "default_height": 1000,  # 默认窗口高度
    "min_width": 500,        # 最小窗口宽度
    "min_height": 900,       # 最小窗口高度
    "title": "BTC 私钥对撞工具 v1.0"  # 窗口标题
}

# 组件尺寸配置
COMPONENT_CONFIG = {
    # 目标地址输入区
    "target_input": {
        "height": 5,  # 输入框高度（行数）
        "font": ("Consolas", 10)  # 字体配置
    },
    
    # 范围参数输入框
    "range_input": {
        "width": 30,  # 输入框宽度
        "font": ("Consolas", 10)  # 字体配置
    },
    
    # 批处理大小输入框
    "batch_size_input": {
        "width": 12,  # 输入框宽度
        "font": ("Consolas", 10)  # 字体配置
    },
    
    # 日志/结果区
    "log_frame": {
        "height": 10,  # 日志框高度（行数）
        "font": ("Consolas", 9)  # 字体配置
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
}

# 颜色配置
COLOR_CONFIG = {
    "bg": "#1e1e2e",           # 背景色
    "surface": "#313244",     # 表面色
    "fg": "#cdd6f4",          # 前景文字色
    "accent": "#f9e2af",      # 强调色（金色）
    "success": "#a6e3a1",     # 成功色（绿色）
    "error": "#f38ba8",       # 错误色（红色）
    "info": "#94e2d5",        # 信息色（青色）
    "button_bg": "#45475a",   # 按钮背景色
    "button_hover": "#585b70",  # 按钮悬停色
    "text_bg": "#1e1e2e",     # 文本框背景色
    "text_fg": "#cdd6f4"      # 文本框前景色
}

# 间距配置
PADDING_CONFIG = {
    "window_padx": 10,    # 窗口内边距（水平）
    "window_pady": 10,    # 窗口内边距（垂直）
    "section_pady": 5,    # 区块间距
    "element_padx": 5,    # 元素间距（水平）
    "element_pady": 2     # 元素间距（垂直）
}
