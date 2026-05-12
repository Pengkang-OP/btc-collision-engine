"""配置管理模块"""

from .config_coordinator import ConfigCoordinator
from .config_manager import ConfigManager
from .config_watcher import ConfigWatcher  # P2-4
from .crypto_config import (
    CryptoBackendType,
    CryptoConfig,
    get_crypto_config,
    init_crypto_from_config,
)
from .performance_config import (
    PerformanceOptimizationConfig,
    PerformanceTuner,
    create_optimized_config,
)

__all__ = [
    "ConfigManager",
    "CryptoConfig",
    "CryptoBackendType",
    "get_crypto_config",
    "init_crypto_from_config",
    "ConfigCoordinator",
    # 性能优化配置
    "PerformanceOptimizationConfig",
    "PerformanceTuner",
    "create_optimized_config",
    # P2-4: 配置热重载
    "ConfigWatcher",
]
