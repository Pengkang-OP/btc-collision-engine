"""引擎工厂 — 简化引擎创建并支持依赖注入"""

import logging
from typing import Optional, Set

logger = logging.getLogger(__name__)


class EngineFactory:
    """引擎工厂
    
    提供统一的引擎创建接口，自动处理依赖注入。
    支持通过 DependencyContainer 或直接参数两种注入方式。
    
    用法::
    
        # 方式1: 使用容器
        container = DependencyContainer()
        container.set_stats(my_stats)
        engine = EngineFactory.create_cpu_engine(targets, container=container)
        
        # 方式2: 直接参数
        engine = EngineFactory.create_cpu_engine(targets, stats=my_stats)
        
        # 方式3: 默认值（向后兼容）
        engine = EngineFactory.create_cpu_engine(targets)
    """
    
    @staticmethod
    def create_cpu_engine(
        targets: Set[str],
        container: Optional['DependencyContainer'] = None,
        stats=None,
        event_bus=None,
        data_logger=None,
        **kwargs
    ):
        """创建 CPU 碰撞引擎
        
        Args:
            targets: 目标地址集合
            container: 依赖容器（优先级低于直接参数）
            stats: CollisionStats 实例
            event_bus: EventBus 实例
            data_logger: DataLogger 实例
            **kwargs: 传递给 KeyCollisionEngine 的其他参数
            
        Returns:
            KeyCollisionEngine 实例
        """
        from .key_collision_engine import KeyCollisionEngine
        
        # 直接参数优先于容器
        if container:
            stats = stats or container.stats
            event_bus = event_bus or container.event_bus
            data_logger = data_logger or container.data_logger
        
        return KeyCollisionEngine(
            targets=targets,
            stats=stats,
            event_bus=event_bus,
            data_logger=data_logger,
            **kwargs
        )
    
    @staticmethod
    def create_gpu_engine(
        targets: Set[str],
        container: Optional['DependencyContainer'] = None,
        stats=None,
        event_bus=None,
        data_logger=None,
        **kwargs
    ):
        """创建 GPU 碰撞引擎
        
        Args:
            targets: 目标地址集合
            container: 依赖容器
            stats: CollisionStats 实例
            event_bus: EventBus 实例
            data_logger: DataLogger 实例
            **kwargs: 传递给 GPUCollisionEngine 的其他参数
            
        Returns:
            GPUCollisionEngine 实例
        """
        from .gpu_collision_engine import GPUCollisionEngine
        
        if container:
            stats = stats or container.stats
            event_bus = event_bus or container.event_bus
            data_logger = data_logger or container.data_logger
        
        return GPUCollisionEngine(
            targets=targets,
            stats=stats,
            event_bus=event_bus,
            data_logger=data_logger,
            **kwargs
        )
