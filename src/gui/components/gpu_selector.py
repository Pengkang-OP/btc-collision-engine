# -*- coding: utf-8 -*-
"""GPU选择面板GUI组件

提供GPU设备选择、模式切换和配置应用功能。
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
from typing import Dict, List, Optional


class GPUSelectorPanel(ttk.Frame):
    """GPU选择面板
    
    功能:
    - GPU模式选择(auto/single/multi)
    - GPU设备列表和选择
    - 设备详细信息展示
    - 负载均衡策略选择
    - 配置应用
    """
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.selected_devices = []
        self.selected_mode = 'auto'
        self.selected_balancing = 'performance'
        self.on_apply_callback = None
        
        self._create_widgets()
        self._load_devices()
    
    def _create_widgets(self):
        """创建界面组件"""
        # 标题
        title_frame = ttk.Frame(self)
        title_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(
            title_frame,
            text="🎮 GPU设备选择",
            font=('Microsoft YaHei', 11, 'bold')
        ).pack(anchor=tk.W)
        
        # GPU模式选择
        mode_frame = ttk.LabelFrame(self, text="GPU模式", padding=5)
        mode_frame.pack(fill=tk.X, pady=5)
        
        self.mode_var = tk.StringVar(value='auto')
        
        ttk.Radiobutton(
            mode_frame,
            text="自动选择最佳GPU",
            variable=self.mode_var,
            value='auto',
            command=self._on_mode_changed
        ).pack(anchor=tk.W)
        
        ttk.Radiobutton(
            mode_frame,
            text="单GPU模式",
            variable=self.mode_var,
            value='single',
            command=self._on_mode_changed
        ).pack(anchor=tk.W)
        
        ttk.Radiobutton(
            mode_frame,
            text="多GPU模式(异构并行)",
            variable=self.mode_var,
            value='multi',
            command=self._on_mode_changed
        ).pack(anchor=tk.W)
        
        # GPU设备列表
        device_frame = ttk.LabelFrame(self, text="可用GPU设备", padding=5)
        device_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 设备列表框
        list_frame = ttk.Frame(device_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建Listbox
        self.device_listbox = tk.Listbox(
            list_frame,
            height=6,
            font=('Consolas', 9),
            selectmode=tk.MULTIPLE
        )
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.device_listbox.yview)
        self.device_listbox.config(yscrollcommand=scrollbar.set)
        
        self.device_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定选择事件
        self.device_listbox.bind('<<ListboxSelect>>', self._on_device_selected)
        
        # 设备详细信息
        detail_frame = ttk.LabelFrame(device_frame, text="设备详细信息", padding=5)
        detail_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.device_info_text = scrolledtext.ScrolledText(
            detail_frame,
            height=8,
            font=('Consolas', 9),
            state=tk.DISABLED
        )
        self.device_info_text.pack(fill=tk.X)
        
        # 负载均衡策略
        balance_frame = ttk.Frame(self)
        balance_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(balance_frame, text="负载均衡策略:").pack(side=tk.LEFT)
        
        self.balancing_var = tk.StringVar(value='performance')
        balancing_combo = ttk.Combobox(
            balance_frame,
            textvariable=self.balancing_var,
            values=['performance', 'equal'],
            state='readonly',
            width=20
        )
        balancing_combo.pack(side=tk.LEFT, padx=5)
        balancing_combo.bind('<<ComboboxSelected>>', self._on_balancing_changed)
        
        # 应用按钮
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, pady=5)
        
        self.apply_button = ttk.Button(
            button_frame,
            text="✓ 应用配置",
            command=self._on_apply
        )
        self.apply_button.pack(side=tk.RIGHT)
        
        self.refresh_button = ttk.Button(
            button_frame,
            text="🔄 刷新设备",
            command=self._load_devices
        )
        self.refresh_button.pack(side=tk.RIGHT, padx=5)
    
    def _load_devices(self):
        """加载GPU设备列表"""
        try:
            from src.gpu.selector import get_gpu_selector
            
            # 在新线程中加载,避免阻塞UI
            def load_thread():
                try:
                    selector = get_gpu_selector()
                    devices = selector.detect_all_devices(force_refresh=True)
                    
                    self.after(0, lambda: self._update_device_list(devices))
                except Exception as e:
                    self.after(0, lambda: self._show_error(f"设备检测失败: {e}"))
            
            thread = threading.Thread(target=load_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            self._show_error(f"加载设备失败: {e}")
    
    def _update_device_list(self, devices: List[Dict]):
        """更新设备列表UI
        
        Args:
            devices: 设备信息列表
        """
        self.device_listbox.delete(0, tk.END)
        
        if not devices:
            self.device_listbox.insert(tk.END, "未检测到GPU设备")
            self.selected_devices = []
            return
        
        # 按评分排序
        sorted_devices = sorted(devices, key=lambda d: d.get('score', 0), reverse=True)
        
        for device in sorted_devices:
            idx = device.get('global_index', -1)
            name = device.get('name', 'Unknown')
            vendor = device.get('vendor', 'unknown').upper()
            memory = device.get('global_mem_gb', 0)
            score = device.get('score', 0)
            
            display_text = f"GPU {idx}: {name} | {vendor} | {memory:.1f}GB | 评分:{score:.1f}"
            self.device_listbox.insert(tk.END, display_text)
        
        # 保存设备数据
        self.devices_data = sorted_devices
        
        # 自动选择第一个(最佳)设备
        if self.mode_var.get() == 'auto':
            self.device_listbox.selection_set(0)
            self.selected_devices = [sorted_devices[0]]
    
    def _on_device_selected(self, event):
        """设备选择事件"""
        selection = self.device_listbox.curselection()
        
        if not selection:
            return
        
        # 获取选中的设备
        self.selected_devices = []
        for idx in selection:
            if idx < len(self.devices_data):
                self.selected_devices.append(self.devices_data[idx])
        
        # 显示第一个选中设备的详细信息
        if self.selected_devices:
            self._show_device_detail(self.selected_devices[0])
    
    def _show_device_detail(self, device: Dict):
        """显示设备详细信息
        
        Args:
            device: 设备信息
        """
        self.device_info_text.config(state=tk.NORMAL)
        self.device_info_text.delete(1.0, tk.END)
        
        from src.gpu.selector import get_gpu_selector
        selector = get_gpu_selector()
        
        detail_text = selector.format_device_info(device, detailed=True)
        self.device_info_text.insert(tk.END, detail_text)
        
        self.device_info_text.config(state=tk.DISABLED)
    
    def _on_mode_changed(self):
        """GPU模式改变事件"""
        mode = self.mode_var.get()
        self.selected_mode = mode
        
        # 根据模式调整选择
        if mode == 'auto':
            self.device_listbox.selection_clear(0, tk.END)
            if hasattr(self, 'devices_data') and self.devices_data:
                self.device_listbox.selection_set(0)
                self.selected_devices = [self.devices_data[0]]
        
        elif mode == 'single':
            # 单GPU模式只能选一个
            selection = self.device_listbox.curselection()
            if len(selection) > 1:
                self.device_listbox.selection_clear(1, tk.END)
                self.selected_devices = [self.selected_devices[0]]
    
    def _on_balancing_changed(self, event=None):
        """负载均衡策略改变事件"""
        self.selected_balancing = self.balancing_var.get()
    
    def _on_apply(self):
        """应用配置按钮点击"""
        # 获取配置
        config = self.get_config()
        
        # 调用回调
        if self.on_apply_callback:
            try:
                self.on_apply_callback(config)
                messagebox.showinfo("成功", "GPU配置已应用!")
            except Exception as e:
                messagebox.showerror("错误", f"应用配置失败: {e}")
        else:
            messagebox.showinfo("提示", "未设置应用回调函数")
    
    def get_config(self) -> Dict:
        """获取当前配置
        
        Returns:
            配置字典
        """
        config = {
            'mode': self.selected_mode,
            'device_indices': [d['global_index'] for d in self.selected_devices],
            'load_balancing': self.selected_balancing,
            'auto_tuning': True
        }
        
        return config
    
    def set_apply_callback(self, callback):
        """设置应用回调函数
        
        Args:
            callback: 回调函数,接收config参数
        """
        self.on_apply_callback = callback
    
    def _show_error(self, message: str):
        """显示错误信息
        
        Args:
            message: 错误消息
        """
        self.device_listbox.delete(0, tk.END)
        self.device_listbox.insert(tk.END, f"错误: {message}")
        self.selected_devices = []
