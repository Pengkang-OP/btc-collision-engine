"""工具模块"""
from .exceptions import (
    CollisionError, ConfigError, ValidationError,
    KeyGenerationError, AddressGenerationError, CheckpointError,
    DeduplicationError, TargetResolutionError, CryptoBackendError
)
from .logger import (
    setup_logger, get_logger, PerformanceMonitor, SampledLogger,
    ThreadSafeLogger, ColoredFormatter, log_performance,
    AsyncLogger, AsyncFileHandler, SafeStreamHandler  # SafeStreamHandler: Windows GBK编码兼容
)
from .logging_config import init_logging, get_configured_logger, LoggingConfig
from .performance_monitor import (
    PerformanceTracker, EnhancedPerformanceMonitor,
    PerformanceMetrics, get_performance_tracker,
    log_performance_summary, create_performance_monitor,
    is_performance_monitoring_enabled
)
from .encoding_utils import EncodingUtils
from .exception_handler import ExceptionHandler
from .file_utils import (
    atomic_json_write, atomic_json_read,
    safe_file_delete, get_file_size_safe,
    ensure_directory
)

__all__ = [
    # 异常类
    'CollisionError', 'ConfigError', 'ValidationError',
    'KeyGenerationError', 'AddressGenerationError', 'CheckpointError',
    'DeduplicationError', 'TargetResolutionError', 'CryptoBackendError',
    # 日志工具
    'setup_logger', 'get_logger', 'PerformanceMonitor', 'SampledLogger',
    'ThreadSafeLogger', 'ColoredFormatter', 'log_performance',
    'AsyncLogger', 'AsyncFileHandler', 'SafeStreamHandler',  # v2.2.1新增; SafeStreamHandler: Windows GBK兼容
    # 日志配置
    'init_logging', 'get_configured_logger', 'LoggingConfig',
    # 性能监控
    'PerformanceTracker', 'EnhancedPerformanceMonitor',
    'PerformanceMetrics', 'get_performance_tracker',
    'log_performance_summary', 'create_performance_monitor',
    'is_performance_monitoring_enabled',
    # 编码工具
    'EncodingUtils',
    # 异常处理
    'ExceptionHandler',
    # 文件工具
    'atomic_json_write', 'atomic_json_read',
    'safe_file_delete', 'get_file_size_safe',
    'ensure_directory'
]
