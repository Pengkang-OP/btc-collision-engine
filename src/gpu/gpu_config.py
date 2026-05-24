"""GPU 模块配置数据结构

定义类型安全的配置 dataclass，替代嵌套 dict 配置传递模式。
提供从 dict 构造和从默认值构造的工厂方法。

使用示例:
    >>> config = MultiGPUConfig.from_dict({'enable_data_monitor': True})
    >>> engine = MultiGPUCollisionEngine(config=config)

    >>> worker_config = WorkerConfig(batch_size=65536)
    >>> worker = SingleGPUWorker(..., config=worker_config)
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GPURecoveryConfig:
    """GPU 恢复管理器配置

    控制 GPU 故障后的自动恢复行为。
    """

    max_retry_count: int = 3
    retry_delay_seconds: float = 5.0
    batch_size_reduction_factor: float = 0.5
    auto_redistribute: bool = True

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None = None) -> "GPURecoveryConfig":
        """从 dict 构造（兼容旧接口）"""
        if not d:
            return cls()
        return cls(
            max_retry_count=d.get("max_retry_count", 3),
            retry_delay_seconds=d.get("retry_delay_seconds", 5.0),
            batch_size_reduction_factor=d.get("batch_size_reduction_factor", 0.5),
            auto_redistribute=d.get("auto_redistribute", True),
        )


@dataclass
class DataMonitorConfig:
    """数据监控器配置

    兼容 DataMonitor 的所有配置项，支持 dict-like .get() 访问。
    """

    check_interval: float = 1.0
    throughput_threshold: float = 0.5
    error_rate_threshold: float = 0.1
    stale_data_timeout: float = 10.0
    max_issues_per_minute: int = 100
    max_seen_keys: int = 100000
    max_seen_addresses: int = 10000
    max_retry_count: int = 3
    anomaly_threshold: float = 0.1

    def get(self, key: str, default: Any = None) -> Any:
        """dict-like 访问（兼容旧 DataMonitor 代码）"""
        return getattr(self, key, default)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None = None) -> "DataMonitorConfig":
        """从 dict 构造"""
        if not d:
            return cls()
        return cls(
            check_interval=d.get("check_interval", 1.0),
            throughput_threshold=d.get("throughput_threshold", 0.5),
            error_rate_threshold=d.get("error_rate_threshold", 0.1),
            stale_data_timeout=d.get("stale_data_timeout", 10.0),
            max_issues_per_minute=d.get("max_issues_per_minute", 100),
            max_seen_keys=d.get("max_seen_keys", 100000),
            max_seen_addresses=d.get("max_seen_addresses", 10000),
            max_retry_count=d.get("max_retry_count", 3),
            anomaly_threshold=d.get("anomaly_threshold", 0.1),
        )


@dataclass
class MultiGPUConfig:
    """多 GPU 引擎配置

    所有可配置参数集中在 dataclass 中，提供类型安全和 IDE 自动补全。
    替代原来的 `config: Dict` 嵌套字典传递模式。

    Attributes:
        total_pool_mb: 总内存池大小 (MB)
        enable_data_monitor: 是否启用数据监控
        data_monitor: 数据监控器配置
        gpu_recovery: GPU 恢复管理器配置
        worker_join_timeout: 等待工作器停止的超时 (秒)
        workload_monitor_interval: 工作负载监控间隔 (秒)
        auto_rebalance: 是否启用自动重平衡
        auto_pause_on_critical: 严重异常时是否自动暂停 GPU
        per_device_config: 每个设备的独立配置覆盖

    """

    total_pool_mb: int = 512
    enable_data_monitor: bool = True
    data_monitor: DataMonitorConfig = field(default_factory=DataMonitorConfig)
    gpu_recovery: GPURecoveryConfig = field(default_factory=GPURecoveryConfig)
    worker_join_timeout: int = 30
    workload_monitor_interval: int = 5
    auto_rebalance: bool = True
    auto_pause_on_critical: bool = False
    per_device_config: dict[str, dict[str, Any]] = field(default_factory=dict)
    # P2修复: 性能历史记录最大条数（可配置化，默认100）
    performance_history_max_size: int = 100

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None = None) -> "MultiGPUConfig":
        """从 dict 构造（兼容旧接口，渐进式迁移用）

        Args:
            d: 旧版配置字典，为 None 时使用所有默认值

        Returns:
            MultiGPUConfig 实例

        """
        if not d:
            return cls()
        return cls(
            total_pool_mb=d.get("total_pool_mb", 512),
            enable_data_monitor=d.get("enable_data_monitor", True),
            data_monitor=DataMonitorConfig.from_dict(d.get("data_monitor")),
            gpu_recovery=GPURecoveryConfig.from_dict(d.get("gpu_recovery")),
            worker_join_timeout=d.get("worker_join_timeout", 30),
            workload_monitor_interval=d.get("workload_monitor_interval", 5),
            auto_rebalance=d.get("auto_rebalance", True),
            auto_pause_on_critical=d.get("auto_pause_on_critical", False),
            per_device_config=d.get("per_device_config", {}),
            performance_history_max_size=d.get("performance_history_max_size", 100),
        )


@dataclass
class WorkerConfig:
    """单个 GPU 工作器配置

    Attributes:
        batch_size: 批次大小 (None 表示自动计算)
        work_group_size: OpenCL 工作组大小
        max_memory_mb: 最大内存使用 (MB)

    """

    batch_size: int | None = None
    work_group_size: int = 256
    max_memory_mb: int | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None = None) -> "WorkerConfig":
        """从 dict 构造（兼容旧接口）"""
        if not d:
            return cls()
        return cls(
            batch_size=d.get("batch_size"),
            work_group_size=d.get("work_group_size", 256),
            max_memory_mb=d.get("max_memory_mb"),
        )

    def to_dict(self) -> dict[str, Any]:
        """转换回 dict（兼容需要 dict 的旧接口）"""
        result: dict[str, Any] = {
            "batch_size": self.batch_size,
            "work_group_size": self.work_group_size,
        }
        if self.max_memory_mb is not None:
            result["max_memory_mb"] = self.max_memory_mb
        return result
