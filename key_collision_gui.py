#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比特币私钥对撞工具 - Tkinter GUI 界面

这是一个基于纯Python标准库实现的比特币私钥对撞工具的图形界面。
支持多种对撞模式：随机碰撞、范围扫描、暴力穷举。

本实现仅使用Python标准库，不依赖任何第三方加密库。

作者: BTC Project
版本: v1.1
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import time
import os
import logging
from datetime import datetime

from src.core import (
    Secp256k1, EllipticCurve, HashUtils, Base58, WIF,
    P2PKHAddressGenerator
)
from src.collision import (
    KeyCollisionEngine, TargetResolver, CollisionStats
)
from src.config.gui_config import WINDOW_CONFIG, COMPONENT_CONFIG, FONT_CONFIG, COLOR_CONFIG, PADDING_CONFIG
from src.utils.ui_helpers import format_timestamp, format_mode_name, format_number_with_commas


# =============================================================================
# 配色方案 - 深色主题
# =============================================================================
class Colors:
    """深色主题配色方案"""
    BG = COLOR_CONFIG["bg"]           # 背景
    SURFACE = COLOR_CONFIG["surface"]     # 表面
    FG = COLOR_CONFIG["fg"]          # 前景文字
    ACCENT = COLOR_CONFIG["accent"]      # 强调色（金色）
    SUCCESS = COLOR_CONFIG["success"]     # 成功色（绿色）
    ERROR = COLOR_CONFIG["error"]       # 错误色（红色）
    INFO = COLOR_CONFIG["info"]        # 信息色（青色）
    BUTTON_BG = COLOR_CONFIG["button_bg"]   # 按钮背景
    BUTTON_HOVER = COLOR_CONFIG["button_hover"]  # 按钮悬停
    TEXT_BG = COLOR_CONFIG["text_bg"]     # 文本框背景
    TEXT_FG = COLOR_CONFIG["text_fg"]     # 文本框前景


