"""监控系统事件适配器

将碰撞引擎事件转换为监控系统调用，实现解耦。

使用示例:
    >>> from src.collision.event_bus import EventBus
    >>> from src.monitoring.event_adapters import DataLoggerAdapter
    >>> 
    >>> # 创建事件总线和适配器
    >>> bus = EventBus()
    >>> adapter = DataLoggerAdapter()
    >>> 
    >>> # 订阅事件
    >>> adapter.subscribe_to(bus)
    >>> 
    >>> # 现在引擎发布的事件会自动记录到日志
"""
import logging
from typing import Optional

from src.collision.events import (
    CollisionEvent,
    EngineProgressEvent,
    EngineMatchEvent,
    EngineErrorEvent,
    EngineCompleteEvent,
    EventType
)
from src.collision.event_bus import EventBus
from src.monitoring.data_logger import DataLogger

logger = logging.getLogger(__name__)


class DataLoggerAdapter:
    """
    DataLogger事件适配器
    
    订阅引擎事件并自动记录到数据日志系统。
    
    这个适配器将事件总线与DataLogger解耦，
    使得引擎不需要直接依赖DataLogger。
    
    Example:
        >>> # 方式1: 手动订阅
        >>> bus = EventBus()
        >>> adapter = DataLoggerAdapter()
        >>> adapter.subscribe_to(bus)
        >>> 
        >>> # 方式2: 使用便捷函数
        >>> bus = EventBus()
        >>> adapter = setup_data_logging(bus)
    """
    
    def __init__(self, data_logger: Optional[DataLogger] = None):
        """
        初始化适配器
        
        Args:
            data_logger: DataLogger实例 (如果为None则自动创建)
        """
        self.data_logger = data_logger or DataLogger()
        self._subscribed = False
        self._event_bus: Optional[EventBus] = None
        
        logger.debug("DataLoggerAdapter已初始化")
    
    def subscribe_to(self, event_bus: EventBus) -> None:
        """
        订阅事件总线的所有相关事件
        
        Args:
            event_bus: 事件总线实例
        """
        if self._subscribed:
            logger.warning("适配器已订阅事件总线")
            return
        
        event_bus.subscribe(EventType.ENGINE_PROGRESS, self.handle_progress)
        event_bus.subscribe(EventType.ENGINE_MATCH, self.handle_match)
        event_bus.subscribe(EventType.ENGINE_ERROR, self.handle_error)
        event_bus.subscribe(EventType.ENGINE_COMPLETE, self.handle_complete)
        event_bus.subscribe(EventType.ENGINE_START, self.handle_start)
        event_bus.subscribe(EventType.ENGINE_STOP, self.handle_stop)
        
        self._subscribed = True
        self._event_bus = event_bus
        
        logger.info("DataLoggerAdapter已订阅事件总线")
    
    def unsubscribe(self) -> None:
        """取消订阅所有事件"""
        if not self._subscribed or not self._event_bus:
            return
        
        self._event_bus.unsubscribe(EventType.ENGINE_PROGRESS, self.handle_progress)
        self._event_bus.unsubscribe(EventType.ENGINE_MATCH, self.handle_match)
        self._event_bus.unsubscribe(EventType.ENGINE_ERROR, self.handle_error)
        self._event_bus.unsubscribe(EventType.ENGINE_COMPLETE, self.handle_complete)
        self._event_bus.unsubscribe(EventType.ENGINE_START, self.handle_start)
        self._event_bus.unsubscribe(EventType.ENGINE_STOP, self.handle_stop)
        
        self._subscribed = False
        
        logger.info("DataLoggerAdapter已取消订阅")
    
    def handle_start(self, event: CollisionEvent) -> None:
        """处理引擎启动事件"""
        logger.info(f"引擎启动: {event.metadata}")
    
    def handle_progress(self, event: EngineProgressEvent) -> None:
        """
        处理进度事件
        
        记录性能数据到日志系统。
        """
        if self.data_logger:
            try:
                self.data_logger.record_performance_data(
                    speed=event.speed,
                    total_checked=event.total_checked,
                    matches_found=event.matches_found,
                    cpu_usage=event.cpu_usage,
                    memory_usage=event.memory_usage,
                    thread_count=event.thread_count
                )
            except Exception as e:
                logger.error(f"记录性能数据失败: {e}")
    
    def handle_match(self, event: EngineMatchEvent) -> None:
        """
        处理匹配事件
        
        记录匹配结果到日志系统。
        
        ⚠️ 安全注意:
            不会记录私钥到日志文件，仅记录地址信息。
        """
        if self.data_logger:
            try:
                # 只记录地址，不记录私钥 (安全考虑)
                logger.info(
                    f"发现匹配! 地址: {event.address}, "
                    f"目标: {event.target_address}"
                )
                
                # 可以在这里保存匹配结果到文件
                # self.data_logger.save_match_result(event.address, event.wif)
                
            except Exception as e:
                logger.error(f"记录匹配事件失败: {e}")
    
    def handle_error(self, event: EngineErrorEvent) -> None:
        """
        处理错误事件
        
        记录错误信息到日志系统。
        """
        if self.data_logger:
            try:
                self.data_logger.record_error(
                    error_type=event.error_type,
                    message=event.error_message,
                    exception=event.exception,
                    context=event.context
                )
            except Exception as e:
                logger.error(f"记录错误事件失败: {e}")
    
    def handle_complete(self, event: EngineCompleteEvent) -> None:
        """
        处理完成事件
        
        保存最终数据并生成报告。
        """
        if self.data_logger:
            try:
                # 保存当前数据
                self.data_logger.save_current_data()
                
                logger.info(
                    f"引擎完成: 检测={event.total_checked}, "
                    f"匹配={event.matches_found}, "
                    f"平均速度={event.avg_speed:.2f} keys/s"
                )
            except Exception as e:
                logger.error(f"处理完成事件失败: {e}")
    
    def handle_stop(self, event: CollisionEvent) -> None:
        """处理引擎停止事件"""
        logger.info(f"引擎停止: {event.metadata}")
    
    @property
    def is_subscribed(self) -> bool:
        """是否已订阅事件总线"""
        return self._subscribed


