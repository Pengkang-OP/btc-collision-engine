"""碰撞引擎观察者模式接口

定义观察者接口，用于解耦碰撞引擎与监控系统、日志系统等。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from .collision_stats import CollisionStats


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
        pass
    
    @abstractmethod
    def on_match(self, private_key: bytes, address: str, wif: str) -> None:
        """匹配成功事件
        
        Args:
            private_key: 匹配的私钥（bytes）
            address: 匹配的地址
            wif: WIF格式私钥
        """
        pass
    
    @abstractmethod
    def on_complete(self, stats: CollisionStats) -> None:
        """碰撞完成事件
        
        Args:
            stats: 最终碰撞统计信息
        """
        pass
    
    def on_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """错误事件（可选实现）
        
        Args:
            error: 异常对象
            context: 错误上下文信息
        """
        pass


class BaseCollisionObserver(CollisionObserver):
    """观察者基类，提供默认实现
    
    子类可以选择性覆盖需要的方法。
    """
    
    def on_progress(self, stats: CollisionStats) -> None:
        """默认不处理进度事件"""
        pass
    
    def on_match(self, private_key: bytes, address: str, wif: str) -> None:
        """默认不处理匹配事件"""
        pass
    
    def on_complete(self, stats: CollisionStats) -> None:
        """默认不处理完成事件"""
        pass
    
    def on_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """默认不处理错误事件"""
        pass


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
        """转发进度事件到监控系统"""
        # 监控系统会自动采集数据，这里仅触发采集
        pass
    
    def on_match(self, private_key: bytes, address: str, wif: str) -> None:
        """记录匹配事件"""
        if hasattr(self.monitoring_system, 'data_logger'):
            # 可以在这里记录匹配事件到日志
            pass
    
    def on_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """记录错误事件"""
        if hasattr(self.monitoring_system, 'data_logger'):
            self.monitoring_system.data_logger.record_error(
                error_type=type(error).__name__,
                error_message=str(error),
                context=context
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
                f"碰撞进度: 已检测={stats.total_checked:,}, "
                f"速度={stats.speed:.2f}/s, "
                f"匹配={len(stats.matches)}"
            )
    
    def on_match(self, private_key: bytes, address: str, wif: str) -> None:
        """记录匹配日志"""
        self.logger.warning(
            f"🎉 找到匹配! 地址={address}, "
            f"私钥(WIF)={wif[:10]}..."
        )
    
    def on_complete(self, stats: CollisionStats) -> None:
        """记录完成日志"""
        self.logger.info(
            f"碰撞完成: 总检测={stats.total_checked:,}, "
            f"总匹配={len(stats.matches)}, "
            f"运行时间={stats.format_elapsed()}"
        )


class ObserverManager:
    """观察者管理器
    
    管理多个观察者，提供批量通知功能。
    """
    
    def __init__(self) -> None:
        self._observers = []
        self._lock = None  # 延迟初始化，避免循环导入
    
    def add_observer(self, observer: CollisionObserver) -> None:
        """添加观察者
        
        Args:
            observer: 观察者实例
        """
        if not isinstance(observer, CollisionObserver):
            raise TypeError("observer必须是CollisionObserver实例")
        
        self._observers.append(observer)
    
    def remove_observer(self, observer: CollisionObserver) -> bool:
        """移除观察者
        
        Args:
            observer: 观察者实例
        
        Returns:
            bool: 移除成功返回True
        """
        try:
            self._observers.remove(observer)
            return True
        except ValueError:
            return False
    
    def notify_progress(self, stats: CollisionStats) -> None:
        """通知所有观察者进度更新
        
        Args:
            stats: 碰撞统计信息
        """
        for observer in self._observers:
            try:
                observer.on_progress(stats)
            except Exception as e:
                # 观察者异常不应影响主流程
                import logging
                logging.getLogger(__name__).error(
                    f"观察者on_progress回调失败: {e}"
                )
    
    def notify_match(self, private_key: bytes, address: str, wif: str) -> None:
        """通知所有观察者匹配成功
        
        Args:
            private_key: 匹配的私钥
            address: 匹配的地址
            wif: WIF格式私钥
        """
        for observer in self._observers:
            try:
                observer.on_match(private_key, address, wif)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"观察者on_match回调失败: {e}"
                )
    
    def notify_complete(self, stats: CollisionStats) -> None:
        """通知所有观察者碰撞完成
        
        Args:
            stats: 最终统计信息
        """
        for observer in self._observers:
            try:
                observer.on_complete(stats)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"观察者on_complete回调失败: {e}"
                )
    
    def notify_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """通知所有观察者错误事件
        
        Args:
            error: 异常对象
            context: 错误上下文
        """
        for observer in self._observers:
            try:
                observer.on_error(error, context)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"观察者on_error回调失败: {e}"
                )
    
    def clear(self) -> None:
        """清空所有观察者"""
        self._observers.clear()
    
    @property
    def observer_count(self) -> int:
        """获取观察者数量"""
        return len(self._observers)