# =============================================================================
# 目标地址输入区
# =============================================================================
class TargetInputFrame(tk.Frame):
    """目标地址输入区组件"""
    
    def __init__(self, parent, resolver: TargetResolver, gui_app=None, **kwargs):
        super().__init__(parent, bg=Colors.SURFACE, **kwargs)
        self.resolver = resolver
        self.targets = set()
        self.gui_app = gui_app  # 保存主GUI应用引用
        
        self._create_widgets()
    
    def _create_widgets(self):
        """创建界面组件"""
        # 标题
        title = tk.Label(
            self, text="目标地址区", font=("Microsoft YaHei", 11, "bold"),
            bg=Colors.SURFACE, fg=Colors.ACCENT
        )
        title.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        # 输入框框架
        input_frame = tk.Frame(self, bg=Colors.SURFACE)
        input_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 提示标签
        hint = tk.Label(
            input_frame, text="输入目标地址/公钥/WIF（每行一个，支持 # 注释）",
            font=("Microsoft YaHei", 9), bg=Colors.SURFACE, fg=Colors.INFO
        )
        hint.pack(anchor=tk.W, pady=(0, 5))
        
        # ScrolledText 输入框
        self.text_input = scrolledtext.ScrolledText(
            input_frame, height=COMPONENT_CONFIG["target_input"]["height"], 
            font=COMPONENT_CONFIG["target_input"]["font"],
            bg=Colors.TEXT_BG, fg=Colors.TEXT_FG,
            insertbackground=Colors.FG, relief=tk.FLAT,
            highlightbackground=Colors.BUTTON_BG,
            highlightcolor=Colors.ACCENT, highlightthickness=1
        )
        self.text_input.pack(fill=tk.BOTH, expand=True)
        
        # 按钮区
        btn_frame = tk.Frame(self, bg=Colors.SURFACE)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.btn_import = tk.Button(
            btn_frame, text="导入文件", font=("Microsoft YaHei", 9),
            bg=Colors.BUTTON_BG, fg=Colors.FG, activebackground=Colors.BUTTON_HOVER,
            activeforeground=Colors.FG, relief=tk.FLAT, cursor="hand2",
            command=self._on_import
        )
        self.btn_import.pack(side=tk.LEFT, padx=(0, 5))
        
        self.btn_parse = tk.Button(
            btn_frame, text="解析目标", font=("Microsoft YaHei", 9),
            bg=Colors.BUTTON_BG, fg=Colors.FG, activebackground=Colors.BUTTON_HOVER,
            activeforeground=Colors.FG, relief=tk.FLAT, cursor="hand2",
            command=self._on_parse
        )
        self.btn_parse.pack(side=tk.LEFT, padx=5)
        
        self.btn_clear = tk.Button(
            btn_frame, text="清空", font=("Microsoft YaHei", 9),
            bg=Colors.BUTTON_BG, fg=Colors.FG, activebackground=Colors.BUTTON_HOVER,
            activeforeground=Colors.FG, relief=tk.FLAT, cursor="hand2",
            command=self._on_clear
        )
        self.btn_clear.pack(side=tk.LEFT, padx=5)
        
        # 状态标签
        self.status_label = tk.Label(
            self, text="状态: 已加载 0 个有效目标地址",
            font=("Microsoft YaHei", 9), bg=Colors.SURFACE, fg=Colors.INFO
        )
        self.status_label.pack(anchor=tk.W, padx=10, pady=(0, 10))
    
    def _on_import(self):
        """导入文件按钮回调"""
        filepath = filedialog.askopenfilename(
            title="选择目标地址文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.text_input.delete('1.0', tk.END)
                self.text_input.insert('1.0', content)
                self._on_parse()
            except Exception as e:
                messagebox.showerror("导入错误", f"无法读取文件:\n{str(e)}")
    
    def _on_parse(self):
        """解析目标按钮回调"""
        content = self.text_input.get('1.0', tk.END).strip()
        lines = content.split('\n')
        
        # 过滤空行和注释
        inputs = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                inputs.append(line)
        
        if not inputs:
            messagebox.showwarning("提示", "请输入至少一个目标地址")
            return
        
        # 解析目标（resolve_multiple返回字典，需要提取值）
        result_dict = self.resolver.resolve_multiple(inputs)
        self.targets = set(result_dict.values())
        
        if not self.targets:
            messagebox.showerror("解析失败", "未能解析任何有效的目标地址\n\n请检查输入格式是否正确\n\n支持的格式：\n- P2PKH地址（以1开头）\n- WIF私钥（以5/K/L开头）\n- 公钥（66或130位十六进制）")
            return
        
        # 更新状态
        self._update_status()
        
        # 在日志区输出解析结果（如果有主GUI应用引用）
        if self.gui_app and hasattr(self.gui_app, 'log_frame'):
            count = len(self.targets)
            self.gui_app.log_frame.log(f"✅ 成功解析 {count} 个目标地址")
            for addr in list(self.targets)[:3]:  # 只显示前3个
                self.gui_app.log_frame.log(f"   → {addr[:20]}...")
            if count > 3:
                self.gui_app.log_frame.log(f"   ... 及其他 {count-3} 个地址")
    
    def _on_clear(self):
        """清空按钮回调"""
        self.text_input.delete('1.0', tk.END)
        self.targets.clear()
        self._update_status()
    
    def _update_status(self):
        """更新状态标签"""
        count = len(self.targets)
        self.status_label.config(text=f"状态: 已加载 {count} 个有效目标地址")
        if count > 0:
            self.status_label.config(fg=Colors.SUCCESS)
        else:
            self.status_label.config(fg=Colors.INFO)
    
    def get_targets(self) -> set:
        """获取已解析的目标地址集合"""
        return self.targets
    
    def set_enabled(self, enabled: bool):
        """设置组件启用/禁用状态"""
        state = tk.NORMAL if enabled else tk.DISABLED
        self.text_input.config(state=state)
        self.btn_import.config(state=state)
        self.btn_parse.config(state=state)
        self.btn_clear.config(state=state)


# =============================================================================
# 控制面板
# =============================================================================
class ControlPanel(tk.Frame):
    """控制面板组件"""
    
    def __init__(self, parent, on_mode_change=None, **kwargs):
        super().__init__(parent, bg=Colors.SURFACE, **kwargs)
        self.on_mode_change = on_mode_change
        self.mode_var = tk.StringVar(value="random")
        
        self._create_widgets()
    
    def _create_widgets(self):
        """创建界面组件"""
        # 标题
        title = tk.Label(
            self, text="控制面板", font=("Microsoft YaHei", 11, "bold"),
            bg=Colors.SURFACE, fg=Colors.ACCENT
        )
        title.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        # 模式选择
        mode_frame = tk.Frame(self, bg=Colors.SURFACE)
        mode_frame.pack(fill=tk.X, padx=10, pady=5)
        
        mode_label = tk.Label(
            mode_frame, text="模式:", font=("Microsoft YaHei", 10),
            bg=Colors.SURFACE, fg=Colors.FG
        )
        mode_label.pack(side=tk.LEFT)
        
        # 单选按钮
        self.rb_random = tk.Radiobutton(
            mode_frame, text="随机碰撞", variable=self.mode_var,
            value="random", font=("Microsoft YaHei", 9),
            bg=Colors.SURFACE, fg=Colors.FG, selectcolor=Colors.BG,
            activebackground=Colors.SURFACE, activeforeground=Colors.ACCENT,
            command=self._on_mode_changed
        )
        self.rb_random.pack(side=tk.LEFT, padx=(10, 5))
        
        self.rb_range = tk.Radiobutton(
            mode_frame, text="范围扫描", variable=self.mode_var,
            value="range", font=("Microsoft YaHei", 9),
            bg=Colors.SURFACE, fg=Colors.FG, selectcolor=Colors.BG,
            activebackground=Colors.SURFACE, activeforeground=Colors.ACCENT,
            command=self._on_mode_changed
        )
        self.rb_range.pack(side=tk.LEFT, padx=5)
        
        self.rb_brute = tk.Radiobutton(
            mode_frame, text="暴力穷举", variable=self.mode_var,
            value="brute_force", font=("Microsoft YaHei", 9),
            bg=Colors.SURFACE, fg=Colors.FG, selectcolor=Colors.BG,
            activebackground=Colors.SURFACE, activeforeground=Colors.ACCENT,
            command=self._on_mode_changed
        )
        self.rb_brute.pack(side=tk.LEFT, padx=5)
        
        # 范围参数区
        self.range_frame = tk.Frame(self, bg=Colors.SURFACE)
        self.range_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 起始值
        start_frame = tk.Frame(self.range_frame, bg=Colors.SURFACE)
        start_frame.pack(fill=tk.X, pady=2)
        
        start_label = tk.Label(
            start_frame, text="起始值:", font=("Microsoft YaHei", 9),
            bg=Colors.SURFACE, fg=Colors.FG, width=8, anchor=tk.W
        )
        start_label.pack(side=tk.LEFT)
        
        self.entry_start = tk.Entry(
            start_frame, font=COMPONENT_CONFIG["range_input"]["font"],
            bg=Colors.TEXT_BG, fg=Colors.TEXT_FG,
            insertbackground=Colors.FG, relief=tk.FLAT,
            highlightbackground=Colors.BUTTON_BG,
            highlightcolor=Colors.ACCENT, highlightthickness=1,
            width=COMPONENT_CONFIG["range_input"]["width"]  # 使用配置文件中的宽度
        )
        self.entry_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        start_hint = tk.Label(
            start_frame, text="(十六进制)", font=("Microsoft YaHei", 8),
            bg=Colors.SURFACE, fg=Colors.INFO
        )
        start_hint.pack(side=tk.LEFT, padx=(5, 0))
        
        # 结束值
        end_frame = tk.Frame(self.range_frame, bg=Colors.SURFACE)
        end_frame.pack(fill=tk.X, pady=2)
        
        end_label = tk.Label(
            end_frame, text="结束值:", font=("Microsoft YaHei", 9),
            bg=Colors.SURFACE, fg=Colors.FG, width=8, anchor=tk.W
        )
        end_label.pack(side=tk.LEFT)
        
        self.entry_end = tk.Entry(
            end_frame, font=COMPONENT_CONFIG["range_input"]["font"],
            bg=Colors.TEXT_BG, fg=Colors.TEXT_FG,
            insertbackground=Colors.FG, relief=tk.FLAT,
            highlightbackground=Colors.BUTTON_BG,
            highlightcolor=Colors.ACCENT, highlightthickness=1,
            width=COMPONENT_CONFIG["range_input"]["width"]  # 使用配置文件中的宽度
        )
        self.entry_end.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        end_hint = tk.Label(
            end_frame, text="(十六进制)", font=("Microsoft YaHei", 8),
            bg=Colors.SURFACE, fg=Colors.INFO
        )
        end_hint.pack(side=tk.LEFT, padx=(5, 0))
        
        # 功能选项区
        options_frame = tk.Frame(self, bg=Colors.SURFACE)
        options_frame.pack(fill=tk.X, padx=10, pady=5)
        
        options_label = tk.Label(
            options_frame, text="高级选项:", font=("Microsoft YaHei", 10),
            bg=Colors.SURFACE, fg=Colors.FG
        )
        options_label.pack(side=tk.LEFT)
        
        # GPU加速复选框
        self.gpu_var = tk.BooleanVar(value=True)
        self.cb_gpu = tk.Checkbutton(
            options_frame, text="GPU加速", variable=self.gpu_var,
            font=("Microsoft YaHei", 9),
            bg=Colors.SURFACE, fg=Colors.FG, selectcolor=Colors.BG,
            activebackground=Colors.SURFACE, activeforeground=Colors.ACCENT,
            command=self._on_gpu_toggled
        )
        self.cb_gpu.pack(side=tk.LEFT, padx=(10, 5))
        
        # 去重过滤复选框（与断点续传位置对换）
        self.dedup_var = tk.BooleanVar(value=False)
        self.cb_dedup = tk.Checkbutton(
            options_frame, text="去重过滤", variable=self.dedup_var,
            font=("Microsoft YaHei", 9),
            bg=Colors.SURFACE, fg=Colors.FG, selectcolor=Colors.BG,
            activebackground=Colors.SURFACE, activeforeground=Colors.ACCENT
        )
        self.cb_dedup.pack(side=tk.LEFT, padx=5)
        
        # 断点续传复选框（与去重过滤位置对换）
        self.checkpoint_var = tk.BooleanVar(value=False)
        self.cb_checkpoint = tk.Checkbutton(
            options_frame, text="断点续传", variable=self.checkpoint_var,
            font=("Microsoft YaHei", 9),
            bg=Colors.SURFACE, fg=Colors.FG, selectcolor=Colors.BG,
            activebackground=Colors.SURFACE, activeforeground=Colors.ACCENT,
            command=self._on_checkpoint_toggled
        )
        self.cb_checkpoint.pack(side=tk.LEFT, padx=(10, 5))
        
        # GPU设备选择区
        self.gpu_device_frame = tk.Frame(self, bg=Colors.SURFACE)
        self.gpu_device_frame.pack(fill=tk.X, padx=10, pady=2)
        
        gpu_device_label = tk.Label(
            self.gpu_device_frame, text="GPU设备:", font=("Microsoft YaHei", 9),
            bg=Colors.SURFACE, fg=Colors.FG, width=8, anchor=tk.W
        )
        gpu_device_label.pack(side=tk.LEFT)
        
        # GPU设备下拉框
        self.gpu_device_var = tk.StringVar(value="自动选择")
        self.gpu_device_combo = ttk.Combobox(
            self.gpu_device_frame, textvariable=self.gpu_device_var,
            font=("Microsoft YaHei", 9), state="readonly", width=40
        )
        self.gpu_device_combo.pack(side=tk.LEFT, padx=(5, 0), fill=tk.X, expand=True)
        
        # 检测并填充GPU设备列表
        self._detect_gpu_devices()
        
        # 控制按钮区
        btn_frame = tk.Frame(self, bg=Colors.SURFACE)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.btn_start = tk.Button(
            btn_frame, text="▶ 开始对撞", font=("Microsoft YaHei", 11, "bold"),
            bg=Colors.SUCCESS, fg=Colors.BG, activebackground="#86efac",
            activeforeground=Colors.BG, relief=tk.FLAT, cursor="hand2",
            width=14, height=1
        )
        self.btn_start.pack(side=tk.LEFT, padx=(0, 8))
        
        self.btn_stop = tk.Button(
            btn_frame, text="⏹ 停止", font=("Microsoft YaHei", 11, "bold"),
            bg=Colors.ERROR, fg=Colors.BG, activebackground="#fca5a5",
            activeforeground=Colors.BG, relief=tk.FLAT, cursor="hand2",
            width=10, height=1, state=tk.DISABLED
        )
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 8))
        
        # 恢复断点按钮（优化样式，与开始/停止按钮协调）
        self.btn_resume = tk.Button(
            btn_frame, text="↺ 恢复断点", font=("Microsoft YaHei", 11),
            bg=Colors.BUTTON_BG, fg=Colors.FG,
            activebackground=Colors.BUTTON_HOVER, activeforeground=Colors.FG,
            relief=tk.FLAT, cursor="hand2",
            command=self._on_resume_checkpoint,
            width=12, height=1
        )
        self.btn_resume.pack(side=tk.LEFT, padx=(0, 5))
        
        # 初始隐藏范围参数
        self._update_range_visibility()
    
    def _on_mode_changed(self):
        """模式改变回调"""
        self._update_range_visibility()
        if self.on_mode_change:
            self.on_mode_change(self.get_mode())
    
    def _update_range_visibility(self):
        """更新范围参数区可见性"""
        mode = self.mode_var.get()
        if mode in ("range", "brute_force"):
            self.range_frame.pack(fill=tk.X, padx=10, pady=5)
            if mode == "brute_force":
                # 暴力穷举只显示起始值
                self.entry_end.config(state=tk.DISABLED)
            else:
                self.entry_end.config(state=tk.NORMAL)
        else:
            self.range_frame.pack_forget()
    
    def _on_gpu_toggled(self):
        """GPU加速开关切换回调"""
        if self.gpu_var.get():
            self.gpu_device_frame.pack(fill=tk.X, padx=10, pady=2)
        else:
            self.gpu_device_frame.pack_forget()
    
    def _on_checkpoint_toggled(self):
        """断点续传开关切换回调"""
        if self.checkpoint_var.get():
            # 检查是否存在断点文件
            from src.collision.checkpoint_manager import CheckpointManager
            mgr = CheckpointManager()
            if mgr.exists():
                data = mgr.load()
                if data:
                    mode = data.get("mode", "random")
                    total_checked = data.get("total_checked", 0)
                    timestamp = data.get("timestamp", "未知")
                    
                    info_msg = f"检测到现有断点:\n"
                    info_msg += f"模式: {mode}\n"
                    info_msg += f"已检测: {total_checked:,}\n"
                    info_msg += f"保存时间: {timestamp}\n\n"
                    info_msg += "启用断点续传后，将自动从上次进度继续。"
                    
                    messagebox.showinfo("断点信息", info_msg)
    
    def _detect_gpu_devices(self):
        """检测可用的GPU设备并填充下拉框"""
        try:
            from src.config.crypto_config import get_crypto_config
            config = get_crypto_config()
            devices = config.get_gpu_device_info()
            
            device_list = ["自动选择"]
            self._gpu_device_map = {"自动选择": -1}
            
            for i, dev in enumerate(devices):
                device_name = f"[{i}] {dev.get('name', 'Unknown')} ({dev.get('vendor', 'Unknown')})"
                device_list.append(device_name)
                self._gpu_device_map[device_name] = i
            
            self.gpu_device_combo['values'] = device_list
            
            # 默认选择 GPU 1（索引为1的设备），如果存在的话
            # 注意：引擎具有自动回退机制，所以GUI也可以智能选择
            if len(devices) > 1:
                # 有GPU 1设备，选择它
                device_1_name = f"[1] {devices[1].get('name', 'Unknown')} ({devices[1].get('vendor', 'Unknown')})"
                self.gpu_device_var.set(device_1_name)
            elif len(devices) == 1:
                # 只有GPU 0，选择它（引擎会自动回退）
                device_0_name = f"[0] {devices[0].get('name', 'Unknown')} ({devices[0].get('vendor', 'Unknown')})"
                self.gpu_device_var.set(device_0_name)
            else:
                # 没有GPU设备，选择自动选择
                self.gpu_device_var.set("自动选择")
            
            # 如果有GPU设备，显示GPU设备选择区
            if len(devices) > 0:
                self.gpu_device_frame.pack(fill=tk.X, padx=10, pady=2)
            else:
                self.gpu_device_frame.pack_forget()
                self.gpu_var.set(False)
                self.cb_gpu.config(state=tk.DISABLED)
                
        except Exception as e:
            # GPU检测失败，隐藏GPU选项
            self.gpu_device_frame.pack_forget()
            self.gpu_var.set(False)
            self.cb_gpu.config(state=tk.DISABLED)
    
    def get_gpu_device_index(self) -> int:
        """获取选择的GPU设备索引"""
        if not self.gpu_var.get():
            return -1  # 使用CPU
        selected = self.gpu_device_var.get()
        return self._gpu_device_map.get(selected, -1)
    
    def use_gpu(self) -> bool:
        """是否使用GPU加速"""
        return self.gpu_var.get()

    def get_mode(self) -> str:
        """获取当前模式"""
        return self.mode_var.get()
    
    def get_range_params(self) -> tuple:
        """获取范围参数 (start, end)
        
        返回:
            (start, end) 元组，解析失败返回 (None, None)
        """
        try:
            start_str = self.entry_start.get().strip()
            start = int(start_str, 16) if start_str else 1
            
            if self.mode_var.get() == "brute_force":
                end = None
            else:
                end_str = self.entry_end.get().strip()
                end = int(end_str, 16) if end_str else start + 1000000
            
            # 验证范围参数
            from src.core.secp256k1 import Secp256k1
            if start < 1:
                messagebox.showerror("参数错误", "起始值必须 >= 1")
                return (None, None)
            if end is not None and end >= Secp256k1.N:
                messagebox.showerror("参数错误", f"结束值必须 < secp256k1曲线阶 N")
                return (None, None)
            if end is not None and start >= end:
                messagebox.showerror("参数错误", "起始值必须小于结束值")
                return (None, None)
            
            return (start, end)
        except ValueError:
            return (None, None)
    
    def set_buttons_state(self, running: bool):
        """设置按钮状态
        
        当对撞运行时，禁用所有配置控件；
        当对撞停止时，恢复所有配置控件的可更改状态。
        """
        if running:
            # 禁用"开始对撞"按钮，启用"停止"按钮
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            
            # 禁用模式选择单选按钮
            self.rb_random.config(state=tk.DISABLED)
            self.rb_range.config(state=tk.DISABLED)
            self.rb_brute.config(state=tk.DISABLED)
            
            # 禁用范围参数输入框
            self.entry_start.config(state=tk.DISABLED)
            self.entry_end.config(state=tk.DISABLED)
            
            # 禁用高级选项复选框
            self.cb_gpu.config(state=tk.DISABLED)
            self.cb_checkpoint.config(state=tk.DISABLED)
            self.cb_dedup.config(state=tk.DISABLED)
            
            # 禁用GPU设备下拉框
            self.gpu_device_combo.config(state=tk.DISABLED)
            
            # 禁用恢复断点按钮
            self.btn_resume.config(state=tk.DISABLED)
        else:
            # 启用"开始对撞"按钮，禁用"停止"按钮
            self.btn_start.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)
            
            # 启用模式选择单选按钮
            self.rb_random.config(state=tk.NORMAL)
            self.rb_range.config(state=tk.NORMAL)
            self.rb_brute.config(state=tk.NORMAL)
            
            # 启用范围参数输入框
            self.entry_start.config(state=tk.NORMAL)
            self.entry_end.config(state=tk.NORMAL)
            
            # 启用高级选项复选框
            self.cb_gpu.config(state=tk.NORMAL)
            self.cb_checkpoint.config(state=tk.NORMAL)
            self.cb_dedup.config(state=tk.NORMAL)
            
            # 启用GPU设备下拉框（仅在GPU加速启用时）
            if self.gpu_var.get():
                self.gpu_device_combo.config(state="readonly")
            else:
                self.gpu_device_combo.config(state=tk.DISABLED)
            
            # 启用恢复断点按钮
            self.btn_resume.config(state=tk.NORMAL)
            
            # 根据当前模式更新范围参数区可见性
            self._update_range_visibility()
    
    def _on_resume_checkpoint(self):
        """恢复断点按钮回调"""
        from src.collision.checkpoint_manager import CheckpointManager
        mgr = CheckpointManager()
        if not mgr.exists():
            messagebox.showinfo("提示", "未找到断点文件")
            return
        
        data = mgr.load()
        if data is None:
            messagebox.showerror("错误", "断点文件加载失败或格式不兼容")
            return
        
        # 显示断点信息
        mode = data.get("mode", "random")
        total_checked = data.get("total_checked", 0)
        targets_count = len(data.get("targets", []))
        timestamp = data.get("timestamp", "未知")
        
        info_msg = f"断点信息:\n"
        info_msg += f"模式: {mode}\n"
        info_msg += f"目标地址数: {targets_count}\n"
        info_msg += f"已检测数量: {total_checked:,}\n"
        info_msg += f"保存时间: {timestamp}\n\n"
        info_msg += "是否恢复此断点继续对撞?"
        
        result = messagebox.askyesno("恢复断点", info_msg)
        if result:
            # 通知主窗口进行恢复
            if hasattr(self, 'master') and hasattr(self.master, '_on_resume_from_control_panel'):
                self.master._on_resume_from_control_panel(data)
    

