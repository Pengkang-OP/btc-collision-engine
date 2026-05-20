"""碰撞引擎观察者模式接口

定义观察者接口，用于解耦碰撞引擎与监控系统、日志系统等。
"""

import hashlib
import logging
import threading
from abc import ABC, abstractmethod
from typing import Any

from .collision_stats import CollisionStats

logger = logging.getLogger(__name__)


class CollisionObserver(ABC):
    """碰撞引擎观察者接口

    实现此接口的类可以订阅碰撞引擎的事件通知，
    实现松耦合的监控、日志、告警等功能。
    """

    @abstractmethod
    def on_progress(self, stats: CollisionStats) -> None:
        """进度更新事件

        Args:
            stats: 当前碰撞统计信息
        """

    @abstractmethod
    def on_match(self, private_key: bytes, address: str, wif: str) -> None:
        """匹配成功事件

        Args:
            private_key: 匹配的私钥（bytes）
            address: 匹配的地址
            wif: WIF格式私钥
        """

    @abstractmethod
    def on_complete(self, stats: CollisionStats) -> None:
        """碰撞完成事件

        Args:
            stats: 最终碰撞统计信息
        """

    def on_error(self, error: Exception, context: dict[str, Any] | None = None) -> None:
        """错误事件（可选实现）

        Args:
            error: 异常对象
            context: 错误上下文信息
        """


class BaseCollisionObserver(CollisionObserver):
    """观察者基类，提供默认实现

    子类可以选择性覆盖需要的方法。
    """

    def on_progress(self, stats: CollisionStats) -> None:
        """默认不处理进度事件"""

    def on_match(self, private_key: bytes, address: str, wif: str) -> None:
        """默认不处理匹配事件"""

    def on_complete(self, stats: CollisionStats) -> None:
        """默认不处理完成事件"""

    def on_error(self, error: Exception, context: dict[str, Any] | None = None) -> None:
        """默认不处理错误事件"""


class MonitoringObserver(BaseCollisionObserver):
    """监控观察者 - 集成监控系统

    将碰撞引擎事件转发到监控系统。
    """

    def __init__(self, monitoring_system: Any) -> None:
        """
        Args:
            monitoring_system: EnhancedMonitoringSystem实例
        """
        self.monitoring_system = monitoring_system

    def on_progress(self, stats: CollisionStats) -> None:
        """转发进度事件到监控系统

        监控系统会自动采集数据（轮询 stats），此方法仅确认事件已触发。
        """
        logger.debug(f"进度事件: 已检查 {stats.total_checked:,} 个密钥")

    def on_match(self, private_key: bytes, address: str, wif: str) -> None:
        """记录匹配事件到监控数据日志"""
        if hasattr(self.monitoring_system, "data_logger"):
            self.monitoring_system.data_logger.record_error(
                error_type="MatchFound",
                error_message=f"地址匹配: {address}",
                context={"address": address, "has_wif": bool(wif)},
            )

    def on_error(self, error: Exception, context: dict[str, Any] | None = None) -> None:
        """记录错误事件"""
        if hasattr(self.monitoring_system, "data_logger"):
            self.monitoring_system.data_logger.record_error(
                error_type=type(error).__name__, error_message=str(error), context=context
            )


class LoggingObserver(BaseCollisionObserver):
    """日志观察者 - 记录碰撞事件到日志

    专门用于记录碰撞引擎的关键事件。
    """

    def __init__(self, logger: Any) -> None:
        """
        Args:
            logger: logging.Logger实例
        """
        self.logger = logger

    def on_progress(self, stats: CollisionStats) -> None:
        """记录进度日志（采样）"""
        # 每10000次记录一次，避免日志洪水
        if stats.total_checked % 10000 == 0:
            self.logger.info(
                f"碰撞进度: 已检测={stats.total_checked:,}, 速度={stats.speed:.2f}/s, 匹配={len(stats.matches)}"
            )

    def on_match(self, private_key: bytes, address: str, wif: str) -> None:
        """记录匹配日志（安全：仅输出地址和密钥哈希，不泄露私钥）"""
        key_hash = hashlib.sha256(private_key).hexdigest()[:16]
        self.logger.info("匹配发现: address=%s, key_hash=KEY_HASH:%s", address, key_hash)

    def on_complete(self, stats: CollisionStats) -> None:
        """记录完成日志"""
        self.logger.info(
            f"碰撞完成: 总检测={stats.total_checked:,}, 总匹配={len(stats.matches)}, 运行时间={stats.format_elapsed()}"
        )


class ObserverManager:
    """观察者管理器

    管理多个观察者，提供批量通知功能。
    线程安全：所有公开方法均受锁保护。
    """

    def __init__(self) -> None:
        self._observers: list[CollisionObserver] = []
        self._lock = threading.Lock()

    def add_observer(self, observer: CollisionObserver) -> None:
        """添加观察者

        Args:
            observer: 观察者实例
        """
        if not isinstance(observer, CollisionObserver):
            raise TypeError("observer必须是CollisionObserver实例")

        with self._lock:
            self._observers.append(observer)

    def remove_observer(self, observer: CollisionObserver) -> bool:
        """移除观察者

        Args:
            observer: 观察者实例

        Returns:
            bool: 移除成功返回True
        """
        with self._lock:
            try:
                self._observers.remove(observer)
                return True
            except ValueError:
                return False

    def _notify_safe(
        self,
        observers_snapshot: list[CollisionObserver],
        callback_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """在锁外安全地遍历观察者快照并调用回调"""
        for observer in observers_snapshot:
            try:
                getattr(observer, callback_name)(*args, **kwargs)
            except Exception as e:
                logging.getLogger(__name__).error("观察者%s回调失败: %s", callback_name, e)

    def notify_progress(self, stats: CollisionStats) -> None:
        """通知所有观察者进度更新

        Args:
            stats: 碰撞统计信息
        """
        with self._lock:
            snapshot = list(self._observers)
        self._notify_safe(snapshot, "on_progress", stats)

    def notify_match(self, private_key: bytes, address: str, wif: str) -> None:
        """通知所有观察者匹配成功

        Args:
            private_key: 匹配的私钥
            address: 匹配的地址
            wif: WIF格式私钥
        """
        with self._lock:
            snapshot = list(self._observers)
        self._notify_safe(snapshot, "on_match", private_key, address, wif)

    def notify_complete(self, stats: CollisionStats) -> None:
        """通知所有观察者碰撞完成

        Args:
            stats: 最终统计信息
        """
        with self._lock:
            snapshot = list(self._observers)
        self._notify_safe(snapshot, "on_complete", stats)

    def notify_error(self, error: Exception, context: dict[str, Any] | None = None) -> None:
        """通知所有观察者错误事件

        Args:
            error: 异常对象
            context: 错误上下文
        """
        with self._lock:
            snapshot = list(self._observers)
        self._notify_safe(snapshot, "on_error", error, context)

    def clear(self) -> None:
        """清空所有观察者"""
        with self._lock:
            self._observers.clear()

    @property
    def observer_count(self) -> int:
        """获取观察者数量"""
        with self._lock:
            return len(self._observers)
