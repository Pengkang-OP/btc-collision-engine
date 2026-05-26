"""
Configuration management package for BTC Collision Engine.

Provides configuration loading, validation, hot-reloading (ConfigWatcher),
migration between config versions, crypto backend selection (CryptoConfig),
and performance/optimization tuning (PerformanceConfig, OptimizationConfig).
"""

from src import __version__ as __version__  # noqa: F401

from .config_coordinator import ConfigCoordinator
from .config_manager import ConfigManager
from .config_migration import migrate_config_file
from .config_watcher import ConfigWatcher
from .crypto_config import CryptoBackendType, CryptoConfig, get_crypto_config, init_crypto_from_config
from .optimization_config import OptimizationConfig, is_feature_enabled
from .performance_config import PerformanceConfig

__all__ = [
    "ConfigManager",
    "ConfigCoordinator",
    "ConfigWatcher",
    "migrate_config_file",
    "CryptoConfig",
    "CryptoBackendType",
    "get_crypto_config",
    "init_crypto_from_config",
    "OptimizationConfig",
    "is_feature_enabled",
    "PerformanceConfig",
]
