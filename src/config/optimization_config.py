"""优化配置模块

管理各项优化功能的启用/禁用设置。
"""

import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class OptimizationConfig:
    """优化配置管理器"""

    def __init__(self) -> None:
        # 默认配置
        self._config = {
            # 增量统计优化
            "delta_stats_enabled": True,
            # 分布式统计聚合
            "distributed_aggregator_enabled": True,
            # 性能监控
            "performance_monitor_enabled": True,
            # 增量统计刷新间隔（秒）
            "delta_stats_flush_interval": 0.1,
            # 分布式聚合间隔（秒）
            "aggregator_interval": 0.1,
            # 性能监控间隔（秒）
            "monitor_interval": 1.0,
            # 性能告警阈值
            "alert_thresholds": {
                "latency_ms": 100.0,
                "lock_contention": 0.5,
                "memory_mb": 512.0,
                "cpu_usage": 80.0,
            },
        }

        # 从环境变量加载配置
        self._load_from_env()

    def _load_from_env(self) -> None:
        """从环境变量加载配置"""
        env_mapping = {
            "OPTIMIZE_DELTA_STATS": "delta_stats_enabled",
            "OPTIMIZE_DISTRIBUTED": "distributed_aggregator_enabled",
            "OPTIMIZE_MONITOR": "performance_monitor_enabled",
            "DELTA_FLUSH_INTERVAL": "delta_stats_flush_interval",
            "AGGREGATOR_INTERVAL": "aggregator_interval",
            "MONITOR_INTERVAL": "monitor_interval",
        }

        for env_key, config_key in env_mapping.items():
            env_value = os.environ.get(env_key)
            if env_value is not None:
                if config_key in [
                    "delta_stats_enabled",
                    "distributed_aggregator_enabled",
                    "performance_monitor_enabled",
                ]:
                    self._config[config_key] = env_value.lower() in ("true", "1", "yes")
                else:
                    try:
                        self._config[config_key] = float(env_value)
                    except ValueError:
                        logger.debug(
                            "环境变量 %s 值 '%s' 无法转换为float，使用默认值", env_key, env_value
                        )

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self._config.get(key, default)

    def is_enabled(self, feature: str) -> bool:
        """检查功能是否启用"""
        return bool(self._config.get(f"{feature}_enabled", False))

    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        self._config[key] = value

    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return dict(self._config)


# 全局配置实例
optimization_config = OptimizationConfig()


def get_optimization_config() -> OptimizationConfig:
    """获取全局优化配置"""
    return optimization_config


def enable_feature(feature: str) -> None:
    """启用指定功能"""
    optimization_config.set(f"{feature}_enabled", True)


def disable_feature(feature: str) -> None:
    """禁用指定功能"""
    optimization_config.set(f"{feature}_enabled", False)


def is_feature_enabled(feature: str) -> bool:
    """检查功能是否启用"""
    return optimization_config.is_enabled(feature)
