"""监控系统配置

独立的配置对象，避免监控系统和数据日志之间的循环依赖（P1-2修复）。
集中管理监控相关配置，解耦EnhancedMonitoringSystem和DataLogger。

创建日期: 2026-04-22
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any


@dataclass
class MonitorConfig:
    """监控系统配置

    集中管理监控相关配置，解耦EnhancedMonitoringSystem和DataLogger。

    使用示例:
        >>> from src.monitoring.monitor_config import MonitorConfig
        >>>
        >>> # 使用默认配置
        >>> config = MonitorConfig()
        >>>
        >>> # 从字典创建
        >>> config = MonitorConfig.from_dict({
        ...     'data_logging_enabled': True,
        ...     'data_logging_interval': 2.0
        ... })
        >>>
        >>> # 转换为字典
        >>> config_dict = config.to_dict()
    """

    # ========== 数据日志配置 ==========
    data_logging_enabled: bool = True
    """是否启用数据日志"""

    data_logging_interval: float = 1.0
    """数据日志记录间隔（秒）"""

    data_log_save_frequency: int = 10
    """数据保存频率（每N次记录保存一次）"""

    # ========== 监控配置 ==========
    enable_monitoring_data: bool = False
    """是否启用监控数据采集"""

    collection_interval: float = 1.0
    """监控数据采集间隔（秒）"""

    enable_gpu_monitoring: bool = True
    """是否启用GPU监控"""

    gpu_monitoring_interval: float = 5.0
    """GPU监控采集间隔（秒）"""

    # ========== 告警配置 ==========
    alert_enabled: bool = True
    """是否启用告警系统"""

    alert_threshold: float = 0.9
    """告警阈值（0.0-1.0）"""

    alert_cooldown: float = 300.0
    """告警冷却时间（秒）"""

    max_alerts_per_hour: int = 60
    """每小时最大告警数"""

    # ========== 报告配置 ==========
    report_enabled: bool = False
    """是否启用报告生成"""

    report_interval: float = 3600.0
    """报告生成间隔（秒）"""

    report_save_path: str = "data_logs"
    """报告保存路径"""

    # ========== 性能优化配置 ==========
    enable_performance_optimization: bool = True
    """是否启用性能优化"""

    auto_adjust_batch_size: bool = True
    """是否自动调整batch_size"""

    performance_log_interval: float = 10.0
    """性能日志记录间隔（秒）"""

    # ========== 高级配置 ==========
    enable_debug_mode: bool = False
    """是否启用调试模式"""

    max_log_entries: int = 10000
    """最大日志条目数"""

    cleanup_interval: float = 86400.0
    """清理间隔（秒，默认24小时）"""

    # P3优化：dataclass初始化后自动验证
    def __post_init__(self) -> None:
        """dataclass初始化后自动调用验证

        确保配置对象创建时就是有效的。
        如需创建无效配置（如从JSON加载），使用from_dict()方法。
        """
        try:
            self.validate()
        except ValueError as e:
            # 不阻止配置创建，只记录警告
            import logging

            logging.getLogger(__name__).warning(f"配置验证警告: {e}")

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "MonitorConfig":
        """从字典创建配置

        Args:
            config: 配置字典

        Returns:
            MonitorConfig实例

        Example:
            >>> config = MonitorConfig.from_dict({
            ...     'data_logging_enabled': True,
            ...     'alert_threshold': 0.85
            ... })
        """
        # 过滤掉不存在的字段
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_config = {k: v for k, v in config.items() if k in valid_fields}

        return cls(**filtered_config)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            配置字典

        Example:
            >>> config = MonitorConfig()
            >>> config_dict = config.to_dict()
            >>> print(config_dict['data_logging_enabled'])
            True
        """
        return asdict(self)

    def update(self, **kwargs) -> "MonitorConfig":
        """更新配置

        Args:
            **kwargs: 要更新的配置项

        Returns:
            self（支持链式调用）

        Example:
            >>> config = MonitorConfig()
            >>> config.update(data_logging_interval=2.0, alert_enabled=False)
        """
        valid_fields = {f.name for f in self.__class__.__dataclass_fields__.values()}

        for key, value in kwargs.items():
            if key in valid_fields:
                setattr(self, key, value)
            else:
                raise ValueError(f"未知配置项: {key}")

        return self

    def validate(self) -> bool:
        """验证配置有效性

        Returns:
            配置是否有效

        Raises:
            ValueError: 配置无效时抛出异常
        """
        # 验证数值范围
        if not 0.0 <= self.alert_threshold <= 1.0:
            raise ValueError(f"alert_threshold必须在0.0-1.0之间，当前: {self.alert_threshold}")

        # 验证时间间隔(必须大于0)
        time_intervals = [
            ("data_logging_interval", self.data_logging_interval),
            ("collection_interval", self.collection_interval),
            ("gpu_monitoring_interval", self.gpu_monitoring_interval),
            ("alert_cooldown", self.alert_cooldown),
            ("report_interval", self.report_interval),
            ("performance_log_interval", self.performance_log_interval),
            ("cleanup_interval", self.cleanup_interval),
        ]

        for name, value in time_intervals:
            if value <= 0:
                raise ValueError(f"{name}必须大于0，当前: {value}")

        # 验证计数(必须大于0)
        counters = [
            ("data_log_save_frequency", self.data_log_save_frequency),
            ("max_alerts_per_hour", self.max_alerts_per_hour),
            ("max_log_entries", self.max_log_entries),
        ]

        for name, value in counters:
            if value <= 0:
                raise ValueError(f"{name}必须大于0，当前: {value}")

        return True

    def merge(self, other: "MonitorConfig") -> "MonitorConfig":
        """合并配置

        other配置优先于当前配置。
        other中的所有值都会覆盖self的对应值（包括默认值）。

        Args:
            other: 另一个配置对象（优先级更高）

        Returns:
            合并后的新配置

        Example:
            >>> config1 = MonitorConfig(alert_threshold=0.8)
            >>> config2 = MonitorConfig(alert_threshold=0.9)
            >>> merged = config1.merge(config2)
            >>> merged.alert_threshold
            0.9
        """
        merged = self.to_dict()
        other_dict = other.to_dict()

        # P2修复：other的所有值都覆盖self（保持other的优先级）
        for key, value in other_dict.items():
            merged[key] = value

        return MonitorConfig.from_dict(merged)

    def __str__(self) -> str:
        """配置字符串表示"""
        items = []
        for field_name, field_value in asdict(self).items():
            # 只显示非默认值
            default_value = getattr(self.__class__(), field_name)
            if field_value != default_value:
                items.append(f"{field_name}={field_value}")

        if items:
            return f"MonitorConfig({', '.join(items)})"
        return "MonitorConfig(默认配置)"


# 预定义配置模板

DEFAULT_CONFIG = MonitorConfig()
"""默认配置"""

PRODUCTION_CONFIG = MonitorConfig(
    data_logging_enabled=True,
    data_logging_interval=5.0,
    enable_monitoring_data=True,
    collection_interval=5.0,
    alert_enabled=True,
    alert_threshold=0.95,
    report_enabled=True,
    report_interval=3600.0,
    enable_debug_mode=False,
)
"""生产环境配置"""

DEVELOPMENT_CONFIG = MonitorConfig(
    data_logging_enabled=True,
    data_logging_interval=1.0,
    enable_monitoring_data=True,
    collection_interval=1.0,
    alert_enabled=True,
    alert_threshold=0.8,
    report_enabled=False,
    enable_debug_mode=True,
    max_alerts_per_hour=120,
)
"""开发环境配置"""

TESTING_CONFIG = MonitorConfig(
    data_logging_enabled=False,
    enable_monitoring_data=False,
    alert_enabled=False,
    report_enabled=False,
    enable_performance_optimization=False,
    enable_debug_mode=False,
)
"""测试环境配置（最小化）"""
