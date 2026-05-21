"""UI辅助工具 - 工具提示和用户引导"""

import tkinter as tk
from tkinter import messagebox
from typing import Any

from ..config.gui_config import FONT_CONFIG
from .platform_utils import PlatformUtils


class Tooltip:
    """工具提示类

    为UI组件添加鼠标悬停提示

    示例:
        >>> tooltip = Tooltip(button, "点击开始碰撞")
    """

    def __init__(self, widget: Any, text: str, delay: int = 500) -> None:
        """
        初始化工具提示

        参数:
            widget: 要添加提示的组件
            text: 提示文本
            delay: 延迟显示时间（毫秒）
        """
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip_window: Any | None = None
        self.after_id = None

        self._bind_events()

    def _bind_events(self):
        """绑定事件"""
        self.widget.bind("<Enter>", self._show_tooltip, add="+")
        self.widget.bind("<Leave>", self._hide_tooltip, add="+")
        self.widget.bind("<Button-1>", self._hide_tooltip, add="+")

    def _show_tooltip(self, event=None):
        """显示提示"""

        def show() -> None:
            # 获取鼠标位置
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

            # 创建提示窗口
            self.tooltip_window = tk.Toplevel(self.widget)
            self.tooltip_window.wm_overrideredirect(True)
            self.tooltip_window.wm_geometry(f"+{x}+{y}")

            # 提示标签
            label = tk.Label(
                self.tooltip_window,
                text=self.text,
                justify=tk.LEFT,
                background="#ffffe0",
                relief="solid",
                borderwidth=1,
                font=FONT_CONFIG.get("hint", PlatformUtils.get_font_config()["hint"]),
                wraplength=300,
            )
            label.pack(ipadx=5, ipady=3)

        # 延迟显示
        self.after_id = self.widget.after(self.delay, show)

    def _hide_tooltip(self, event=None):
        """隐藏提示"""
        # 取消延迟显示
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

        # 销毁提示窗口
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


def add_tooltip(widget: Any, text: str, delay: int = 500) -> Tooltip:
    """为组件添加工具提示（便捷函数）

    参数:
        widget: 要添加提示的组件
        text: 提示文本
        delay: 延迟显示时间（毫秒）

    返回:
        Tooltip实例
    """
    return Tooltip(widget, text, delay)


class UserGuide:
    """用户引导类

    提供首次使用引导、帮助信息等功能
    """

    def __init__(self, root: tk.Tk) -> None:
        """
        初始化用户引导

        参数:
            root: Tk根窗口
        """
        self.root = root
        self._has_shown_welcome = False

    def show_welcome_guide(self) -> Any:
        """显示新用户欢迎引导"""
        if self._has_shown_welcome:
            return

        message = (
            "欢迎使用 BTC 碰撞引擎 v4.2.2！\n\n"
            "快速开始：\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "1. 在'目标地址区'输入比特币地址\n"
            "   （支持P2PKH/P2SH/Bech32/WIF/公钥）\n\n"
            "2. 选择碰撞模式：\n"
            "   • 随机搜索 - 随机生成私钥碰撞\n"
            "   • 范围扫描 - 扫描指定范围\n"
            "   • 暴力穷举 - 从头开始穷举\n\n"
            "3. 点击'开始碰撞'按钮\n\n"
            "提示：\n"
            "• 点击'导入文件'可批量导入地址\n"
            "• 支持断点续传功能\n"
            "• GPU加速可提升100-1000倍性能\n\n"
            "快捷键：\n"
            "• Ctrl+Enter - 开始碰撞\n"
            "• Ctrl+Shift+S - 停止\n"
            "• F5 - 恢复\n"
            "• Ctrl+O - 导入文件\n"
        )

        result = messagebox.askokcancel("欢迎使用", message)

        self._has_shown_welcome = True
        return result

    def show_format_help(self) -> None:
        """显示输入格式帮助"""
        message = (
            "支持的输入格式：\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "1. P2PKH地址（以1开头）\n"
            "   示例: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n\n"
            "2. P2SH地址（以3开头）\n"
            "   示例: 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy\n\n"
            "3. Bech32地址（以bc1开头）\n"
            "   示例: bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq\n\n"
            "4. WIF私钥（以5/K/L开头）\n"
            "   示例: 5HueCGU8rMjfsEXEg4MdpQW3pNjRwbTkXq\n\n"
            "5. 公钥（66或130位十六进制）\n"
            "   示例: 0279be667ef9dcbbac55a06295ce870b0702...\n\n"
            "注意：\n"
            "• 每行一个地址\n"
            "• 不要包含空格或特殊字符\n"
            "• 系统会自动去重\n"
        )

        messagebox.showinfo("输入格式帮助", message)

    def show_mode_help(self, mode: str) -> None:
        """显示模式帮助

        参数:
            mode: 模式名称 (random/range/brute_force)
        """
        help_text = {
            "random": (
                "随机搜索模式\n\n"
                "• 随机生成私钥进行碰撞\n"
                "• 适合未知范围的地址\n"
                "• 可能重复生成相同私钥\n"
                "• 系统会自动去重\n"
            ),
            "range": (
                "范围扫描模式\n\n• 扫描指定的私钥范围\n• 需要设置起始值和结束值\n• 不会重复\n• 适合已知范围的地址\n"
            ),
            "brute_force": (
                "暴力穷举模式\n\n• 从1开始顺序穷举\n• 保证不重复\n• 适合小范围搜索\n• 支持断点续传\n"
            ),
        }

        messagebox.showinfo(f"{mode}模式说明", help_text.get(mode, "未知模式"))


def setup_tutorials(gui_app: Any) -> None:
    """为GUI应用设置工具提示和引导

    参数:
        gui_app: CollisionGUI实例
    """
    try:
        # 目标地址区提示
        if hasattr(gui_app, "target_frame"):
            add_tooltip(
                gui_app.target_frame,
                "输入比特币地址、WIF私钥或公钥\n每行一个，支持多种格式\n点击'导入文件'可批量导入",
            )

        # 模式选择提示
        if hasattr(gui_app, "control_panel"):
            panel = gui_app.control_panel
            if hasattr(panel, "mode_var"):
                add_tooltip(
                    panel,
                    "选择碰撞模式：\n• 随机搜索 - 适合未知范围\n• 范围扫描 - 适合已知范围\n• 暴力穷举 - 保证不重复",
                )

        # 开始按钮提示
        if hasattr(gui_app, "control_panel"):
            panel = gui_app.control_panel
            if hasattr(panel, "btn_start"):
                add_tooltip(panel.btn_start, "开始碰撞 (Ctrl+Enter)")
            if hasattr(panel, "btn_stop"):
                add_tooltip(panel.btn_stop, "停止碰撞 (Ctrl+Shift+S)")
            if hasattr(panel, "btn_resume"):
                add_tooltip(panel.btn_resume, "从断点恢复 (F5)")

    except Exception as e:
        # 工具提示设置失败不应影响主程序
        import logging

        logging.warning("设置工具提示失败: %s", str(e))