class EnhancedMonitoringAdapter:
    """
    EnhancedMonitoringSystem事件适配器
    
    订阅引擎事件并触发增强监控系统的相应操作。
    
    Note:
        EnhancedMonitoringSystem通常运行在独立线程中，
        自行采集数据。此适配器主要用于错误传递。
    """
    
    def __init__(self, monitoring_system):
        """
        初始化适配器
        
        Args:
            monitoring_system: EnhancedMonitoringSystem实例
        """
        self.monitoring_system = monitoring_system
        self._subscribed = False
        self._event_bus: Optional[EventBus] = None
        
        logger.debug("EnhancedMonitoringAdapter已初始化")
    
    def subscribe_to(self, event_bus: EventBus) -> None:
        """订阅事件总线"""
        if self._subscribed:
            return
        
        # 主要订阅错误事件
        event_bus.subscribe(EventType.ENGINE_ERROR, self.handle_error)
        
        self._subscribed = True
        self._event_bus = event_bus
        
        logger.info("EnhancedMonitoringAdapter已订阅事件总线")
    
    def unsubscribe(self) -> None:
        """取消订阅"""
        if not self._subscribed or not self._event_bus:
            return
        
        self._event_bus.unsubscribe(EventType.ENGINE_ERROR, self.handle_error)
        self._subscribed = False
    
    def handle_error(self, event: EngineErrorEvent) -> None:
        """处理错误事件"""
        if self.monitoring_system:
            try:
                self.monitoring_system.handle_error(
                    error=event.exception or Exception(event.error_message),
                    context=event.context
                )
            except Exception as e:
                logger.error(f"增强监控错误处理失败: {e}")


# ============================================================================
# 便捷函数
# ============================================================================

def setup_data_logging(
    event_bus: EventBus,
    data_logger: Optional[DataLogger] = None
) -> DataLoggerAdapter:
    """
    便捷函数: 设置数据日志事件监听
    
    Args:
        event_bus: 事件总线
        data_logger: DataLogger实例 (可选)
    
    Returns:
        DataLoggerAdapter实例
    
    Example:
        >>> bus = get_event_bus()
        >>> adapter = setup_data_logging(bus)
    """
    adapter = DataLoggerAdapter(data_logger)
    adapter.subscribe_to(event_bus)
    return adapter


def setup_enhanced_monitoring(
    event_bus: EventBus,
    monitoring_system
) -> EnhancedMonitoringAdapter:
    """
    便捷函数: 设置增强监控事件监听
    
    Args:
        event_bus: 事件总线
        monitoring_system: EnhancedMonitoringSystem实例
    
    Returns:
        EnhancedMonitoringAdapter实例
    """
    adapter = EnhancedMonitoringAdapter(monitoring_system)
    adapter.subscribe_to(event_bus)
    return adapter
