#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立日志显示窗口

创建一个独立的窗口来显示引擎执行的日志，与主交互界面分离。
"""

import threading
import queue
import time
import tkinter as tk
from tkinter import scrolledtext, ttk
import logging
from typing import Optional, Any


class LogWindow:
    """独立的日志显示窗口

    功能:
    - 实时显示引擎执行的日志
    - 支持日志级别过滤
    - 支持自动滚动
    - 支持清空日志
    - 支持保存日志到文件
    """

    def __init__(self, title: str = "引擎日志", width: int = 800, height: int = 600) -> None:
        """初始化日志窗口

        Args:
            title: 窗口标题
            width: 窗口宽度
            height: 窗口高度
        """
        self.title = title
        self.width = width
        self.height = height
        self.log_queue: "queue.Queue[Any]" = queue.Queue()
        self.root: Optional[Any] = None
        self.text_area: Optional[Any] = None
        self.filter_var: Optional[Any] = None
        self.auto_scroll_var: Optional[Any] = None
        self.running: bool = False
        self.update_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """启动日志窗口

        在新线程中创建并运行Tkinter窗口
        """
        self.running = True
        self.update_thread = threading.Thread(target=self._run_window, daemon=True)
        self.update_thread.start()
        # 等待窗口初始化完成
        time.sleep(0.5)

    def stop(self) -> None:
        """停止日志窗口

        安全关闭窗口和线程
        """
        self.running = False
        if self.root:
            self.root.after(0, self.root.destroy)
        if self.update_thread:
            self.update_thread.join(timeout=2.0)

    def log(self, message: str, level: str = "INFO") -> None:
        """添加日志消息

        Args:
            message: 日志消息
            level: 日志级别
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        try:
            self.log_queue.put_nowait(log_entry)
        except queue.Full:
            pass  # 队列满时丢弃日志

    def _run_window(self):
        """在新线程中运行Tkinter窗口

        注意：Tkinter需要在单独的线程中运行
        """
        self.root = tk.Tk()
        self.root.title(self.title)
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 创建工具栏
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        # 日志级别过滤器
        ttk.Label(toolbar, text="过滤级别:").pack(side=tk.LEFT, padx=(0, 5))
        self.filter_var = tk.StringVar(value="ALL")
        filter_combo = ttk.Combobox(
            toolbar,
            textvariable=self.filter_var,
            values=["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        )
        filter_combo.pack(side=tk.LEFT, padx=(0, 10))

        # 自动滚动选项
        self.auto_scroll_var = tk.BooleanVar(value=True)
        auto_scroll_check = ttk.Checkbutton(toolbar, text="自动滚动", variable=self.auto_scroll_var)
        auto_scroll_check.pack(side=tk.LEFT, padx=(0, 10))

        # 清空按钮
        clear_button = ttk.Button(toolbar, text="清空", command=self._clear_log)
        clear_button.pack(side=tk.LEFT, padx=(0, 10))

        # 保存按钮
        save_button = ttk.Button(toolbar, text="保存", command=self._save_log)
        save_button.pack(side=tk.LEFT)

        # 创建日志显示区域
        self.text_area = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.text_area.pack(fill=tk.BOTH, expand=True)

        # 配置文本标签
        self.text_area.tag_config("DEBUG", foreground="gray")
        self.text_area.tag_config("INFO", foreground="black")
        self.text_area.tag_config("WARNING", foreground="orange")
        self.text_area.tag_config("ERROR", foreground="red")
        self.text_area.tag_config("CRITICAL", foreground="red", font=("Consolas", 10, "bold"))

        # 开始更新循环
        self._update_logs()

        # 运行主循环
        try:
            self.root.mainloop()
        except Exception:
            pass  # 忽略窗口关闭时的异常

    def _update_logs(self):
        """更新日志显示

        从队列中获取日志并显示
        """
        if not self.running or not self.root:
            return

        # 处理队列中的所有日志
        while not self.log_queue.empty():
            try:
                log_entry = self.log_queue.get_nowait()
                self._display_log(log_entry)
            except queue.Empty:
                break

        # 继续更新循环
        if self.running and self.root:
            self.root.after(100, self._update_logs)

    def _display_log(self, log_entry: str):
        """显示单条日志

        Args:
            log_entry: 日志条目
        """
        if not self.text_area:
            return

        # 提取日志级别
        level_start = log_entry.find("[") + 1
        level_end = log_entry.find("]", level_start)
        if level_start > 0 and level_end > level_start:
            level = log_entry[level_start:level_end]
        else:
            level = "INFO"

        # 检查过滤级别
        filter_level = self.filter_var.get() if self.filter_var else "ALL"
        if filter_level != "ALL" and level != filter_level:
            return

        # 显示日志
        self.text_area.insert(tk.END, log_entry + "\n", level)

        # 自动滚动
        if self.auto_scroll_var and self.auto_scroll_var.get():
            self.text_area.see(tk.END)

    def _clear_log(self):
        """清空日志显示"""
        if self.text_area:
            self.text_area.delete(1.0, tk.END)

    def _save_log(self):
        """保存日志到文件"""
        if not self.text_area:
            return

        import tkinter.filedialog as filedialog

        file_path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("All files", "*.*")],
            initialfile=f"engine_log_{time.strftime('%Y%m%d_%H%M%S')}.log",
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.text_area.get(1.0, tk.END))
            except Exception as e:
                self.log(f"保存日志失败: {e}", "ERROR")

    def _on_close(self):
        """窗口关闭事件处理"""
        self.running = False
        if self.root:
            self.root.destroy()


