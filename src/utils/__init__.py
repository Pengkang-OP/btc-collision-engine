"""工具模块"""

from .bech32_codec import (
    bech32_decode,
    bech32_encode,
    decode_segwit_address,
)
from .encoding_utils import EncodingUtils
from .error_recovery import (
    ErrorRecoveryManager,
    FallbackStrategy,
    RecoverableErrorCategory,
    RecoveryAction,
    RecoveryStats,
    RetryRecord,
    classify_recoverable_error,
    get_default_recovery_manager,
    retry_on_error,
)
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
from .sensitive_patterns import (
    # 敏感数据检测模式（非MASK变体，通过 __all__ 导出）
    BECH32_ADDRESS,
    BECH32M_ADDRESS,
    BIP32_EXTENDED_KEY,
    BIP32_EXTENDED_PUBKEY,
    BIP39_CONTEXT_KEYWORDS,
    BIP39_PHRASE_12,
    BIP39_PHRASE_24,
    P2PKH_ADDRESS,
    P2SH_ADDRESS,
    PRIVATE_KEY_CONTEXT,
    PRIVATE_KEY_HEX,
    RAW_KEY,
    WIF_COMPRESSED,
    WIF_UNCOMPRESSED,
    # _MASK 变体由 sensitive_patterns 内部使用，此处不重新导出
)
from .timeout import (
    TimeoutContext,
    invoke_with_timeout,
    with_timeout,
)

__all__ = [
    # 超时保护工具
    "with_timeout",
    "invoke_with_timeout",
    "TimeoutContext",
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
    "SafeStreamHandler",  # v4.2.1新增; SafeStreamHandler: Windows GBK兼容
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
    # 错误恢复
    "ErrorRecoveryManager",
    "FallbackStrategy",
    "RecoverableErrorCategory",
    "RecoveryAction",
    "RecoveryStats",
    "RetryRecord",
    "classify_recoverable_error",
    "get_default_recovery_manager",
    "retry_on_error",
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
    "decode_segwit_address",
    # 敏感数据模式常量 (v4.5.1: 从 sensitive_patterns 共享模块导入)
    "PRIVATE_KEY_HEX",
    "WIF_UNCOMPRESSED",
    "WIF_COMPRESSED",
    "RAW_KEY",
    "PRIVATE_KEY_CONTEXT",
    "P2PKH_ADDRESS",
    "P2SH_ADDRESS",
    "BECH32_ADDRESS",
    "BECH32M_ADDRESS",
    "BIP32_EXTENDED_KEY",
    "BIP32_EXTENDED_PUBKEY",
    "BIP39_CONTEXT_KEYWORDS",
    "BIP39_PHRASE_12",
    "BIP39_PHRASE_24",
]
