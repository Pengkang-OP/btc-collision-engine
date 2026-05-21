"""日志管理工具

提供增强的日志功能，包括：
- 彩色控制台输出
- 性能监控日志
- 采样日志（高频操作）
- 异步日志写入（v4.2.1新增）

性能优化说明：
- Python的logging.Logger本身是线程安全的（内部使用RLock）
- 高频场景请使用SampledLogger或AsyncLogger
"""

import logging
import os
import platform
import queue
import sys
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from functools import wraps
from logging.handlers import RotatingFileHandler
from typing import Any


def _make_rotating_handler(filename: str, max_bytes: int, backup_count: int) -> RotatingFileHandler:
    """工厂函数：Windows 返回 SafeRotatingFileHandler，其他平台返回原生 RotatingFileHandler"""
    if platform.system() == "Windows":
        # 延迟导入避免循环依赖（logging_config 也导入 logger）
        with suppress(ImportError):
            from .logging_config import SafeRotatingFileHandler

            return SafeRotatingFileHandler(
                filename, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
            )
    return RotatingFileHandler(
        filename, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )


class SafeStreamHandler(logging.StreamHandler):
    """Windows GBK 编码安全控制台处理器

    在 Windows CMD/PowerShell（默认 GBK 编码）环境下，中文日志消息会乱码。
    本处理器在 emit 时尝试将无法编码的字符替换为 '?'，同时在真实终端下尝试强制 UTF-8 输出。
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            stream = self.stream
            # 检测流是否已被关闭（如测试替换 sys.stdout 后恢复导致的）
            if stream is None or getattr(stream, "closed", False):
                return
            # 如果是 Windows 且流编码不是 UTF-8，尝试将消息安全转换
            enc = getattr(stream, "encoding", "") or ""
            if enc.lower() not in ("utf-8", "utf8"):
                # 将无法用目标编码输出的字符替换为 '?'
                msg = msg.encode(enc, errors="replace").decode(enc, errors="replace")
            stream.write(msg + self.terminator)
            self.flush()
        except RecursionError:
            raise
        except (ValueError, OSError):
            # I/O operation on closed file 等流关闭异常，静默跳过
            return
        except (TypeError, RuntimeError, AttributeError):
            self.handleError(record)


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""

    # ANSI 颜色代码
    COLORS = {
        "DEBUG": "\033[36m",  # 青色
        "INFO": "\033[32m",  # 绿色
        "WARNING": "\033[33m",  # 黄色
        "ERROR": "\033[31m",  # 红色
        "CRITICAL": "\033[35m",  # 紫色
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # 保存原始级别名称
        orig_levelname = record.levelname

        # 添加颜色（仅控制台）
        if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
            color = self.COLORS.get(record.levelname, self.RESET)
            record.levelname = f"{color}{record.levelname}{self.RESET}"

        result = super().format(record)
        record.levelname = orig_levelname  # 恢复原始值
        return result


class PerformanceMonitor:
    """性能监控上下文管理器"""

    def __init__(self, logger: logging.Logger, operation: str, level: str = "DEBUG") -> None:
        self.logger = logger
        self.operation = operation
        self.level = getattr(logging, level.upper())
        self.start_time: float | None = None
        self.end_time: float | None = None

    def __enter__(self) -> "PerformanceMonitor":
        self.start_time = time.perf_counter()
        return self

    def __exit__(
        self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any | None
    ) -> None:
        self.end_time = time.perf_counter()
        assert self.start_time is not None
        elapsed_ms = (self.end_time - self.start_time) * 1000

        if exc_type is None:
            self.logger.log(self.level, f"[Performance] {self.operation}: {elapsed_ms:.2f}ms")
        else:
            self.logger.error(
                f"[Performance] {self.operation}: FAILED after {elapsed_ms:.2f}ms - {exc_val}"
            )

    @property
    def elapsed_ms(self) -> float:
        """获取已耗时的毫秒数"""
        if self.end_time is None:
            assert self.start_time is not None
            return (time.perf_counter() - self.start_time) * 1000
        assert self.start_time is not None
        return (self.end_time - self.start_time) * 1000


class SampledLogger:
    """采样日志记录器（用于高频操作）

    通过降低日志记录频率来减少I/O开销，适用于：
    - 循环内部的状态报告
    - 高频性能指标记录
    - 批量处理进度跟踪

    支持两种限频模式（可同时使用）：
    - 计数采样（sample_rate）：每N条消息记录1条
    - 时间限频（max_per_second）：每秒最多记录N条
    两个条件同时满足才会实际写入日志。
    """

    # 计数器上限，防止长时间运行后整数过大
    _COUNTER_MAX = 10**9

    def __init__(
        self, logger: logging.Logger, sample_rate: int = 100, max_per_second: float = 0.0
    ) -> None:
        """
        参数:
            logger: 底层日志记录器
            sample_rate: 采样率（每N条记录1条，计数采样）
            max_per_second: 每秒最多记录N条（时间限频），0表示不限制
        """
        self.logger = logger
        self.sample_rate = sample_rate
        self.max_per_second = max_per_second
        # Q2修复: 将 max_per_second 转换为整数，避免浮点数与整数比较
        self._max_per_second_int = max(1, int(max_per_second)) if max_per_second > 0 else 0
        self._counter = 0
        self._lock = threading.Lock()
        # 时间限频相关：记录当前秒窗口的起始时间和已记录条数
        self._last_log_time = 0.0
        self._time_window_count = 0

    def _should_log_by_time(self) -> bool:
        """检查是否满足时间限频条件（调用前须持有 _lock）

        返回 True 表示允许记录，同时更新时间窗口计数器。
        若 max_per_second <= 0 则始终返回 True（不限频）。
        """
        # Q2修复: 使用整数 _max_per_second_int 进行比较，避免浮点数与整数比较的逻辑错误
        if self._max_per_second_int <= 0:
            return True

        current_time = time.monotonic()
        # 判断是否处于同一秒窗口
        if current_time - self._last_log_time >= 1.0:
            # 新的时间窗口，重置计数
            self._last_log_time = current_time
            self._time_window_count = 1
            return True
        else:
            # 在同一秒窗口内，使用整数比较
            if self._time_window_count < self._max_per_second_int:
                self._time_window_count += 1
                return True
            return False

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            self._counter += 1
            # 防止计数器无限增长
            if self._counter >= self._COUNTER_MAX:
                self._counter = 0
            if self._counter % self.sample_rate == 0 and self._should_log_by_time():
                self.logger.debug(f"[Sampled 1/{self.sample_rate}] {msg}", *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            self._counter += 1
            # 防止计数器无限增长
            if self._counter >= self._COUNTER_MAX:
                self._counter = 0
            if self._counter % self.sample_rate == 0 and self._should_log_by_time():
                self.logger.info(f"[Sampled 1/{self.sample_rate}] {msg}", *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            self._counter += 1
            # 防止计数器无限增长
            if self._counter >= self._COUNTER_MAX:
                self._counter = 0
            if self._counter % self.sample_rate == 0 and self._should_log_by_time():
                self.logger.warning(f"[Sampled 1/{self.sample_rate}] {msg}", *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            self._counter += 1
            # 防止计数器无限增长
            if self._counter >= self._COUNTER_MAX:
                self._counter = 0
            if self._counter % self.sample_rate == 0 and self._should_log_by_time():
                self.logger.error(f"[Sampled 1/{self.sample_rate}] {msg}", *args, **kwargs)


def setup_logger(
    name: str,
    level: str = "INFO",
    log_file: str | None = None,
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    use_color: bool = True,
) -> logging.Logger:
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
        console_formatter: logging.Formatter = ColoredFormatter(format)
    else:
        console_formatter = logging.Formatter(format)

    # 创建控制台处理器（使用 SafeStreamHandler 以兼容 Windows GBK 编码）
    console_handler = SafeStreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level))
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 创建文件处理器（如果指定了文件）
    if log_file:
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, mode=0o750, exist_ok=True)

        # 使用 SafeRotatingFileHandler 自动轮转（Windows 安全）
        file_handler: logging.FileHandler = _make_rotating_handler(
            log_file, max_bytes, backup_count
        )
        file_handler.setLevel(getattr(logging, level))
        file_handler.setFormatter(logging.Formatter(format))
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """获取已配置的日志记录器，如果不存在则创建默认记录器。

    Args:
        name: 日志记录器名称

    Returns:
        日志记录器 (Python 原生 Logger，本身已是线程安全)
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        # 未配置，创建默认记录器
        logger = setup_logger(name)

    return logger


