"""碰撞插件基础类"""

from abc import ABC, abstractmethod
from typing import Set, Optional, Callable, Tuple

# 使用相对导入而非绝对导入，避免包外部导入失败
from ..collision_stats import CollisionStats


class CollisionPlugin(ABC):
    """碰撞插件基础类，定义插件接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """插件描述"""
        pass

    @abstractmethod
    def initialize(self, targets: Set[str], **kwargs) -> None:
        """
        初始化插件

        参数:
            targets: 目标地址集合（只读，插件不得修改）
            kwargs: 其他参数
        """
        pass

    @abstractmethod
    def start(
        self,
        on_progress: Optional[Callable[["CollisionStats"], None]] = None,
        on_match: Optional[Callable[[bytes, str, str], None]] = None,
        on_complete: Optional[Callable[["CollisionStats"], None]] = None,
    ) -> None:
        """
        开始碰撞

        参数:
            on_progress: 进度回调 - 签名: (stats: CollisionStats) -> None
            on_match: 匹配回调 - 签名: (private_key: bytes, address: str, wif: str) -> None
                     【安全约束】插件实现必须遵守：
                     1. 不得在日志或文件中记录私钥原文
                     2. 不得将私钥数据发送到远程服务器
                     3. 使用后应立即释放私钥引用
            on_complete: 完成回调 - 签名: (stats: CollisionStats) -> None
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """停止碰撞"""
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """是否正在运行"""
        pass

    @abstractmethod
    def get_stats(self) -> CollisionStats:
        """获取统计数据"""
        pass