# =============================================================================
# 实时统计显示
# =============================================================================
class StatsDisplay(tk.Frame):
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=Colors.SURFACE, **kwargs)
        
        self._create_widgets()
    
    def _create_widgets(self):
        """创建界面组件"""
        # 标题
        title = tk.Label(
            self, text="实时统计", font=("Microsoft YaHei", 11, "bold"),
            bg=Colors.SURFACE, fg=Colors.ACCENT
        )
        title.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        # 统计信息框架
        stats_frame = tk.Frame(self, bg=Colors.SURFACE)
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 第一行: 已检测 | 速度
        row1 = tk.Frame(stats_frame, bg=Colors.SURFACE)
        row1.pack(fill=tk.X, pady=2)
        
        checked_label = tk.Label(
            row1, text="已检测:", font=("Microsoft YaHei", 10),
            bg=Colors.SURFACE, fg=Colors.FG, width=8, anchor=tk.W
        )
        checked_label.pack(side=tk.LEFT)
        
        self.lbl_checked = tk.Label(
            row1, text="0", font=("Consolas", 10),
            bg=Colors.SURFACE, fg=Colors.INFO, width=15, anchor=tk.W
        )
        self.lbl_checked.pack(side=tk.LEFT)
        
        speed_label = tk.Label(
            row1, text="速度:", font=("Microsoft YaHei", 10),
            bg=Colors.SURFACE, fg=Colors.FG, width=6, anchor=tk.W
        )
        speed_label.pack(side=tk.LEFT, padx=(20, 0))
        
        self.lbl_speed = tk.Label(
            row1, text="0/s", font=("Consolas", 10),
            bg=Colors.SURFACE, fg=Colors.SUCCESS, width=15, anchor=tk.W
        )
        self.lbl_speed.pack(side=tk.LEFT)
        
        # 第二行: 运行时间 | 匹配数
        row2 = tk.Frame(stats_frame, bg=Colors.SURFACE)
        row2.pack(fill=tk.X, pady=2)
        
        elapsed_label = tk.Label(
            row2, text="运行时间:", font=("Microsoft YaHei", 10),
            bg=Colors.SURFACE, fg=Colors.FG, width=8, anchor=tk.W
        )
        elapsed_label.pack(side=tk.LEFT)
        
        self.lbl_elapsed = tk.Label(
            row2, text="00:00:00", font=("Consolas", 10),
            bg=Colors.SURFACE, fg=Colors.INFO, width=15, anchor=tk.W
        )
        self.lbl_elapsed.pack(side=tk.LEFT)
        
        match_label = tk.Label(
            row2, text="匹配数:", font=("Microsoft YaHei", 10),
            bg=Colors.SURFACE, fg=Colors.FG, width=6, anchor=tk.W
        )
        match_label.pack(side=tk.LEFT, padx=(20, 0))
        
        self.lbl_matches = tk.Label(
            row2, text="0", font=("Consolas", 10),
            bg=Colors.SURFACE, fg=Colors.ACCENT, width=15, anchor=tk.W
        )
        self.lbl_matches.pack(side=tk.LEFT)
        
        # 第三行: 进度百分比 | ETA（仅范围模式显示）
        row3 = tk.Frame(stats_frame, bg=Colors.SURFACE)
        row3.pack(fill=tk.X, pady=2)
        
        progress_label = tk.Label(
            row3, text="进度:", font=("Microsoft YaHei", 10),
            bg=Colors.SURFACE, fg=Colors.FG, width=8, anchor=tk.W
        )
        progress_label.pack(side=tk.LEFT)
        
        self.lbl_progress = tk.Label(
            row3, text="-", font=("Consolas", 10),
            bg=Colors.SURFACE, fg=Colors.INFO, width=15, anchor=tk.W
        )
        self.lbl_progress.pack(side=tk.LEFT)
        
        eta_label = tk.Label(
            row3, text="ETA:", font=("Microsoft YaHei", 10),
            bg=Colors.SURFACE, fg=Colors.FG, width=6, anchor=tk.W
        )
        eta_label.pack(side=tk.LEFT, padx=(20, 0))
        
        self.lbl_eta = tk.Label(
            row3, text="-", font=("Consolas", 10),
            bg=Colors.SURFACE, fg=Colors.ACCENT, width=15, anchor=tk.W
        )
        self.lbl_eta.pack(side=tk.LEFT)
        
        # 状态标签
        self.lbl_status = tk.Label(
            self, text="状态: 就绪", font=("Microsoft YaHei", 10, "bold"),
            bg=Colors.SURFACE, fg=Colors.INFO
        )
        self.lbl_status.pack(anchor=tk.W, padx=10, pady=(5, 5))
        
        # 断点状态显示（新增）
        checkpoint_frame = tk.Frame(self, bg=Colors.SURFACE)
        checkpoint_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        checkpoint_label = tk.Label(
            checkpoint_frame, text="断点:", font=("Microsoft YaHei", 10),
            bg=Colors.SURFACE, fg=Colors.FG, width=8, anchor=tk.W
        )
        checkpoint_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.lbl_checkpoint = tk.Label(
            checkpoint_frame, text="无断点", font=("Consolas", 10),
            bg=Colors.SURFACE, fg=Colors.INFO, anchor=tk.W
        )
        self.lbl_checkpoint.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 初始化时检查断点状态
        self._update_checkpoint_status()
    
    def update_stats(self, stats: CollisionStats):
        """更新统计数据"""
        self.lbl_checked.config(text=f"{stats.total_checked:,}")
        self.lbl_speed.config(text=stats.format_speed())
        self.lbl_elapsed.config(text=stats.format_elapsed())
        self.lbl_matches.config(text=str(len(stats.matches)))
        
        # 进度和 ETA（仅范围模式有效）
        if hasattr(stats, 'total_range') and stats.total_range > 0:
            pct = stats.total_checked / stats.total_range * 100
            self.lbl_progress.config(text=f"{pct:.2f}%")
            if hasattr(stats, 'eta_seconds') and stats.eta_seconds >= 0:
                eta = stats.eta_seconds
                if eta >= 3600:
                    eta_str = f"{eta/3600:.1f}h"
                elif eta >= 60:
                    eta_str = f"{eta/60:.1f}m"
                else:
                    eta_str = f"{eta:.0f}s"
                self.lbl_eta.config(text=eta_str)
            else:
                self.lbl_eta.config(text="计算中...")
        else:
            self.lbl_progress.config(text="-")
            self.lbl_eta.config(text="-")
    
    def set_status(self, status: str, status_type: str = "info"):
        """设置状态文字
        
        Args:
            status: 状态文字
            status_type: info/success/error/warning
        """
        self.lbl_status.config(text=f"状态: {status}")
        
        if status_type == "success":
            self.lbl_status.config(fg=Colors.SUCCESS)
        elif status_type == "error":
            self.lbl_status.config(fg=Colors.ERROR)
        elif status_type == "warning":
            self.lbl_status.config(fg=Colors.ACCENT)
        else:
            self.lbl_status.config(fg=Colors.INFO)
    
    def reset(self):
        """重置统计"""
        self.lbl_checked.config(text="0")
        self.lbl_speed.config(text="0/s")
        self.lbl_elapsed.config(text="00:00:00")
        self.lbl_matches.config(text="0")
        self.lbl_progress.config(text="-")
        self.lbl_eta.config(text="-")
        self.set_status("就绪", "info")
        self._update_checkpoint_status()
    
    def _update_checkpoint_status(self):
        """更新断点状态显示"""
        from src.collision.checkpoint_manager import CheckpointManager
        
        mgr = CheckpointManager()
        
        # 检查断点文件是否存在
        if not mgr.exists():
            self.lbl_checkpoint.config(text="无断点", fg=Colors.INFO)
            return
        
        # 加载断点数据
        data = mgr.load()
        if not data:
            self.lbl_checkpoint.config(text="✗ 断点文件无效", fg=Colors.ERROR)
            return
        
        # 数据有效，显示断点信息
        total_checked = data.get("total_checked", 0)
        mode = data.get("mode", "random")
        timestamp = data.get("timestamp", "")
        
        # 使用工具函数格式化
        mode_cn = format_mode_name(mode)
        time_str = format_timestamp(timestamp) or ""
        
        self.lbl_checkpoint.config(
            text=f"✓ {format_number_with_commas(total_checked)} 次 | 模式:{mode_cn} | {time_str}",
            fg=Colors.SUCCESS
        )