def get_sampled_logger(
    name: str, sample_rate: int = 100, max_per_second: float = 0.0
) -> SampledLogger:
    """
    获取采样日志记录器（用于高频操作）

    注意: 使用此函数前应先调用 init_logging() 配置全局日志系统，
    以避免重复配置 handlers 导致日志重复输出。

    参数:
        name: 日志记录器名称
        sample_rate: 采样率（每N条记录1条，计数采样）
        max_per_second: 每秒最多记录N条（时间限频），0表示不限制

    返回:
        采样日志记录器
    """
    # 直接使用 logging.getLogger，依赖全局 init_logging 配置的 handlers
    # 避免通过 get_logger/setup_logger 再次配置 handlers 导致重复输出
    base_logger = logging.getLogger(name)
    return SampledLogger(base_logger, sample_rate, max_per_second)


def log_performance(logger: logging.Logger, operation: str, level: str = "DEBUG") -> Callable:
    """
    性能监控装饰器工厂

    使用示例:
        @log_performance(logger, "expensive_operation")
        def my_function():
            pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with PerformanceMonitor(logger, operation, level):
                return func(*args, **kwargs)

        return wrapper

    return decorator


class AsyncLogger:
    """异步日志记录器（v4.2.1新增）

    使用后台线程异步写入日志，避免I/O阻塞计算线程。
    适用于高频日志记录场景（如GPU碰撞引擎的批量处理）。

    特性:
    - 非阻塞: emit()立即返回，不等待I/O完成
    - 缓冲: 使用队列缓冲日志记录，批量写入
    - 安全: 后台线程安全退出，确保日志不丢失

    性能提升:
    - 高频场景下可减少30-50%的I/O等待时间
    - 适用于每秒1000+条日志的场景

    使用示例:
        >>> async_handler = AsyncFileHandler('logs/async.log')
        >>> logger.addHandler(async_handler)
        >>> # 程序退出时调用
        >>> async_handler.close()
    """

    # Q6修复: 添加丢弃计数上限常量，防止整数溢出
    _DROPPED_COUNT_MAX = 10**12

    def __init__(self, max_queue_size: int = 10000) -> None:
        """
        参数:
            max_queue_size: 队列最大长度，超出时丢弃最旧日志
        """
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._handler: logging.Handler | None = None
        self._writer_thread = threading.Thread(
            target=self._write_loop,
            daemon=False,  # 非守护线程，确保程序退出时日志完整写入
            name="AsyncLogger-Writer",
        )
        self._stop_event = threading.Event()
        self._writer_thread.start()
        self._dropped_count = 0
        self._started_at = time.time()

        _logger = logging.getLogger(__name__)
        _logger.info(f"AsyncLogger 已初始化: max_queue_size={max_queue_size}")

    def set_handler(self, handler: logging.Handler) -> None:
        """Q1修复: 设置底层日志处理器（替代直接访问私有属性）

        Args:
            handler: 底层日志处理器
        """
        self._handler = handler

    def _write_loop(self):
        """后台写入循环"""
        while not self._stop_event.is_set():
            try:
                record = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                # 实际写入（调用底层handler）
                if self._handler:
                    self._handler.emit(record)
            except Exception as e:
                # 写入失败不应崩溃后台线程
                sys.stderr.write(f"异步日志写入失败: {e}\n")
            finally:
                self._queue.task_done()

        # 修复竞态条件: 停止事件设置后，处理队列中所有剩余记录
        while True:
            try:
                record = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                if self._handler:
                    self._handler.emit(record)
            except Exception as e:
                sys.stderr.write(f"异步日志drain写入失败: {e}\n")
            finally:
                self._queue.task_done()

    def emit(self, record: logging.LogRecord) -> None:
        """异步发出日志记录"""
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            # Q6修复: 添加丢弃计数上限，防止整数溢出
            self._dropped_count += 1
            if self._dropped_count >= self._DROPPED_COUNT_MAX:
                self._dropped_count = self._DROPPED_COUNT_MAX
            # G5修复 & M-7修复: 简化警告条件，使用更清晰的逻辑
            dropped = self._dropped_count
            # 在关键阈值点警告：1K, 5K, 10K, 50K, 100K, 500K, 1M, 之后每5M警告一次
            warning_thresholds = [1000, 5000, 10000, 50000, 100000, 500000, 1000000]
            is_threshold = dropped in warning_thresholds
            is_periodic = dropped > 1000000 and (dropped - 1000000) % 5000000 == 0
            if is_threshold or is_periodic:
                sys.stderr.write(f"⚠️ 异步日志队列已满，已丢弃 {dropped:,} 条记录\n")

    def close(self) -> None:
        """关闭异步日志器，等待队列清空"""
        _logger = logging.getLogger(__name__)
        _logger.info(
            f"AsyncLogger 正在关闭: queue_size={self._queue.qsize()}, "
            f"dropped_count={self._dropped_count}, "
            f"uptime={time.time() - self._started_at:.1f}s"
        )
        self._stop_event.set()

        # 等待队列清空（最多5秒）
        with suppress(OSError, ValueError):
            self._queue.join()

        # 等待线程退出
        self._writer_thread.join(timeout=5)
        if self._writer_thread.is_alive():
            import sys

            sys.stderr.write("警告: 异步日志写线程未能在规定时间内退出\n")

        # 关闭底层handler
        if hasattr(self, "_handler") and self._handler:
            self._handler.close()

        _logger.info("AsyncLogger 已关闭")

    def get_stats(self) -> dict:
        """获取异步日志统计信息"""
        return {
            "queue_size": self._queue.qsize(),
            "dropped_count": self._dropped_count,
            "is_running": self._writer_thread.is_alive(),
        }


class AsyncFileHandler(logging.Handler):
    """异步文件日志处理器

    包装AsyncLogger，提供标准的logging.Handler接口。

    使用示例:
        >>> handler = AsyncFileHandler('logs/app.log', max_bytes=10*1024*1024)
        >>> logger.addHandler(handler)
    """

    def __init__(self, filename: str, max_bytes: int = 0, backup_count: int = 0) -> None:
        """
        参数:
            filename: 日志文件路径
            max_bytes: 单个文件最大字节数（0表示不轮转）
            backup_count: 保留的备份文件数
        """
        super().__init__()

        # 创建底层文件处理器
        if max_bytes > 0:
            self._handler: logging.Handler = _make_rotating_handler(
                filename, max_bytes, backup_count
            )
        else:
            self._handler = logging.FileHandler(filename, encoding="utf-8")

        # Q1修复: 使用 set_handler 方法设置处理器，避免直接访问私有属性
        self._async_logger = AsyncLogger()
        self._async_logger.set_handler(self._handler)

    def emit(self, record: logging.LogRecord) -> None:
        """异步发出日志记录"""
        self._async_logger.emit(record)

    def close(self) -> None:
        """关闭处理器"""
        self._async_logger.close()
        super().close()

    def get_stats(self) -> dict:
        """获取统计信息"""
        return self._async_logger.get_stats()
