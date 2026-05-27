"""GPU 模块接口抽象层 (ARCH-1修复).

定义 GPU 子系统核心接口，降低碰撞引擎与 GPU 实现的耦合度。
Facade 和具体实现通过接口解耦，便于测试和替换。
"""

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class GPUDeviceProtocol(Protocol):
    """GPU 设备协议（鸭子类型接口）."""

    device_index: int
    context: Any

    def get_memory_info(self) -> dict[str, Any]:
        """Get GPU memory info."""
        ...

    def cleanup(self) -> None:
        """Cleanup GPU resources."""
        ...


class GPUCollisionEngineInterface(ABC):
    """GPU 碰撞引擎抽象接口."""

    @abstractmethod
    def set_target_addresses(self, targets: list[str]) -> None:
        """设置目标地址列表."""

    @abstractmethod
    def start(self, mode: str = "random", batch_size: int = 10000) -> None:
        """启动碰撞检测."""

    @abstractmethod
    def stop(self) -> None:
        """停止碰撞检测."""

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """获取碰撞统计信息."""

    @abstractmethod
    def get_device_info(self) -> dict[str, Any]:
        """获取设备信息."""


class GPUDriverInterface(ABC):
    """GPU 驱动管理抽象接口."""

    @abstractmethod
    def detect_gpu(self) -> bool:
        """检测 GPU 是否可用."""

    @abstractmethod
    def get_gpu_count(self) -> int:
        """获取 GPU 数量."""

    @abstractmethod
    def list_devices(self) -> list[dict[str, Any]]:
        """列出所有 GPU 设备."""


class GPUMemoryPoolInterface(ABC):
    """GPU 内存池抽象接口."""

    @abstractmethod
    def allocate(self, size: int, flags: Any = None, buffer_type: str = "generic") -> Any:
        """分配 GPU 内存."""

    @abstractmethod
    def release(self, buf: Any, size: int | None = None, buffer_type: str = "generic") -> None:
        """归还 GPU 内存到池."""

    @abstractmethod
    def clear(self) -> None:
        """清空内存池."""

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """获取内存池统计信息."""
