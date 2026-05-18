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
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(Enum):
    """事件类型枚举"""

    # 引擎生命周期事件
    ENGINE_START = "engine.start"
    ENGINE_STOP = "engine.stop"
    ENGINE_PROGRESS = "engine.progress"
    ENGINE_MATCH = "engine.match"
    ENGINE_ERROR = "engine.error"
    ENGINE_COMPLETE = "engine.complete"


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

    event_type: EventType | None = field(default=None)
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "collision_engine"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type.value if self.event_type else None,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "metadata": self.metadata,
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
        self.metadata.update(
            {"mode": self.mode, "target_count": self.target_count, "batch_size": self.batch_size}
        )


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
        self.metadata.update(
            {
                "total_checked": self.total_checked,
                "speed": self.speed,
                "avg_speed": self.avg_speed,
                "matches_found": self.matches_found,
            }
        )


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
        # 安全脱敏: metadata中的地址仅保留前6和后4字符
        masked_addr = self.address if len(self.address) <= 10 else f"{self.address[:6]}...{self.address[-4:]}"
        masked_target = self.target_address if len(self.target_address) <= 10 else f"{self.target_address[:6]}...{self.target_address[-4:]}"
        self.metadata.update({"address": masked_addr, "target_address": masked_target})

    def __repr__(self) -> str:
        """安全repr: 遮蔽 wif 和 private_key 防止日志泄露。"""
        return (
            f"EngineMatchEvent("
            f"address={self.address!r}, "
            f"target_address={self.target_address!r}, "
            f"wif=<REDACTED>, private_key=<REDACTED>)"
        )


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
    exception: Exception | None = None
    context: dict[str, Any] = field(default_factory=dict)
    recoverable: bool = False

    def __post_init__(self) -> None:
        self.event_type = EventType.ENGINE_ERROR
        self.metadata.update(
            {
                "error_type": self.error_type,
                "error_message": self.error_message,
                "recoverable": self.recoverable,
            }
        )


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
        self.metadata.update(
            {
                "total_checked": self.total_checked,
                "matches_found": self.matches_found,
                "elapsed_time": self.elapsed_time,
                "avg_speed": self.avg_speed,
                "stop_reason": self.stop_reason,
            }
        )


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
            "total_checked": self.total_checked,
        })
