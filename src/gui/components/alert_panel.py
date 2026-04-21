"""GUI告警显示面板组件

在GUI中显示实时告警信息,支持:
- 活动告警列表
- 告警级别颜色标识
- 告警详情查看
- 告警历史记录
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Any
from datetime import datetime

from src.monitoring.alert_system import AlertLevel, AlertType, get_alert_system


# 告警级别配色
ALERT_COLORS = {
    AlertLevel.INFO: "#4FC3F7",        # 蓝色
    AlertLevel.WARNING: "#FFB74D",     # 橙色
    AlertLevel.CRITICAL: "#EF5350",    # 红色
    AlertLevel.EMERGENCY: "#FF1744"    # 深红
}

# 告警类型中文映射
ALERT_TYPE_NAMES = {
    AlertType.PERFORMANCE_DEGRADATION: "性能退化",
    AlertType.MEMORY_OVERFLOW: "内存溢出",
    AlertType.GPU_OVERHEAT: "GPU过热",
    AlertType.ERROR_RATE_HIGH: "错误率高",
    AlertType.THROUGHPUT_DROP: "吞吐量下降",
    AlertType.SYSTEM_STABLE: "系统稳定"
}


class AlertPanel(tk.Frame):
    """告警显示面板"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg="#1E1E1E", **kwargs)
        
        # 告警系统
        self.alert_system = get_alert_system()
        
        # 告警更新定时器
        self._update_job = None
        
        self._create_widgets()
        self._start_auto_update()
    
    def _create_widgets(self):
        """创建界面组件"""
        # 标题栏
        title_frame = tk.Frame(self, bg="#1E1E1E")
        title_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        title = tk.Label(
            title_frame, 
            text="⚠️ 实时告警", 
            font=("Microsoft YaHei", 11, "bold"),
            bg="#1E1E1E", 
            fg="#FFB74D"
        )
        title.pack(anchor=tk.W)
        
        # 状态栏
        status_frame = tk.Frame(self, bg="#1E1E1E")
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_label = tk.Label(
            status_frame,
            text="活动告警: 0 | 总告警: 0",
            font=("Microsoft YaHei", 9),
            bg="#1E1E1E",
            fg="#9E9E9E"
        )
        self.status_label.pack(anchor=tk.W)
        
        # 告警列表(Treeview)
        list_frame = tk.Frame(self, bg="#1E1E1E")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建Treeview
        columns = ("time", "level", "type", "message")
        self.alert_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            height=10
        )
        
        # 设置列
        self.alert_tree.heading("time", text="时间")
        self.alert_tree.heading("level", text="级别")
        self.alert_tree.heading("type", text="类型")
        self.alert_tree.heading("message", text="消息")
        
        self.alert_tree.column("time", width=80, anchor=tk.CENTER)
        self.alert_tree.column("level", width=70, anchor=tk.CENTER)
        self.alert_tree.column("type", width=80, anchor=tk.CENTER)
        self.alert_tree.column("message", width=400, anchor=tk.W)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.alert_tree.yview)
        self.alert_tree.configure(yscrollcommand=scrollbar.set)
        
        self.alert_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定双击事件
        self.alert_tree.bind("<Double-1>", self._on_alert_double_click)
        
        # 按钮栏
        btn_frame = tk.Frame(self, bg="#1E1E1E")
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        btn_refresh = tk.Button(
            btn_frame,
            text="🔄 刷新",
            font=("Microsoft YaHei", 9),
            bg="#333333",
            fg="#FFFFFF",
            activebackground="#444444",
            command=self._refresh_alerts
        )
        btn_refresh.pack(side=tk.LEFT, padx=5)
        
        btn_clear = tk.Button(
            btn_frame,
            text="🗑️ 清空历史",
            font=("Microsoft YaHei", 9),
            bg="#333333",
            fg="#FFFFFF",
            activebackground="#444444",
            command=self._clear_history
        )
        btn_clear.pack(side=tk.LEFT, padx=5)
        
        btn_stats = tk.Button(
            btn_frame,
            text="📊 统计",
            font=("Microsoft YaHei", 9),
            bg="#333333",
            fg="#FFFFFF",
            activebackground="#444444",
            command=self._show_stats
        )
        btn_stats.pack(side=tk.LEFT, padx=5)
    
    def _start_auto_update(self):
        """启动自动更新(每5秒)"""
        self._refresh_alerts()
        self._update_job = self.after(5000, self._start_auto_update)
    
    def _refresh_alerts(self):
        """刷新告警列表"""
        try:
            # 清空列表
            for item in self.alert_tree.get_children():
                self.alert_tree.delete(item)
            
            # 获取所有告警(最近50条)
            all_alerts = self.alert_system.alert_history[-50:]
            
            # 插入告警
            for alert in reversed(all_alerts):  # 最新的在前
                # 格式化时间
                time_str = self._format_time(alert.timestamp)
                
                # 级别中文
                level_name = self._format_level(alert.level)
                
                # 类型中文
                type_name = ALERT_TYPE_NAMES.get(alert.alert_type, alert.alert_type.value)
                
                # 插入行
                item_id = self.alert_tree.insert("", tk.END, values=(
                    time_str,
                    level_name,
                    type_name,
                    alert.message
                ))
                
                # 设置颜色标签
                color = ALERT_COLORS.get(alert.level, "#9E9E9E")
                self.alert_tree.item(item_id, tags=(color,))
                
                # 如果已解决,添加标记
                if alert.resolved:
                    self.alert_tree.item(item_id, tags=("resolved",))
            
            # 配置标签颜色
            for level, color in ALERT_COLORS.items():
                self.alert_tree.tag_configure(color, background=color, foreground="#000000")
            self.alert_tree.tag_configure("resolved", foreground="#9E9E9E")
            
            # 更新状态
            stats = self.alert_system.get_alert_statistics()
            self.status_label.config(
                text=f"活动告警: {stats['active_alerts']} | 总告警: {stats['total_alerts']}"
            )
            
        except Exception as e:
            pass  # 静默失败,不影响GUI
    
    def _format_time(self, timestamp: str) -> str:
        """格式化时间戳"""
        try:
            dt = datetime.fromisoformat(timestamp)
            return dt.strftime("%H:%M:%S")
        except:
            return timestamp[:19]
    
    def _format_level(self, level: AlertLevel) -> str:
        """格式化告警级别"""
        level_map = {
            AlertLevel.INFO: "ℹ️ 信息",
            AlertLevel.WARNING: "⚠️ 警告",
            AlertLevel.CRITICAL: "🔴 严重",
            AlertLevel.EMERGENCY: "🚨 紧急"
        }
        return level_map.get(level, level.value)
    
    def _on_alert_double_click(self, event):
        """双击告警查看详情"""
        selection = self.alert_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        values = self.alert_tree.item(item, "values")
        
        # 获取告警索引
        index = len(self.alert_tree.get_children()) - self.alert_tree.index(item) - 1
        
        if 0 <= index < len(self.alert_system.alert_history):
            alert = self.alert_system.alert_history[index]
            self._show_alert_detail(alert)
    
    def _show_alert_detail(self, alert):
        """显示告警详情"""
        detail_window = tk.Toplevel(self)
        detail_window.title("告警详情")
        detail_window.geometry("500x400")
        detail_window.configure(bg="#1E1E1E")
        
        # 标题
        title = tk.Label(
            detail_window,
            text=alert.message,
            font=("Microsoft YaHei", 12, "bold"),
            bg="#1E1E1E",
            fg=ALERT_COLORS.get(alert.level, "#FFFFFF")
        )
        title.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        # 详情文本
        detail_text = tk.Text(
            detail_window,
            font=("Consolas", 10),
            bg="#2D2D2D",
            fg="#FFFFFF",
            wrap=tk.WORD,
            height=15
        )
        detail_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 填充详情
        detail_content = f"""告警类型: {ALERT_TYPE_NAMES.get(alert.alert_type, alert.alert_type.value)}
告警级别: {alert.level.value.upper()}
触发时间: {alert.timestamp}
解决状态: {'已解决' if alert.resolved else '未解决'}
解决时间: {alert.resolved_at or 'N/A'}

触发时的性能指标:
"""
        for key, value in alert.metrics.items():
            detail_content += f"  {key}: {value}\n"
        
        detail_text.insert(tk.END, detail_content)
        detail_text.config(state=tk.DISABLED)
        
        # 关闭按钮
        btn_close = tk.Button(
            detail_window,
            text="关闭",
            font=("Microsoft YaHei", 10),
            bg="#333333",
            fg="#FFFFFF",
            command=detail_window.destroy
        )
        btn_close.pack(pady=10)
    
    def _clear_history(self):
        """清空告警历史"""
        if messagebox.askyesno("确认", "确定要清空所有告警历史吗?"):
            self.alert_system.clear_history()
            self._refresh_alerts()
            messagebox.showinfo("完成", "告警历史已清空")
    
    def _show_stats(self):
        """显示告警统计"""
        stats = self.alert_system.get_alert_statistics()
        
        stats_text = f"""告警统计

总告警数: {stats['total_alerts']}
活动告警: {stats['active_alerts']}
已解决: {stats['resolved_alerts']}

按级别统计:
"""
        for level, count in stats['alerts_by_level'].items():
            stats_text += f"  {level}: {count}\n"
        
        stats_text += "\n按类型统计:\n"
        for alert_type, count in stats['alerts_by_type'].items():
            type_name = ALERT_TYPE_NAMES.get(AlertType(alert_type), alert_type)
            stats_text += f"  {type_name}: {count}\n"
        
        messagebox.showinfo("告警统计", stats_text)
    
    def destroy(self):
        """销毁组件"""
        if self._update_job:
            self.after_cancel(self._update_job)
        super().destroy()