# =============================================================================
# 日志/结果区
# =============================================================================
class ResultLogFrame(tk.Frame):
    """日志/结果区组件"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=Colors.SURFACE, **kwargs)
        
        self._create_widgets()
    
    def _create_widgets(self):
        """创建界面组件"""
        # 标题
        title = tk.Label(
            self, text="日志/结果", font=("Microsoft YaHei", 11, "bold"),
            bg=Colors.SURFACE, fg=Colors.ACCENT
        )
        title.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(
            self, height=COMPONENT_CONFIG["log_frame"]["height"], 
            font=COMPONENT_CONFIG["log_frame"]["font"],
            bg=Colors.TEXT_BG, fg=Colors.TEXT_FG,
            relief=tk.FLAT, state=tk.DISABLED,
            highlightbackground=Colors.BUTTON_BG,
            highlightcolor=Colors.ACCENT, highlightthickness=1
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 配置标签样式
        self.log_text.tag_configure("match", foreground=Colors.ACCENT, font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("error", foreground=Colors.ERROR)
        self.log_text.tag_configure("success", foreground=Colors.SUCCESS)
        self.log_text.tag_configure("info", foreground=Colors.INFO)
        
        # 按钮区
        btn_frame = tk.Frame(self, bg=Colors.SURFACE)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.btn_export = tk.Button(
            btn_frame, text="导出日志", font=("Microsoft YaHei", 9),
            bg=Colors.BUTTON_BG, fg=Colors.FG, activebackground=Colors.BUTTON_HOVER,
            activeforeground=Colors.FG, relief=tk.FLAT, cursor="hand2",
            command=self._on_export
        )
        self.btn_export.pack(side=tk.LEFT)
    
    def log(self, message: str, tag: str = None):
        """添加日志消息"""
        self.log_text.config(state=tk.NORMAL)
        timestamp = time.strftime("%H:%M:%S")
        if tag:
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
        else:
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def log_match(self, private_key: bytes, address: str, wif: str):
        """记录匹配结果（高亮显示）- 显示完整信息"""
        self.log_text.config(state=tk.NORMAL)
        timestamp = time.strftime("%H:%M:%S")
        
        # 获取完整私钥Hex
        pk_hex = private_key.hex()
        
        # 插入空行作为分隔
        self.log_text.insert(tk.END, "\n")
        
        # 匹配标题（高亮）
        self.log_text.insert(tk.END, f"[{timestamp}] ", "info")
        self.log_text.insert(tk.END, "★★★ 发现匹配! ★★★\n", "match")
        
        # 地址信息
        self.log_text.insert(tk.END, f"[{timestamp}] ", "info")
        self.log_text.insert(tk.END, f"地址: {address}\n", "match")
        
        # 私钥Hex（完整显示）
        self.log_text.insert(tk.END, f"[{timestamp}] ", "info")
        self.log_text.insert(tk.END, f"私钥: {pk_hex}\n", "match")
        
        # WIF格式（完整显示）
        self.log_text.insert(tk.END, f"[{timestamp}] ", "info")
        self.log_text.insert(tk.END, f"WIF:  {wif}\n", "match")
        
        # 分隔线
        self.log_text.insert(tk.END, f"[{timestamp}] ", "info")
        self.log_text.insert(tk.END, "-" * 50 + "\n", "info")
        
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def log_error(self, message: str):
        """记录错误消息"""
        self.log(message, "error")
    
    def log_success(self, message: str):
        """记录成功消息"""
        self.log(message, "success")
    
    def _on_export(self):
        """导出日志按钮回调"""
        filepath = filedialog.asksaveasfilename(
            title="导出日志",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if filepath:
            try:
                self.log_text.config(state=tk.NORMAL)
                content = self.log_text.get('1.0', tk.END)
                self.log_text.config(state=tk.DISABLED)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                try:
                    os.chmod(filepath, 0o600)
                except OSError:
                    pass
                
                self.log_success(f"日志已导出到: {filepath}")
            except Exception as e:
                self.log_error(f"导出失败: {str(e)}")
    
    def clear(self):
        """清空日志"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state=tk.DISABLED)


