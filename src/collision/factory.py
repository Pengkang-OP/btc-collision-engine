"""引擎工厂 — 简化引擎创建并支持依赖注入

v4.5.1: 方法体统一委托给 `create_collision_engine()` 避免工厂逻辑重复。
        保留 `EngineFactory` 类作为向后兼容的便捷入口。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .dependency_container import DependencyContainer

logger = logging.getLogger(__name__)


class EngineFactory:
    """引擎工厂

    提供统一的引擎创建接口，自动处理依赖注入。
    支持通过 DependencyContainer 或直接参数两种注入方式。

    v4.5.1: 方法委托给 `collision.create_collision_engine()`。

    用法::

        # 方式1: 使用容器
        container = DependencyContainer()
        container.set_stats(my_stats)
        engine = EngineFactory.create_cpu_engine(targets, container=container)

        # 方式2: 直接参数
        engine = EngineFactory.create_cpu_engine(targets, event_bus=my_bus)

        # 方式3: 默认值（向后兼容）
        engine = EngineFactory.create_cpu_engine(targets)
    """

    @staticmethod
    def create_cpu_engine(
        targets: set[str],
        container: DependencyContainer | None = None,
        event_bus: Any = None,
        **kwargs,
    ) -> Any:
        """创建 CPU 碰撞引擎（委托给 create_collision_engine）

        Args:
            targets: 目标地址集合
            container: 依赖容器（优先级低于直接参数）
            event_bus: EventBus 实例
            **kwargs: 传递给 KeyCollisionEngine 的其他参数
        """
        from . import create_collision_engine

        kwargs.pop("stats", None)
        kwargs.pop("data_logger", None)
        if event_bus is not None:
            kwargs.setdefault("event_bus", event_bus)

        return create_collision_engine(
            targets=targets, mode="cpu", container=container, **kwargs
        )

    @staticmethod
    def create_gpu_engine(
        targets: set[str],
        container: DependencyContainer | None = None,
        event_bus: Any = None,
        **kwargs,
    ) -> Any:
        """创建 GPU 碰撞引擎（委托给 create_collision_engine）

        Args:
            targets: 目标地址集合
            container: 依赖容器
            event_bus: EventBus 实例（保留参数，GPU 引擎自建 event_bus）
            **kwargs: 传递给 GPUCollisionEngine 的其他参数
        """
        from . import create_collision_engine

        kwargs.pop("stats", None)
        kwargs.pop("data_logger", None)

        return create_collision_engine(
            targets=targets, mode="gpu", container=container, **kwargs
        )
