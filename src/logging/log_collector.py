#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志收集器

从多个来源收集日志数据。
"""

import logging
import threading
import queue
import time
from typing import Dict, Any, Optional, Callable
from .events import LogEvent, LogEventType


class LogCollector:
    """日志收集器

    从多种来源收集日志：
    - Python logging模块
    - 消息队列
    - 文件系统
    - 标准输出/错误
    """

    def __init__(self, max_queue_size: int = 1000):
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._handlers: Dict[str, Callable] = {}
        self._running = False
        self._collector_thread: Optional[threading.Thread] = None
        self._log_handler = None
        self._setup_logging_handler()

    def _setup_logging_handler(self):
        """设置logging处理器"""
        self._log_handler = _CollectorLogHandler(self)
        self._log_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self._log_handler.setFormatter(formatter)

    def start(self):
        """启动收集器"""
        if self._running:
            return

        self._running = True
        self._collector_thread = threading.Thread(
            target=self._collect_loop,
            daemon=True
        )
        self._collector_thread.start()

    def stop(self):
        """停止收集器"""
        self._running = False
        if self._collector_thread:
            self._collector_thread.join(timeout=2.0)
        self._collector_thread = None

    def _collect_loop(self):
        """收集循环"""
        while self._running:
            try:
                item = self._queue.get(timeout=0.1)
                self._process_item(item)
            except queue.Empty:
                continue
            except Exception:
                pass

    def _process_item(self, item: Dict[str, Any]):
        """处理收集到的项目"""
        event_type = item.get('event_type', LogEventType.STATUS_UPDATE)
        data = item.get('data', {})
        timestamp = item.get('timestamp', time.time())

        event = LogEvent(
            event_type=event_type,
            data=data,
            timestamp=timestamp,
            source=item.get('source', 'collector')
        )

        # 调用注册的处理器
        handler = self._handlers.get(event_type.value)
        if handler:
            try:
                handler(event)
            except Exception:
                pass

    def collect_from_queue(self, event_type: LogEventType, data: Dict[str, Any],
                          source: str = "external"):
        """从消息队列收集

        Args:
            event_type: 事件类型
            data: 事件数据
            source: 事件来源
        """
        try:
            self._queue.put_nowait({
                'event_type': event_type,
                'data': data,
                'timestamp': time.time(),
                'source': source
            })
        except queue.Full:
            pass

    def collect_log(self, logger_name: str, level: int, message: str):
        """收集logging模块的日志"""
        level_name = logging.getLevelName(level)
        self.collect_from_queue(
            LogEventType.STATUS_UPDATE,
            {
                'logger': logger_name,
                'level': level_name,
                'message': message
            },
            source='logging'
        )

    def register_handler(self, event_type: str, handler: Callable):
        """注册事件处理器

        Args:
            event_type: 事件类型
            handler: 处理函数
        """
        self._handlers[event_type] = handler

    def unregister_handler(self, event_type: str):
        """取消注册事件处理器"""
        self._handlers.pop(event_type, None)

    def attach_to_logger(self, logger_name: str = None):
        """附加到Python logger

        Args:
            logger_name: 日志器名称，None表示根日志器
        """
        logger = logging.getLogger(logger_name)
        logger.addHandler(self._log_handler)
        logger.setLevel(logging.DEBUG)

    def detach_from_logger(self, logger_name: str = None):
        """从Python logger分离

        Args:
            logger_name: 日志器名称，None表示根日志器
        """
        logger = logging.getLogger(logger_name)
        if self._log_handler in logger.handlers:
            logger.removeHandler(self._log_handler)


class _CollectorLogHandler(logging.Handler):
    """收集器专用的logging处理器"""

    def __init__(self, collector: LogCollector):
        super().__init__()
        self.collector = collector

    def emit(self, record: logging.LogRecord):
        """发送日志记录"""
        try:
            self.collector.collect_log(
                record.name,
                record.levelno,
                self.format(record)
            )
        except Exception:
            self.handleError(record)
