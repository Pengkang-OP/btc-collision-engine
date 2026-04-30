"""依赖注入容器 — 集中管理引擎核心依赖的生命周期"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DependencyContainer:
    """引擎依赖注入容器
    
    集中管理 CollisionStats、EventBus、DataLogger 等核心组件，
    支持延迟初始化和可替换注入，便于测试和配置灵活性。
    
    用法::
    
        container = DependencyContainer()
        container.set_stats(mock_stats)  # 测试时注入 Mock
        engine = EngineFactory.create_cpu_engine(targets, container=container)
    """
    
    def __init__(self) -> None:
        self._stats = None
        self._event_bus = None
        self._data_logger = None
        self._initialized = False
    
    @property
    def stats(self) -> Any:
        """获取 CollisionStats（延迟创建）"""
        if self._stats is None:
            from .collision_stats import CollisionStats
            self._stats = CollisionStats()
        return self._stats
    
    @property
    def event_bus(self) -> Any:
        """获取 EventBus（延迟创建）"""
        if self._event_bus is None:
            from .event_bus import EventBus
            self._event_bus = EventBus()
        return self._event_bus
    
    @property
    def data_logger(self) -> Any:
        """获取 DataLogger（延迟创建）"""
        if self._data_logger is None:
            from ..monitoring.data_logger import DataLogger
            self._data_logger = DataLogger()
        return self._data_logger
    
    def set_stats(self, stats: Any) -> 'DependencyContainer':
        """注入自定义 CollisionStats"""
        self._stats = stats
        return self
    
    def set_event_bus(self, event_bus: Any) -> 'DependencyContainer':
        """注入自定义 EventBus"""
        self._event_bus = event_bus
        return self
    
    def set_data_logger(self, data_logger: Any) -> 'DependencyContainer':
        """注入自定义 DataLogger"""
        self._data_logger = data_logger
        return self
    
    def reset(self) -> None:
        """重置所有依赖（测试用）"""
        self._stats = None
        self._event_bus = None
        self._data_logger = None
    
    def __repr__(self) -> str:
        return (
            f"DependencyContainer("
            f"stats={'set' if self._stats else 'lazy'}, "
            f"event_bus={'set' if self._event_bus else 'lazy'}, "
            f"data_logger={'set' if self._data_logger else 'lazy'})"
        )
