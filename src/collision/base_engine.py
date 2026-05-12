"""碰撞引擎抽象基类

定义CPU和GPU碰撞引擎的统一接口。
"""

from abc import ABC, abstractmethod
from typing import Any

from .collision_stats import CollisionStats


class BaseCollisionEngine(ABC):
    """碰撞引擎抽象基类

    所有碰撞引擎(CPU/GPU)必须实现此接口。
    """

    @abstractmethod
    def __init__(self, targets: set[str], **kwargs) -> None:
        """
        初始化碰撞引擎

        参数:
            targets: 目标地址集合
            **kwargs: 引擎特定参数
        """

    @abstractmethod
    def start(self, mode: str = "random", resume: bool = False, **kwargs) -> None:
        """
        启动碰撞引擎

        参数:
            mode: 运行模式 ("random", "range", "brute_force")
            resume: 是否从断点恢复
            **kwargs: 模式特定参数
                     - range模式: start, end
                     - brute_force模式: start
        """

    @abstractmethod
    def stop(self, timeout: float | None = None) -> None:
        """
        停止碰撞引擎

        参数:
            timeout: 等待停止的超时时间(秒)
        """

    @abstractmethod
    def is_running(self) -> bool:
        """
        检查引擎是否正在运行

        返回:
            True表示引擎正在运行
        """

    @abstractmethod
    def get_stats(self) -> CollisionStats:
        """
        获取碰撞统计信息

        返回:
            CollisionStats对象
        """

    def get_device_info(self) -> dict[str, Any]:
        """
        获取设备信息

        返回:
            设备信息字典
        """
        return {}

    def get_supported_modes(self) -> list:
        """
        获取支持的运行模式

        返回:
            支持的模式列表
        """
        return ["random", "range", "brute_force"]
