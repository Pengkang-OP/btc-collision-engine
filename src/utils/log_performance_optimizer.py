"""日志性能优化模块

优化日志处理性能，充分利用平台支持的编程语言特性，包括：
- 异步日志处理
- 日志缓存机制
- 批量写入
- 平台特定优化
"""
import os
import sys
import time
import threading
import queue
import logging
import platform
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field


@dataclass
class LogPerformanceConfig:
    """日志性能配置"""
    async_enabled: bool = True  # 是否启用异步日志
    buffer_size: int = 10000  # 日志缓冲区大小
    flush_interval: float = 1.0  # 刷新间隔（秒）
    batch_size: int = 100  # 批量写入大小
    use_thread_pool: bool = True  # 是否使用线程池
    thread_pool_size: int = 4  # 线程池大小
    compression_enabled: bool = False  # 是否启用压缩
    memory_threshold: int = 1024  # 内存阈值（MB）


class AsyncLogBuffer:
    """异步日志缓冲区"""
    
    def __init__(self, config: LogPerformanceConfig) -> None:
        """
        初始化异步日志缓冲区
        
        Args:
            config: 性能配置
        """
        self.config = config
        self.queue = queue.Queue(maxsize=config.buffer_size)
        self._stop_event = threading.Event()
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="AsyncLogBuffer-Flush"
        )
        self._flush_thread.start()
        self._handlers: List[logging.Handler] = []
        self._dropped_count = 0
    
    def add_handler(self, handler: logging.Handler) -> None:
        """添加日志处理器"""
        self._handlers.append(handler)
    
    def remove_handler(self, handler: logging.Handler) -> None:
        """移除日志处理器"""
        if handler in self._handlers:
            self._handlers.remove(handler)
    
    def emit(self, record: logging.LogRecord) -> None:
        """异步发出日志记录"""
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            # 队列满时丢弃最旧日志
            self._dropped_count += 1
            if self._dropped_count % 1000 == 0:
                print(f"警告: 日志缓冲区已满，已丢弃 {self._dropped_count} 条记录")
    
    def _flush_loop(self) -> None:
        """后台刷新循环"""
        while not self._stop_event.is_set():
            try:
                # 批量获取日志记录
                records = []
                while len(records) < self.config.batch_size:
                    try:
                        record = self.queue.get(timeout=self.config.flush_interval)
                        records.append(record)
                        self.queue.task_done()
                    except queue.Empty:
                        break
                
                # 批量写入
                if records:
                    self._batch_write(records)
            except Exception as e:
                print(f"日志刷新循环错误: {e}")
    
    def _batch_write(self, records: List[logging.LogRecord]) -> None:
        """批量写入日志记录"""
        for handler in self._handlers:
            try:
                for record in records:
                    handler.emit(record)
            except Exception as e:
                print(f"批量写入错误: {e}")
    
    def flush(self) -> None:
        """手动刷新缓冲区"""
        records = []
        while not self.queue.empty():
            try:
                record = self.queue.get_nowait()
                records.append(record)
                self.queue.task_done()
            except queue.Empty:
                break
        
        if records:
            self._batch_write(records)
    
    def close(self) -> None:
        """关闭缓冲区"""
        self._stop_event.set()
        self._flush_thread.join(timeout=5)
        self.flush()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'queue_size': self.queue.qsize(),
            'dropped_count': self._dropped_count,
            'handler_count': len(self._handlers)
        }


