#!/usr/bin/env python3
"""
BTC碰撞引擎 - 日志处理模块

该模块专注于日志的收集、处理与存储功能。

主要功能：
- 日志收集：从多个来源收集日志
- 日志处理：格式化和处理日志数据
- 日志存储：持久化存储日志
- 日志查询：查询和检索日志

支持独立运行：
    python -m src.logging

或者导入使用：
    from src.logging import LogManager
    log_manager = LogManager()
    log_manager.start()
"""

__version__ = "1.0.0"
__author__ = "BTC Collision Engine Team"

from .events import LogEvent
from .log_collector import LogCollector
from .log_manager import LogLevel, LogManager
from .log_processor import LogProcessor
from .log_query import LogQuery
from .log_storage import LogStorage

__all__ = [
    "LogManager",
    "LogLevel",
    "LogCollector",
    "LogProcessor",
    "LogStorage",
    "LogQuery",
    "LogEvent",
]
