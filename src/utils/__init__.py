"""工具模块"""

from .bech32_codec import (
    BECH32_CHARSET,
    BECH32_CONST,
    BECH32M_CONST,
    bech32_create_checksum,
    bech32_decode,
    bech32_encode,
    bech32_polymod,
    bech32_verify_checksum,
    convertbits,
    decode_segwit_address,
)
from .encoding_utils import EncodingUtils
from .exception_handler import ExceptionHandler
from .exceptions import (
    AddressGenerationError,
    CheckpointError,
    CollisionError,
    ConfigError,
    CryptoBackendError,
    DeduplicationError,
    KeyGenerationError,
    TargetResolutionError,
    ValidationError,
)
from .file_utils import (
    atomic_json_read,
    atomic_json_write,
    ensure_directory,
    get_file_size_safe,
    safe_file_delete,
)
from .logger import (
    AsyncFileHandler,
    AsyncLogger,
    ColoredFormatter,
    PerformanceMonitor,
    SafeStreamHandler,  # SafeStreamHandler: Windows GBK编码兼容
    SampledLogger,
    get_logger,
    log_performance,
    setup_logger,
)
from .logging_config import LoggingConfig, get_configured_logger, init_logging
from .performance_monitor import (
    EnhancedPerformanceMonitor,
    PerformanceMetrics,
    PerformanceTracker,
    create_performance_monitor,
    get_performance_tracker,
    is_performance_monitoring_enabled,
    log_performance_summary,
)

__all__ = [
    # 异常类
    "CollisionError",
    "ConfigError",
    "ValidationError",
    "KeyGenerationError",
    "AddressGenerationError",
    "CheckpointError",
    "DeduplicationError",
    "TargetResolutionError",
    "CryptoBackendError",
    # 日志工具
    "setup_logger",
    "get_logger",
    "PerformanceMonitor",
    "SampledLogger",
    "ColoredFormatter",
    "log_performance",
    "AsyncLogger",
    "AsyncFileHandler",
    "SafeStreamHandler",  # v2.2.1新增; SafeStreamHandler: Windows GBK兼容
    # 日志配置
    "init_logging",
    "get_configured_logger",
    "LoggingConfig",
    # 性能监控
    "PerformanceTracker",
    "EnhancedPerformanceMonitor",
    "PerformanceMetrics",
    "get_performance_tracker",
    "log_performance_summary",
    "create_performance_monitor",
    "is_performance_monitoring_enabled",
    # 编码工具
    "EncodingUtils",
    # 异常处理
    "ExceptionHandler",
    # 文件工具
    "atomic_json_write",
    "atomic_json_read",
    "safe_file_delete",
    "get_file_size_safe",
    "ensure_directory",
    # Bech32 编解码 (BIP-173/BIP-350)
    "bech32_decode",
    "bech32_encode",
    "convertbits",
    "decode_segwit_address",
    "bech32_polymod",
    "bech32_verify_checksum",
    "bech32_create_checksum",
    "BECH32_CHARSET",
    "BECH32_CONST",
    "BECH32M_CONST",
]
