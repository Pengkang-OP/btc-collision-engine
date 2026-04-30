"""碰撞引擎事件定义

定义碰撞引擎运行时产生的各类事件，用于解耦引擎与监控/日志系统。

使用示例:
    >>> from src.collision.events import EngineProgressEvent, EventType
    >>> 
    >>> # 创建事件
    >>> event = EngineProgressEvent(
    ...     total_checked=1000000,
    ...     speed=537000.0,
    ...     matches_found=0
    ... )
    >>> 
    >>> # 访问事件属性
    >>> print(f"速度: {event.speed} keys/s")
    >>> print(f"事件类型: {event.event_type.value}")
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime


class EventType(Enum):
    """事件类型枚举"""
    
    # 引擎生命周期事件
    ENGINE_START = "engine.start"
    ENGINE_STOP = "engine.stop"
    ENGINE_PROGRESS = "engine.progress"
    ENGINE_MATCH = "engine.match"
    ENGINE_ERROR = "engine.error"
    ENGINE_COMPLETE = "engine.complete"
    
    # GPU特定事件
    GPU_KERNEL_EXEC = "gpu.kernel.exec"
    GPU_MEMORY_ALLOC = "gpu.memory.alloc"
    GPU_MEMORY_FREE = "gpu.memory.free"
    GPU_ERROR = "gpu.error"
    
    # 监控系统事件
    MONITORING_DATA_SAVED = "monitoring.data.saved"
    MONITORING_ALERT = "monitoring.alert"
    MONITORING_ANOMALY = "monitoring.anomaly"


@dataclass
class CollisionEvent:
    """
    碰撞事件基类
    
    所有碰撞引擎事件的基类，包含通用属性。
    
    Attributes:
        event_type: 事件类型
        timestamp: 事件发生时间
        source: 事件来源 (模块名称)
        metadata: 附加元数据
    """
    event_type: Optional[EventType] = field(default=None)
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "collision_engine"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type.value if self.event_type else None,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "metadata": self.metadata
        }


@dataclass
class EngineStartEvent(CollisionEvent):
    """
    引擎启动事件
    
    Attributes:
        mode: 运行模式 (random/range/brute)
        target_count: 目标地址数量
        batch_size: 批次大小
    """
    mode: str = "random"
    target_count: int = 0
    batch_size: int = 0
    
    def __post_init__(self) -> None:
        self.event_type = EventType.ENGINE_START
        self.metadata.update({
            "mode": self.mode,
            "target_count": self.target_count,
            "batch_size": self.batch_size
        })


@dataclass
class EngineProgressEvent(CollisionEvent):
    """
    引擎进度事件
    
    定期发布，用于更新监控数据和进度显示。
    
    Attributes:
        total_checked: 已检测密钥总数
        speed: 当前速度 (keys/s)
        avg_speed: 平均速度 (keys/s)
        matches_found: 发现匹配数
        cpu_usage: CPU使用率 (%)
        memory_usage: 内存使用 (MB)
        thread_count: 线程数
        elapsed_time: 运行时长 (秒)
    """
    total_checked: int = 0
    speed: float = 0.0
    avg_speed: float = 0.0
    matches_found: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    thread_count: int = 0
    elapsed_time: float = 0.0
    
    def __post_init__(self) -> None:
        self.event_type = EventType.ENGINE_PROGRESS
        self.metadata.update({
            "total_checked": self.total_checked,
            "speed": self.speed,
            "avg_speed": self.avg_speed,
            "matches_found": self.matches_found
        })


@dataclass
class EngineMatchEvent(CollisionEvent):
    """
    引擎匹配事件
    
    发现目标地址匹配时触发。
    
    ⚠️ 安全注意:
        private_key 包含敏感信息，使用后应立即清零。
    
    Attributes:
        private_key: 匹配的私钥 (bytes)
        address: 生成的地址
        wif: WIF格式私钥
        target_address: 匹配的目标地址
    """
    private_key: bytes = b""
    address: str = ""
    wif: str = ""
    target_address: str = ""
    
    def __post_init__(self) -> None:
        self.event_type = EventType.ENGINE_MATCH
        # 不将private_key放入metadata (安全考虑)
        self.metadata.update({
            "address": self.address,
            "target_address": self.target_address
        })


@dataclass
class EngineErrorEvent(CollisionEvent):
    """
    引擎错误事件
    
    Attributes:
        error_type: 错误类型
        error_message: 错误消息
        exception: 异常对象 (可选)
        context: 错误上下文
        recoverable: 是否可恢复
    """
    error_type: str = ""
    error_message: str = ""
    exception: Optional[Exception] = None
    context: Dict[str, Any] = field(default_factory=dict)
    recoverable: bool = False
    
    def __post_init__(self) -> None:
        self.event_type = EventType.ENGINE_ERROR
        self.metadata.update({
            "error_type": self.error_type,
            "error_message": self.error_message,
            "recoverable": self.recoverable
        })


@dataclass
class EngineCompleteEvent(CollisionEvent):
    """
    引擎完成事件
    
    Attributes:
        total_checked: 总检测数
        matches_found: 匹配数
        elapsed_time: 总运行时长 (秒)
        avg_speed: 平均速度 (keys/s)
        stop_reason: 停止原因 (normal/error/interrupted)
    """
    total_checked: int = 0
    matches_found: int = 0
    elapsed_time: float = 0.0
    avg_speed: float = 0.0
    stop_reason: str = "normal"
    
    def __post_init__(self) -> None:
        self.event_type = EventType.ENGINE_COMPLETE
        self.metadata.update({
            "total_checked": self.total_checked,
            "matches_found": self.matches_found,
            "elapsed_time": self.elapsed_time,
            "avg_speed": self.avg_speed,
            "stop_reason": self.stop_reason
        })


@dataclass
class EngineStopEvent(CollisionEvent):
    """
    引擎停止事件
    
    Attributes:
        reason: 停止原因
        total_checked: 停止时已检测数
    """
    reason: str = "user_request"
    total_checked: int = 0
    
    def __post_init__(self) -> None:
        self.event_type = EventType.ENGINE_STOP
        self.metadata.update({
            "reason": self.reason,
            "total_checked": self.total_checked
        })


# GPU特定事件

@dataclass
class GPUKernelExecEvent(CollisionEvent):
    """
    GPU内核执行事件
    
    Attributes:
        kernel_name: 内核名称
        batch_size: 批次大小
        exec_time: 执行时间 (秒)
        device_index: GPU设备索引
    """
    kernel_name: str = ""
    batch_size: int = 0
    exec_time: float = 0.0
    device_index: int = 0
    
    def __post_init__(self) -> None:
        self.event_type = EventType.GPU_KERNEL_EXEC
        self.metadata.update({
            "kernel_name": self.kernel_name,
            "batch_size": self.batch_size,
            "exec_time": self.exec_time,
            "device_index": self.device_index
        })


@dataclass
class GPUErrorEvent(CollisionEvent):
    """
    GPU错误事件
    
    Attributes:
        error_type: 错误类型 (compilation/execution/memory)
        error_message: 错误消息
        device_index: GPU设备索引
        recoverable: 是否可恢复
    """
    error_type: str = ""
    error_message: str = ""
    device_index: int = 0
    recoverable: bool = False
    
    def __post_init__(self) -> None:
        self.event_type = EventType.GPU_ERROR
        self.metadata.update({
            "error_type": self.error_type,
            "device_index": self.device_index,
            "recoverable": self.recoverable
        })


# 监控系统事件

@dataclass
class MonitoringAlertEvent(CollisionEvent):
    """
    监控告警事件
    
    Attributes:
        alert_type: 告警类型
        alert_message: 告警消息
        severity: 严重程度 (info/warning/critical)
        metrics: 相关指标
    """
    alert_type: str = ""
    alert_message: str = ""
    severity: str = "info"
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        self.event_type = EventType.MONITORING_ALERT
        self.metadata.update({
            "alert_type": self.alert_type,
            "severity": self.severity
        })


@dataclass
class MonitoringAnomalyEvent(CollisionEvent):
    """
    监控异常事件
    
    Attributes:
        anomaly_type: 异常类型
        metric_name: 指标名称
        current_value: 当前值
        expected_range: 预期范围 (min, max)
        deviation: 偏离度
    """
    anomaly_type: str = ""
    metric_name: str = ""
    current_value: float = 0.0
    expected_range: tuple = (0.0, 0.0)
    deviation: float = 0.0
    
    def __post_init__(self) -> None:
        self.event_type = EventType.MONITORING_ANOMALY
        self.metadata.update({
            "anomaly_type": self.anomaly_type,
            "metric_name": self.metric_name,
            "current_value": self.current_value,
            "deviation": self.deviation
        })