class LogWindowHandler(logging.Handler):
    """将日志重定向到LogWindow的Handler"""

    def __init__(self, log_window: LogWindow) -> None:
        """初始化日志处理器

        Args:
            log_window: LogWindow实例
        """
        super().__init__()
        self.log_window = log_window

    def emit(self, record: logging.LogRecord) -> None:
        """处理日志记录

        Args:
            record: 日志记录
        """
        try:
            message = self.format(record)
            self.log_window.log(message, record.levelname)
        except Exception:
            pass


# 全局单例实例（修复：防止重复创建）
_log_window_instance = None


def reset_log_window_instance() -> None:
    """重置日志窗口单例（用于测试隔离）

    清理全局单例和根日志器中的 LogWindowHandler，
    确保 pytest 测试间隔离，避免交叉污染。
    """
    global _log_window_instance

    if _log_window_instance is not None:
        try:
            _log_window_instance.stop()
        except Exception:
            pass

    # 从根日志器移除 LogWindowHandler
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        if isinstance(handler, LogWindowHandler):
            root_logger.removeHandler(handler)

    _log_window_instance = None


def create_log_window() -> LogWindow:
    """创建并启动日志窗口

    Returns:
        LogWindow实例
    """
    global _log_window_instance

    # 修复: 单例模式，防止重复创建
    if _log_window_instance is not None:
        logging.getLogger(__name__).info("日志窗口已存在，跳过重复创建")
        return _log_window_instance

    log_window = LogWindow()
    log_window.start()

    # 配置根日志器
    root_logger = logging.getLogger()

    # 修复: 不要移除现有处理器，只添加新的LogWindowHandler
    # for handler in list(root_logger.handlers):  # ← 已删除，避免破坏日志配置
    #     root_logger.removeHandler(handler)

    # 添加LogWindowHandler
    log_handler = LogWindowHandler(log_window)
    log_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    root_logger.addHandler(log_handler)
    # 修复: 不修改根日志级别，保持配置文件设置
    # root_logger.setLevel(logging.DEBUG)  # ← 已删除，避免覆盖配置

    # 保存单例实例
    _log_window_instance = log_window

    return log_window


if __name__ == "__main__":
    # 测试日志窗口
    log_window = create_log_window()

    # 测试日志输出
    logger = logging.getLogger("Test")
    logger.debug("这是一条调试信息")
    logger.info("这是一条信息")
    logger.warning("这是一条警告")
    logger.error("这是一条错误")
    logger.critical("这是一条严重错误")

    # 保持程序运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log_window.stop()