class LogPerformanceOptimizer:
    """日志性能优化器"""
    
    def __init__(self, config: Optional[LogPerformanceConfig] = None) -> None:
        """
        初始化性能优化器
        
        Args:
            config: 性能配置
        """
        self.config = config or LogPerformanceConfig()
        self.async_buffer: Optional[AsyncLogBuffer] = None
        self._initialized = False
    
    def initialize(self) -> None:
        """初始化优化器"""
        if not self._initialized:
            if self.config.async_enabled:
                self.async_buffer = AsyncLogBuffer(self.config)
            self._initialized = True
    
    def optimize_handler(self, handler: logging.Handler) -> logging.Handler:
        """
        优化日志处理器
        
        Args:
            handler: 原始日志处理器
        
        Returns:
            优化后的日志处理器
        """
        self.initialize()
        
        if self.config.async_enabled and self.async_buffer:
            # 包装为异步处理器
            class OptimizedHandler(logging.Handler):
                def __init__(self, original_handler, async_buffer) -> None:
                    super().__init__()
                    self.original_handler = original_handler
                    self.async_buffer = async_buffer
                    self.async_buffer.add_handler(original_handler)
                
                def emit(self, record: logging.LogRecord) -> None:
                    self.async_buffer.emit(record)
                
                def close(self) -> None:
                    self.async_buffer.remove_handler(self.original_handler)
                    self.original_handler.close()
                    super().close()
            
            return OptimizedHandler(handler, self.async_buffer)
        else:
            # 直接返回原始处理器
            return handler
    
    def optimize_logger(self, logger: logging.Logger) -> logging.Logger:
        """
        优化日志记录器
        
        Args:
            logger: 原始日志记录器
        
        Returns:
            优化后的日志记录器
        """
        self.initialize()
        
        # 优化现有处理器
        optimized_handlers = []
        for handler in logger.handlers:
            optimized_handler = self.optimize_handler(handler)
            optimized_handlers.append(optimized_handler)
        
        # 替换处理器
        logger.handlers = optimized_handlers
        return logger
    
    def get_platform_optimizations(self) -> Dict[str, Any]:
        """
        获取平台特定的优化策略
        
        Returns:
            平台优化策略
        """
        platform_name = platform.system()
        optimizations = {
            'platform': platform_name,
            'recommendations': []
        }
        
        if platform_name == 'Windows':
            optimizations['recommendations'].append('使用 SafeRotatingFileHandler 避免文件锁问题')
            optimizations['recommendations'].append('减少磁盘I/O操作，增加缓冲区大小')
        elif platform_name == 'Linux':
            optimizations['recommendations'].append('使用 os.fsync() 确保数据写入')
            optimizations['recommendations'].append('考虑使用 syslog 进行日志聚合')
        elif platform_name == 'Darwin':
            optimizations['recommendations'].append('使用 macOS 原生日志系统')
        
        return optimizations
    
    def get_memory_usage(self) -> float:
        """
        获取当前内存使用情况
        
        Returns:
            内存使用量（MB）
        """
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            return memory_info.rss / (1024 * 1024)  # 转换为MB
        except ImportError:
            return 0.0
    
    def should_throttle(self) -> bool:
        """
        判断是否应该节流
        
        Returns:
            是否应该节流
        """
        memory_usage = self.get_memory_usage()
        return memory_usage > self.config.memory_threshold
    
    def close(self) -> None:
        """关闭优化器"""
        if self.async_buffer:
            self.async_buffer.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取优化器统计信息
        
        Returns:
            统计信息
        """
        stats = {
            'async_enabled': self.config.async_enabled,
            'buffer_size': self.config.buffer_size,
            'flush_interval': self.config.flush_interval,
            'batch_size': self.config.batch_size,
            'memory_usage': self.get_memory_usage()
        }
        
        if self.async_buffer:
            stats.update(self.async_buffer.get_stats())
        
        return stats


class LogThrottler:
    """日志节流器"""
    
    def __init__(self, max_logs_per_second: float = 100.0) -> None:
        """
        初始化日志节流器
        
        Args:
            max_logs_per_second: 每秒最大日志数
        """
        self.max_logs_per_second = max_logs_per_second
        self._window_size = 1.0  # 时间窗口大小（秒）
        self._log_times: List[float] = []
        self._lock = threading.Lock()
    
    def should_log(self) -> bool:
        """
        判断是否应该记录日志
        
        Returns:
            是否应该记录日志
        """
        if self.max_logs_per_second <= 0:
            return True
        
        current_time = time.time()
        
        with self._lock:
            # 清理过期的日志时间
            self._log_times = [t for t in self._log_times if current_time - t < self._window_size]
            
            # 检查是否超过限制
            if len(self._log_times) < self.max_logs_per_second:
                self._log_times.append(current_time)
                return True
            else:
                return False


def log_performance_decorator(logger: logging.Logger, operation: str, level: str = "DEBUG"):
    """
    性能监控装饰器
    
    Args:
        logger: 日志记录器
        operation: 操作名称
        level: 日志级别
    
    Returns:
        装饰器
    """
    def decorator(func):
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = (time.time() - start_time) * 1000
                logger.log(getattr(logging, level), f"[性能] {operation}: {elapsed:.2f}ms")
                return result
            except Exception as e:
                elapsed = (time.time() - start_time) * 1000
                logger.error(f"[性能] {operation}: 失败 after {elapsed:.2f}ms - {e}")
                raise
        return wrapper
    return decorator


# 全局性能优化器实例
_performance_optimizer: Optional[LogPerformanceOptimizer] = None


def get_performance_optimizer(config: Optional[LogPerformanceConfig] = None) -> LogPerformanceOptimizer:
    """
    获取性能优化器实例
    
    Args:
        config: 性能配置
    
    Returns:
        性能优化器实例
    """
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = LogPerformanceOptimizer(config)
    return _performance_optimizer


def optimize_logger(logger: logging.Logger) -> logging.Logger:
    """
    优化日志记录器
    
    Args:
        logger: 日志记录器
    
    Returns:
        优化后的日志记录器
    """
    optimizer = get_performance_optimizer()
    return optimizer.optimize_logger(logger)


def optimize_handler(handler: logging.Handler) -> logging.Handler:
    """
    优化日志处理器
    
    Args:
        handler: 日志处理器
    
    Returns:
        优化后的日志处理器
    """
    optimizer = get_performance_optimizer()
    return optimizer.optimize_handler(handler)


def get_log_stats() -> Dict[str, Any]:
    """
    获取日志系统统计信息
    
    Returns:
        统计信息
    """
    optimizer = get_performance_optimizer()
    return optimizer.get_stats()
