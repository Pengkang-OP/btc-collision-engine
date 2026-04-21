# -*- coding: utf-8 -*-
"""多GPU监控面板GUI组件

实时显示多个GPU的状态、性能和进度。
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional
from datetime import datetime


class MultiGPUMonitorPanel(ttk.Frame):
    """多GPU监控面板
    
    功能:
    - 显示每个GPU的实时状态
    - 显示吞吐量、显存使用
    - 进度条可视化
    - 汇总统计信息
    """
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.gpu_frames = {}
        self.total_throughput = 0
        self.total_keys = 0
        
        self._create_widgets()
    
    def _create_widgets(self):
        """创建界面组件"""
        # 标题
        title_frame = ttk.Frame(self)
        title_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(
            title_frame,
            text="📊 多GPU实时监控",
            font=('Microsoft YaHei', 11, 'bold')
        ).pack(anchor=tk.W)
        
        # GPU状态容器
        self.gpu_container = ttk.Frame(self)
        self.gpu_container.pack(fill=tk.X, pady=5)
        
        # 汇总信息
        summary_frame = ttk.LabelFrame(self, text="汇总统计", padding=5)
        summary_frame.pack(fill=tk.X, pady=5)
        
        # 总吞吐量
        ttk.Label(summary_frame, text="总吞吐量:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.total_throughput_label = ttk.Label(
            summary_frame,
            text="0 keys/s",
            font=('Consolas', 10, 'bold'),
            foreground='#4CAF50'
        )
        self.total_throughput_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        # 总检查数
        ttk.Label(summary_frame, text="已检查:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.total_keys_label = ttk.Label(
            summary_frame,
            text="0",
            font=('Consolas', 10)
        )
        self.total_keys_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        # GPU数量
        ttk.Label(summary_frame, text="活跃GPU:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.active_gpu_label = ttk.Label(
            summary_frame,
            text="0",
            font=('Consolas', 10)
        )
        self.active_gpu_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        # 运行时间
        ttk.Label(summary_frame, text="运行时间:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        self.elapsed_label = ttk.Label(
            summary_frame,
            text="00:00:00",
            font=('Consolas', 10)
        )
        self.elapsed_label.grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
        
        # 状态标签
        self.status_label = ttk.Label(
            summary_frame,
            text="● 已停止",
            font=('Microsoft YaHei', 10, 'bold'),
            foreground='#F44336'
        )
        self.status_label.grid(row=0, column=2, rowspan=4, padx=20)
    
    def update_gpu_status(self, device_idx: int, stats: Dict):
        """更新单个GPU的状态
        
        Args:
            device_idx: GPU设备索引
            stats: 统计信息
        """
        # 创建或更新GPU框架
        if device_idx not in self.gpu_frames:
            self._create_gpu_frame(device_idx, stats)
        else:
            self._update_gpu_frame(device_idx, stats)
        
        # 更新汇总信息
        self._update_summary()
    
    def _create_gpu_frame(self, device_idx: int, stats: Dict):
        """创建GPU状态框架
        
        Args:
            device_idx: GPU设备索引
            stats: 统计信息
        """
        frame = ttk.LabelFrame(
            self.gpu_container,
            text=f"GPU {device_idx}",
            padding=5
        )
        frame.pack(fill=tk.X, pady=2)
        
        # 设备名称
        name_label = ttk.Label(
            frame,
            text=stats.get('device_name', 'Unknown'),
            font=('Microsoft YaHei', 9, 'bold')
        )
        name_label.grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        
        # 状态
        status_label = ttk.Label(frame, text="● 运行中", foreground='#4CAF50')
        status_label.grid(row=0, column=1, padx=10, pady=2)
        
        # 吞吐量
        ttk.Label(frame, text="吞吐量:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        throughput_label = ttk.Label(
            frame,
            text=f"{stats.get('throughput', 0):,.0f} keys/s",
            font=('Consolas', 9),
            foreground='#2196F3'
        )
        throughput_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        # 已检查数量
        ttk.Label(frame, text="已检查:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        keys_label = ttk.Label(
            frame,
            text=f"{stats.get('keys_checked', 0):,}",
            font=('Consolas', 9)
        )
        keys_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        # 进度条
        ttk.Label(frame, text="进度:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        progress = ttk.Progressbar(frame, length=200, mode='determinate')
        progress.grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
        
        # 保存组件引用
        self.gpu_frames[device_idx] = {
            'frame': frame,
            'name_label': name_label,
            'status_label': status_label,
            'throughput_label': throughput_label,
            'keys_label': keys_label,
            'progress': progress
        }
    
    def _update_gpu_frame(self, device_idx: int, stats: Dict):
        """更新GPU状态框架
        
        Args:
            device_idx: GPU设备索引
            stats: 统计信息
        """
        if device_idx not in self.gpu_frames:
            return
        
        frame_data = self.gpu_frames[device_idx]
        
        # 更新状态
        status = stats.get('status', 'unknown')
        if status == 'running':
            frame_data['status_label'].config(text="● 运行中", foreground='#4CAF50')
        elif status == 'paused':
            frame_data['status_label'].config(text="● 已暂停", foreground='#FF9800')
        elif status == 'stopped':
            frame_data['status_label'].config(text="● 已停止", foreground='#F44336')
        elif status == 'error':
            frame_data['status_label'].config(text="● 错误", foreground='#F44336')
        
        # 更新吞吐量
        throughput = stats.get('throughput', 0)
        frame_data['throughput_label'].config(text=f"{throughput:,.0f} keys/s")
        
        # 更新已检查数量
        keys = stats.get('keys_checked', 0)
        frame_data['keys_label'].config(text=f"{keys:,}")
        
        # 更新进度条(假设目标为10M keys)
        progress_value = min(keys / 10000000 * 100, 100)
        frame_data['progress']['value'] = progress_value
    
    def _update_summary(self):
        """更新汇总统计"""
        total_throughput = 0
        total_keys = 0
        active_count = 0
        
        for device_idx, frame_data in self.gpu_frames.items():
            # 从标签文本中提取数值
            try:
                throughput_text = frame_data['throughput_label']['text']
                throughput = float(throughput_text.replace(' keys/s', '').replace(',', ''))
                total_throughput += throughput
            except:
                pass
            
            try:
                keys_text = frame_data['keys_label']['text']
                keys = int(keys_text.replace(',', ''))
                total_keys += keys
            except:
                pass
            
            status_text = frame_data['status_label']['text']
            if '运行中' in status_text:
                active_count += 1
        
        # 更新标签
        self.total_throughput_label.config(text=f"{total_throughput:,.0f} keys/s")
        self.total_keys_label.config(text=f"{total_keys:,}")
        self.active_gpu_label.config(text=str(active_count))
        
        self.total_throughput = total_throughput
        self.total_keys = total_keys
    
    def set_running(self, is_running: bool):
        """设置运行状态
        
        Args:
            is_running: 是否正在运行
        """
        if is_running:
            self.status_label.config(text="● 运行中", foreground='#4CAF50')
        else:
            self.status_label.config(text="● 已停止", foreground='#F44336')
    
    def update_elapsed_time(self, elapsed_seconds: float):
        """更新运行时间
        
        Args:
            elapsed_seconds: 运行秒数
        """
        hours = int(elapsed_seconds // 3600)
        minutes = int((elapsed_seconds % 3600) // 60)
        seconds = int(elapsed_seconds % 60)
        
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self.elapsed_label.config(text=time_str)
    
    def clear(self):
        """清空所有GPU状态"""
        for device_idx in list(self.gpu_frames.keys()):
            if device_idx in self.gpu_frames:
                self.gpu_frames[device_idx]['frame'].destroy()
                del self.gpu_frames[device_idx]
        
        self.total_throughput = 0
        self.total_keys = 0
        
        self.total_throughput_label.config(text="0 keys/s")
        self.total_keys_label.config(text="0")
        self.active_gpu_label.config(text="0")
        self.elapsed_label.config(text="00:00:00")
        self.status_label.config(text="● 已停止", foreground='#F44336')
