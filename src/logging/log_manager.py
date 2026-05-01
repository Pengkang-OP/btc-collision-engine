#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志管理器

日志处理模块的对外统一接口。
"""

import sys
import os
import threading
import time
from enum import Enum
from typing import Optional, Dict, Any, Callable

# 添加项目根目录到路径
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from .log_collector import LogCollector
from .log_processor import LogProcessor, SensitiveDataFilter
from .log_storage import LogStorage
from .log_query import LogQuery
from .events import LogEvent, LogEventType


class LogLevel(Enum):
    """日志级别"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogManager:
    """日志管理器

    对外提供统一的日志管理接口。

    使用示例：
        log_manager = LogManager()
        log_manager.start()

        # 记录日志
        log_manager.info("引擎启动")
        log_manager.error("发生错误", error_details)

        # 查询日志
        recent_logs = log_manager.get_recent(50)

        log_manager.stop()
    """

    def __init__(
        self,
        storage_dir: str = "logs",
        enable_console: bool = True,
        enable_file: bool = True,
        redact_sensitive: bool = True,
    ):
        """初始化日志管理器

        Args:
            storage_dir: 存储目录
            enable_console: 启用控制台输出
            enable_file: 启用文件存储
            redact_sensitive: 启用敏感数据过滤
        """
        self.storage_dir = storage_dir
        self.enable_console = enable_console
        self.enable_file = enable_file
        self._running = False
        self._lock = threading.Lock()

        # 初始化组件
        self.collector = LogCollector()
        self.processor = LogProcessor()
        self.storage = LogStorage(storage_dir) if enable_file else None
        self.query = LogQuery(storage_dir)

        # 设置敏感数据过滤器
        if redact_sensitive:
            self.processor.add_filter(SensitiveDataFilter().filter)

        # 注册默认处理器
        self._register_default_handlers()

    def _register_default_handlers(self):
        """注册默认处理器"""

        def handle_all(event: LogEvent):
            # 处理事件
            processed = self.processor.process(event)
            if processed is None:
                return

            # 控制台输出
            if self.enable_console:
                self._print_to_console(processed)

            # 文件存储
            if self.enable_file and self.storage:
                self.storage.save(processed)

        self.collector.register_handler("status_update", handle_all)
        self.collector.register_handler("engine_start", handle_all)
        self.collector.register_handler("engine_stop", handle_all)
        self.collector.register_handler("engine_error", handle_all)
        self.collector.register_handler("engine_pause", handle_all)
        self.collector.register_handler("engine_resume", handle_all)
        self.collector.register_handler("gpu_detected", handle_all)
        self.collector.register_handler("gpu_usage_update", handle_all)
        self.collector.register_handler("performance_update", handle_all)
        self.collector.register_handler("match_found", handle_all)
        self.collector.register_handler("checkpoint_saved", handle_all)
        self.collector.register_handler("config_loaded", handle_all)
        self.collector.register_handler("wizard_start", handle_all)
        self.collector.register_handler("wizard_complete", handle_all)
        self.collector.register_handler("wizard_error", handle_all)
        self.collector.register_handler("target_selected", handle_all)
        self.collector.register_handler("mode_selected", handle_all)
        self.collector.register_handler("options_selected", handle_all)
        self.collector.register_handler("gpu_selected", handle_all)
        self.collector.register_handler("config_built", handle_all)

    def _print_to_console(self, formatted_event: Dict[str, Any]):
        """打印到控制台"""
        timestamp = formatted_event.get("formatted_time", "")
        message = formatted_event.get("message", "")
        event_type = formatted_event.get("type", "")

        # 根据事件类型使用不同颜色
        color_map = {
            "engine_error": "\033[91m",  # 红色
            "wizard_error": "\033[91m",
            "engine_start": "\033[92m",  # 绿色
            "wizard_complete": "\033[92m",
            "engine_stop": "\033[94m",  # 蓝色
            "warning": "\033[93m",  # 黄色
        }

        color = color_map.get(event_type, "\033[0m")
        reset = "\033[0m"

        print(f"{color}[{timestamp}] {message}{reset}")

    def start(self):
        """启动日志管理器"""
        with self._lock:
            if self._running:
                return

            self._running = True
            self.collector.start()

            # 附加到Python logging
            root_logger = logging.getLogger()
            self.collector.attach_to_logger()

    def stop(self):
        """停止日志管理器"""
        with self._lock:
            if not self._running:
                return

            self._running = False
            self.collector.stop()

            # 从Python logging分离
            self.collector.detach_from_logger()

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running

    # 便捷的日志记录方法

    def debug(self, message: str, **kwargs):
        """记录调试日志"""
        self.collector.collect_from_queue(
            LogEventType.STATUS_UPDATE, {"level": "DEBUG", "message": message, **kwargs}
        )

    def info(self, message: str, **kwargs):
        """记录信息日志"""
        self.collector.collect_from_queue(
            LogEventType.STATUS_UPDATE, {"level": "INFO", "message": message, **kwargs}
        )

    def warning(self, message: str, **kwargs):
        """记录警告日志"""
        self.collector.collect_from_queue(
            LogEventType.STATUS_UPDATE, {"level": "WARNING", "message": message, **kwargs}
        )

    def error(self, message: str, **kwargs):
        """记录错误日志"""
        self.collector.collect_from_queue(LogEventType.ENGINE_ERROR, {"error": message, **kwargs})

    def critical(self, message: str, **kwargs):
        """记录严重错误日志"""
        self.collector.collect_from_queue(
            LogEventType.ENGINE_ERROR, {"critical": message, **kwargs}
        )

    # 专用日志方法

    def log_wizard_start(self, config: Dict[str, Any]):
        """记录向导开始"""
        self.collector.collect_from_queue(
            LogEventType.ENGINE_START, {"config": config}, source="wizard"
        )

    def log_wizard_complete(self, result: Dict[str, Any]):
        """记录向导完成"""
        self.collector.collect_from_queue(
            LogEventType.ENGINE_STOP, {"result": result}, source="wizard"
        )

    def log_wizard_error(self, error: str):
        """记录向导错误"""
        self.collector.collect_from_queue(
            LogEventType.ENGINE_ERROR, {"error": error}, source="wizard"
        )

    def log_target_selected(self, targets: list, target_file: Optional[str] = None):
        """记录目标选择"""
        self.collector.collect_from_queue(
            LogEventType.CONFIG_LOADED,
            {"targets": targets, "target_file": target_file},
            source="wizard",
        )

    def log_mode_selected(self, mode: str):
        """记录模式选择"""
        self.collector.collect_from_queue(
            LogEventType.CONFIG_LOADED, {"mode": mode}, source="wizard"
        )

    def log_gpu_selected(self, gpu_indices: list, use_multi_gpu: bool):
        """记录GPU选择"""
        self.collector.collect_from_queue(
            LogEventType.GPU_DETECTED,
            {"gpu_indices": gpu_indices, "use_multi_gpu": use_multi_gpu},
            source="wizard",
        )

    # 查询方法

    def get_recent(self, count: int = 50) -> list:
        """获取最近的日志"""
        if self.storage:
            return self.storage.get_recent(count)
        return []

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if self.storage:
            return self.storage.get_stats()
        return {}

    # 上下文管理器支持

    def __enter__(self):
        """进入上下文"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        self.stop()


# 导入logging模块（避免循环导入）
import logging


def main():
    """独立运行日志管理器"""
    import argparse

    parser = argparse.ArgumentParser(description="BTC碰撞引擎 - 日志管理器")
    parser.add_argument("--watch", action="store_true", help="实时监控日志")
    parser.add_argument("--query", type=str, help="查询日志")
    parser.add_argument("--recent", type=int, default=50, help="最近N条日志")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")
    parser.add_argument("--export", type=str, help="导出日志到文件")

    args = parser.parse_args()

    log_manager = LogManager()

    if args.watch:
        print("启动日志监控 (Ctrl+C 退出)...")
        log_manager.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n停止监控...")

        log_manager.stop()

    elif args.query:
        results = log_manager.query.search(args.query)
        for result in results:
            print(f"[{result.get('formatted_time', '')}] {result.get('message', '')}")

    elif args.stats:
        stats = log_manager.get_stats()
        print("日志统计:")
        print(f"  总数: {stats.get('total_count', 0)}")
        print(f"  类型统计: {stats.get('type_counts', {})}")

    elif args.export:
        if log_manager.storage.export_to_json(args.export):
            print(f"[OK] 日志已导出到: {args.export}")
        else:
            print("[ERROR] 导出失败")

    else:
        results = log_manager.get_recent(args.recent)
        print(f"最近的 {len(results)} 条日志:")
        for result in results:
            print(f"[{result.get('formatted_time', '')}] {result.get('message', '')}")


if __name__ == "__main__":
    main()