# =============================================================================
# 主 GUI 类
# =============================================================================
class CollisionGUI:
    """比特币私钥对撞工具 GUI"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(WINDOW_CONFIG["title"])
        self.root.geometry(f"{WINDOW_CONFIG['default_width']}x{WINDOW_CONFIG['default_height']}")
        self.root.configure(bg=Colors.BG)
        
        # 设置窗口最小尺寸
        self.root.minsize(WINDOW_CONFIG["min_width"], WINDOW_CONFIG["min_height"])
        
        # 初始化组件
        self.resolver = TargetResolver()
        self.engine = None
        self._is_cleaning_up = False  # 资源清理标志（防止重复清理）
        
        self._create_widgets()
        self._setup_bindings()
        
        # 启动定时器更新统计
        self._schedule_stats_update()
    
    def _create_widgets(self):
        """创建界面组件"""
        # 主容器
        main_container = tk.Frame(self.root, bg=Colors.BG)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 标题栏
        title_frame = tk.Frame(main_container, bg=Colors.BG)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        title = tk.Label(
            title_frame, text="BTC 私钥对撞工具 v1.0",
            font=("Microsoft YaHei", 16, "bold"),
            bg=Colors.BG, fg=Colors.ACCENT
        )
        title.pack()
        
        # 目标地址输入区
        self.target_frame = TargetInputFrame(main_container, self.resolver, gui_app=self)
        self.target_frame.pack(fill=tk.X, pady=5)
        
        # 控制面板
        self.control_panel = ControlPanel(main_container, on_mode_change=self._on_mode_change)
        self.control_panel.pack(fill=tk.X, pady=5)
        
        # 实时统计
        self.stats_display = StatsDisplay(main_container)
        self.stats_display.pack(fill=tk.X, pady=5)
        
        # 日志/结果区
        self.log_frame = ResultLogFrame(main_container)
        self.log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 绑定控制按钮
        self.control_panel.btn_start.config(command=self._on_start)
        self.control_panel.btn_stop.config(command=self._on_stop)
        self.control_panel.btn_resume.config(command=self._on_resume)
    
    def _setup_bindings(self):
        """设置事件绑定"""
        # 窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_mode_change(self, mode: str):
        """模式改变回调"""
        self.log_frame.log(f"切换模式: {mode}")
    
    
    def _on_start(self):
        """开始对撞按钮回调"""
        # 获取目标地址
        targets = self.target_frame.get_targets()
        if not targets:
            messagebox.showwarning("警告", "请先设置目标地址")
            return
        
        # 获取模式
        mode = self.control_panel.get_mode()
        
        # 获取范围参数（如果需要）
        kwargs = {}
        if mode in ("range", "brute_force"):
            start, end = self.control_panel.get_range_params()
            if start is None:
                messagebox.showerror("错误", "无效的起始值，请输入有效的十六进制数值")
                return
            kwargs['start'] = start
            if mode == "range":
                if end is None:
                    messagebox.showerror("错误", "无效的结束值，请输入有效的十六进制数值")
                    return
                kwargs['end'] = end
        
        # 读取高级选项
        checkpoint_enabled = self.control_panel.checkpoint_var.get()
        dedup_enabled = self.control_panel.dedup_var.get()
        use_gpu = self.control_panel.use_gpu()
        gpu_device_index = self.control_panel.get_gpu_device_index()
        
        # 如果启用了断点续传，检查是否存在断点文件
        if checkpoint_enabled:
            from src.collision.checkpoint_manager import CheckpointManager
            mgr = CheckpointManager()
            if mgr.exists():
                data = mgr.load()
                if data:
                    mode = data.get("mode", "random")
                    total_checked = data.get("total_checked", 0)
                    timestamp = data.get("timestamp", "未知")
                    
                    info_msg = f"检测到现有断点:\n"
                    info_msg += f"模式: {mode}\n"
                    info_msg += f"已检测: {total_checked:,}\n"
                    info_msg += f"保存时间: {timestamp}\n\n"
                    info_msg += "是否从断点继续？\n\n"
                    info_msg += "选择【是】从断点继续\n"
                    info_msg += "选择【否】开始新的对撞（断点文件将被覆盖）"
                    
                    result = messagebox.askyesno("断点续传", info_msg)
                    if result:
                        # 用户选择从断点继续
                        self._on_resume_from_control_panel(data)
                        return
                    # 如果选择否，继续执行新的对撞，断点文件将被覆盖
        
        # 根据用户选择创建引擎
        from src.collision import create_collision_engine, GPUCollisionEngine
        try:
            if use_gpu:
                # 用户选择使用 GPU
                self.engine = create_collision_engine(
                    targets=targets,
                    mode='gpu',  # 强制使用 GPU
                    device_index=gpu_device_index,
                    on_progress=self._on_progress,
                    on_match=self._on_match,
                    on_complete=self._on_complete,
                    checkpoint_enabled=checkpoint_enabled,
                    dedup_enabled=dedup_enabled
                )
                actual_mode = "GPU"
                device_info = self.engine.get_device_info()
                device_name = device_info.get('name', 'Unknown')
                self.log_frame.log(f"GPU 检测成功: {device_name}")
            else:
                # 用户选择使用 CPU
                self.engine = create_collision_engine(
                    targets=targets,
                    mode='cpu',  # 强制使用 CPU
                    on_progress=self._on_progress,
                    on_match=self._on_match,
                    on_complete=self._on_complete,
                    checkpoint_enabled=checkpoint_enabled,
                    dedup_enabled=dedup_enabled
                )
                actual_mode = "CPU"
        except Exception as e:
            # 如果创建 GPU 引擎失败，回退到 CPU 引擎
            self.log_frame.log(f"GPU 引擎初始化失败: {e}，使用 CPU 引擎")
            self.engine = KeyCollisionEngine(
                targets=targets,
                on_progress=self._on_progress,
                on_match=self._on_match,
                on_complete=self._on_complete,
                checkpoint_enabled=checkpoint_enabled,
                dedup_enabled=dedup_enabled
            )
            actual_mode = "CPU"
        
        # 更新UI状态
        self.control_panel.set_buttons_state(True)
        self.target_frame.set_enabled(False)
        self.stats_display.reset()
        self.stats_display.set_status("运行中...", "info")
        
        # 记录开始日志
        self.log_frame.log(f"开始对撞 | 模式: {mode} | 引擎: {actual_mode} | 目标数: {len(targets)}")
        
        # 记录选项状态
        opts = []
        if checkpoint_enabled:
            opts.append("断点续传")
        if dedup_enabled:
            opts.append("去重过滤")
        if opts:
            self.log_frame.log(f"已启用: {', '.join(opts)}")
        if mode == "range":
            self.log_frame.log(f"范围: {kwargs['start']} - {kwargs['end']} (十六进制)")
        elif mode == "brute_force":
            self.log_frame.log(f"起始: {kwargs['start']} (十六进制)")
        
        # 启动引擎
        self.engine.start(mode=mode, **kwargs)
    
    def _on_stop(self):
        """停止按钮回调"""
        if self.engine:
            # 保存引擎引用，避免竞态条件
            engine_to_stop = self.engine
            
            # 禁用停止按钮防止重复点击
            self.control_panel.btn_stop.config(state=tk.DISABLED)
            self.log_frame.log("正在停止对撞引擎...")
            
            # 在后台线程中执行停止操作，避免阻塞 UI
            def stop_engine_bg():
                try:
                    engine_to_stop.stop()  # 使用局部引用，避免竞态条件
                    # 停止完成后，在主线程中更新 UI
                    self.root.after(0, self._on_stop_complete)
                except Exception as e:
                    # 立即捕获错误消息，避免闭包变量问题
                    error_msg = str(e)
                    self.root.after(0, lambda msg=error_msg: self.log_frame.log(f"停止引擎时出错: {msg}"))
                    self.root.after(0, self._on_stop_complete)
            
            stop_thread = threading.Thread(target=stop_engine_bg, daemon=True)
            stop_thread.start()
    
    def _on_stop_complete(self):
        """停止完成后的 UI 更新"""
        self.log_frame.log("对撞引擎已停止")
        self.control_panel.set_buttons_state(False)
        self.target_frame.set_enabled(True)
        self.stats_display.set_status("已停止", "warning")
        self.log_frame.log("界面状态已恢复")
    
    def _on_resume_from_control_panel(self, checkpoint_data: dict):
        """从控制面板恢复断点"""
        # 恢复目标地址
        targets = set(checkpoint_data.get("targets", []))
        if not targets:
            messagebox.showerror("错误", "断点中无目标地址")
            return
        
        mode = checkpoint_data.get("mode", "random")
        
        # 读取高级选项
        dedup_enabled = self.control_panel.dedup_var.get()
        use_gpu = self.control_panel.use_gpu()
        gpu_device_index = self.control_panel.get_gpu_device_index()
        
        # 根据用户选择创建引擎
        from src.collision import create_collision_engine
        try:
            if use_gpu:
                # 用户选择使用 GPU
                self.engine = create_collision_engine(
                    targets=targets,
                    mode='gpu',  # 强制使用 GPU
                    device_index=gpu_device_index,
                    on_progress=self._on_progress,
                    on_match=self._on_match,
                    on_complete=self._on_complete,
                    checkpoint_enabled=True,  # 恢复断点时总是启用
                    dedup_enabled=dedup_enabled
                )
                actual_mode = "GPU"
                device_info = self.engine.get_device_info()
                device_name = device_info.get('name', 'Unknown')
                self.log_frame.log(f"GPU 检测成功: {device_name}")
            else:
                # 用户选择使用 CPU
                self.engine = create_collision_engine(
                    targets=targets,
                    mode='cpu',  # 强制使用 CPU
                    on_progress=self._on_progress,
                    on_match=self._on_match,
                    on_complete=self._on_complete,
                    checkpoint_enabled=True,  # 恢复断点时总是启用
                    dedup_enabled=dedup_enabled
                )
                actual_mode = "CPU"
        except Exception as e:
            # 如果创建 GPU 引擎失败，回退到 CPU 引擎
            self.log_frame.log(f"GPU 引擎初始化失败: {e}，使用 CPU 引擎")
            self.engine = KeyCollisionEngine(
                targets=targets,
                on_progress=self._on_progress,
                on_match=self._on_match,
                on_complete=self._on_complete,
                checkpoint_enabled=True,  # 恢复断点时总是启用
                dedup_enabled=dedup_enabled
            )
            actual_mode = "CPU"
        
        # 更新UI状态
        self.control_panel.set_buttons_state(True)
        self.target_frame.set_enabled(False)
        self.stats_display.reset()
        self.stats_display.set_status("恢复中...", "info")
        
        total_checked = checkpoint_data.get('total_checked', 0)
        self.log_frame.log(f"从断点恢复 | 模式: {mode} | 引擎: {actual_mode} | 已检测: {total_checked:,}")
        
        # 使用 resume 启动引擎
        self.engine.start(mode=mode, resume=True)
    
    def _on_resume(self):
        """恢复断点按钮回调（兼容旧版）"""
        self.control_panel._on_resume_checkpoint()
    
    def _on_progress(self, stats: CollisionStats):
        """进度回调（在后台线程中调用，需要调度到主线程）"""
        self.root.after(0, lambda: self._update_progress_ui(stats))
    
    def _update_progress_ui(self, stats: CollisionStats):
        """在主线程更新进度UI"""
        self.stats_display.update_stats(stats)
    
    def _on_match(self, private_key: bytes, address: str, wif: str):
        """匹配回调（在后台线程中调用，需要调度到主线程）"""
        self.root.after(0, lambda: self._update_match_ui(private_key, address, wif))
    
    def _update_match_ui(self, private_key: bytes, address: str, wif: str):
        """在主线程更新匹配UI"""
        self.log_frame.log_match(private_key, address, wif)
        self.stats_display.set_status("发现匹配!", "success")
    
    def _on_complete(self, stats: CollisionStats):
        """完成回调（在后台线程中调用，需要调度到主线程）"""
        self.root.after(0, lambda: self._update_complete_ui(stats))
    
    def _update_complete_ui(self, stats: CollisionStats):
        """在主线程更新完成UI"""
        self.control_panel.set_buttons_state(False)
        self.target_frame.set_enabled(True)
        
        if stats.matches:
            self.stats_display.set_status(f"完成! 发现 {len(stats.matches)} 个匹配", "success")
            self.log_frame.log_success(f"对撞完成! 共发现 {len(stats.matches)} 个匹配")
        else:
            self.stats_display.set_status("已停止", "warning")
            self.log_frame.log("对撞已停止，未发现匹配")
        
        # 更新最终统计
        self.stats_display.update_stats(stats)
    
    def _schedule_stats_update(self):
        """定时更新统计数据"""
        if self.engine and self.engine.is_running():
            stats = self.engine.get_stats()
            self.stats_display.update_stats(stats)
        
        # 100ms后再次调用
        self.root.after(100, self._schedule_stats_update)
    
    def _on_close(self):
        """窗口关闭回调 - 增强资源清理版本"""
        if self.engine and self.engine.is_running():
            if messagebox.askyesno("确认", "对撞正在进行中，确定要退出吗?"):
                # 异步停止引擎，完成后关闭窗口，避免 UI 阻塞
                self.log_frame.log("正在停止引擎并关闭窗口...")
                
                # 保存引擎引用，避免竞态条件
                engine_to_stop = self.engine
                
                def stop_and_close():
                    try:
                        # 1. 停止引擎（会清理所有内部资源）
                        engine_to_stop.stop()
                        
                        # 2. 在主线程中完成清理
                        self.root.after(0, self._cleanup_and_destroy)
                    except Exception as e:
                        error_msg = str(e)
                        self.root.after(0, lambda msg=error_msg: self.log_frame.log(f"停止失败: {msg}"))
                        self.root.after(0, self._cleanup_and_destroy)
                
                stop_thread = threading.Thread(target=stop_and_close, daemon=True)
                stop_thread.start()
                return  # 不立即销毁，等待后台线程完成
        else:
            # 引擎未运行或不存在，直接清理
            self._cleanup_and_destroy()
    
    def _cleanup_and_destroy(self):
        """清理所有资源并销毁窗口"""
        # 防止重复清理
        if self._is_cleaning_up:
            return
        
        self._is_cleaning_up = True
        
        try:
            # 1. 显式清理引擎引用（允许垃圾回收）
            if self.engine:
                self.log_frame.log("清理引擎资源...")
                self.engine = None
            
            # 2. 清理监控系统（如果存在）
            if hasattr(self, 'stats_display'):
                self.log_frame.log("清理显示组件...")
            
            # 3. 最后一条日志（必须在 shutdown 之前）
            self.log_frame.log("资源清理完成，关闭窗口...")
            
            # 4. 刷新日志系统（必须在最后，之后不能再写日志）
            logging.shutdown()
            
        except Exception as e:
            print(f"清理过程出错: {e}")
        finally:
            # 5. 销毁窗口（无论如何都要执行）
            self.root.destroy()


# =============================================================================
# 程序入口
# =============================================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = CollisionGUI(root)
    root.mainloop()
