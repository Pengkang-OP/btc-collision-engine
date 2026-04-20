"""日志管理工具

提供增强的日志功能，包括：
- 彩色控制台输出
- 线程安全的日志记录
- 性能监控日志
- 采样日志（高频操作）
"""
import logging
import os
import sys
import threading
import time
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler
from functools import wraps


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""
    
    # ANSI 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # 保存原始级别名称
        orig_levelname = record.levelname
        
        # 添加颜色（仅控制台）
        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            color = self.COLORS.get(record.levelname, self.RESET)
            record.levelname = f"{color}{record.levelname}{self.RESET}"
        
        result = super().format(record)
        record.levelname = orig_levelname  # 恢复原始值
        return result


class ThreadSafeLogger:
    """线程安全的日志包装器"""
    
    def __init__(self, logger: logging.Logger):
        self._logger = logger
        self._lock = threading.Lock()
    
    def debug(self, msg: str, *args, **kwargs):
        with self._lock:
            self._logger.debug(msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        with self._lock:
            self._logger.info(msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        with self._lock:
            self._logger.warning(msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        with self._lock:
            self._logger.error(msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        with self._lock:
            self._logger.critical(msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs):
        with self._lock:
            self._logger.exception(msg, *args, **kwargs)


class PerformanceMonitor:
    """性能监控上下文管理器"""
    
    def __init__(self, logger: logging.Logger, operation: str, level: str = "DEBUG"):
        self.logger = logger
        self.operation = operation
        self.level = getattr(logging, level.upper())
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        elapsed_ms = (self.end_time - self.start_time) * 1000
        
        if exc_type is None:
            self.logger.log(self.level, f"[Performance] {self.operation}: {elapsed_ms:.2f}ms")
        else:
            self.logger.error(f"[Performance] {self.operation}: FAILED after {elapsed_ms:.2f}ms - {exc_val}")
    
    @property
    def elapsed_ms(self) -> float:
        """获取已耗时的毫秒数"""
        if self.end_time is None:
            return (time.perf_counter() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000


class SampledLogger:
    """采样日志记录器（用于高频操作）"""
    
    def __init__(self, logger: logging.Logger, sample_rate: int = 100):
        """
        参数:
            logger: 底层日志记录器
            sample_rate: 采样率（每N条记录1条）
        """
        self.logger = logger
        self.sample_rate = sample_rate
        self._counter = 0
        self._lock = threading.Lock()
    
    def debug(self, msg: str, *args, **kwargs):
        with self._lock:
            self._counter += 1
            if self._counter % self.sample_rate == 0:
                self.logger.debug(f"[Sampled 1/{self.sample_rate}] {msg}", *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        with self._lock:
            self._counter += 1
            if self._counter % self.sample_rate == 0:
                self.logger.info(f"[Sampled 1/{self.sample_rate}] {msg}", *args, **kwargs)


def setup_logger(name: str, level: str = "INFO", 
                log_file: Optional[str] = None,
                format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                max_bytes: int = 10*1024*1024,  # 10MB
                backup_count: int = 5,
                use_color: bool = True) -> logging.Logger:
    """
    设置日志记录器（增强版）
    
    参数:
        name: 日志记录器名称
        level: 日志级别
        log_file: 日志文件路径，None表示只输出到控制台
        format: 日志格式
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的备份文件数量
        use_color: 是否使用彩色输出
        
    返回:
        配置好的日志记录器
    """
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))
    
    # 清除已有的处理器
    logger.handlers.clear()
    
    # 创建格式化器
    if use_color:
        console_formatter = ColoredFormatter(format)
    else:
        console_formatter = logging.Formatter(format)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level))
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 创建文件处理器（如果指定了文件）
    if log_file:
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, mode=0o750, exist_ok=True)
        
        # 使用 RotatingFileHandler 自动轮转
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, level))
        file_handler.setFormatter(logging.Formatter(format))
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str, thread_safe: bool = False) -> logging.Logger:
    """
    获取已配置的日志记录器，如果不存在则创建默认记录器
    
    参数:
        name: 日志记录器名称
        thread_safe: 是否返回线程安全包装器
        
    返回:
        日志记录器
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        # 未配置，创建默认记录器
        logger = setup_logger(name)
    
    if thread_safe:
        return ThreadSafeLogger(logger)
    return logger


def get_sampled_logger(name: str, sample_rate: int = 100) -> SampledLogger:
    """
    获取采样日志记录器（用于高频操作）
    
    注意: 使用此函数前应先调用 init_logging() 配置全局日志系统，
    以避免重复配置 handlers 导致日志重复输出。
    
    参数:
        name: 日志记录器名称
        sample_rate: 采样率
        
    返回:
        采样日志记录器
    """
    # 直接使用 logging.getLogger，依赖全局 init_logging 配置的 handlers
    # 避免通过 get_logger/setup_logger 再次配置 handlers 导致重复输出
    base_logger = logging.getLogger(name)
    return SampledLogger(base_logger, sample_rate)


def log_performance(logger: logging.Logger, operation: str, level: str = "DEBUG"):
    """
    性能监控装饰器工厂
    
    使用示例:
        @log_performance(logger, "expensive_operation")
        def my_function():
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with PerformanceMonitor(logger, operation, level):
                return func(*args, **kwargs)
        return wrapper
    return decorator
