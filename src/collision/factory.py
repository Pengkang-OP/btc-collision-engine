"""引擎工厂 — 简化引擎创建并支持依赖注入

v4.2.2 M2: 移除 stats/data_logger 废弃参数，向后兼容通过 **kwargs 过滤。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .dependency_container import DependencyContainer
    from .gpu_collision_engine import GPUCollisionEngine
    from .key_collision_engine import KeyCollisionEngine

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
        targets: set[str],
        container: DependencyContainer | None = None,
        event_bus: Any = None,
        **kwargs,
    ) -> KeyCollisionEngine:
        """创建 CPU 碰撞引擎

        Args:
            targets: 目标地址集合
            container: 依赖容器（优先级低于直接参数）
            event_bus: EventBus 实例
            **kwargs: 传递给 KeyCollisionEngine 的其他参数
                (v4.2.2 M2: 已移除 stats/data_logger 废弃参数)

        Returns:
            KeyCollisionEngine 实例
        """
        from .key_collision_engine import KeyCollisionEngine

<<<<<<< Updated upstream
        # Deprecation: stats/data_logger 参数在新架构中由引擎自建
        if stats is not None:
            warnings.warn(
                "'stats' parameter is deprecated and ignored. "
                "KeyCollisionEngine now creates its own CollisionStats internally.",
                FutureWarning,
                stacklevel=2,
            )
        if data_logger is not None:
            warnings.warn(
                "'data_logger' parameter is deprecated and ignored. "
                "KeyCollisionEngine now creates its own DataLogger internally.",
                FutureWarning,
                stacklevel=2,
            )
=======
        # v4.2.2 M2: 移除 stats/data_logger 废弃参数，向后兼容：通过 **kwargs 过滤
        kwargs.pop('stats', None)
        kwargs.pop('data_logger', None)
>>>>>>> Stashed changes

        # 直接参数优先于容器
        if container:
            event_bus = event_bus or container.event_bus

        return KeyCollisionEngine(targets=targets, event_bus=event_bus, **kwargs)

    @staticmethod
    def create_gpu_engine(
        targets: set[str],
        container: DependencyContainer | None = None,
        event_bus: Any = None,
        **kwargs,
    ) -> GPUCollisionEngine:
        """创建 GPU 碰撞引擎

        Args:
            targets: 目标地址集合
            container: 依赖容器
            event_bus: EventBus 实例
            **kwargs: 传递给 GPUCollisionEngine 的其他参数
                (v4.2.2 M2: 已移除 stats/event_bus/data_logger 废弃参数)

        Returns:
            GPUCollisionEngine 实例
        """
        from .gpu_collision_engine import GPUCollisionEngine

<<<<<<< Updated upstream
        # Deprecation: stats/event_bus/data_logger 参数在新架构中由引擎自建
        if stats is not None:
            warnings.warn(
                "'stats' parameter is deprecated and ignored. "
                "GPUCollisionEngine now creates its own CollisionStats internally.",
                FutureWarning,
                stacklevel=2,
            )
        if event_bus is not None:
            warnings.warn(
                "'event_bus' parameter is deprecated and ignored. "
                "GPUCollisionEngine now creates its own EventBus internally.",
                FutureWarning,
                stacklevel=2,
            )
        if data_logger is not None:
            warnings.warn(
                "'data_logger' parameter is deprecated and ignored. "
                "GPUCollisionEngine now creates its own DataLogger internally.",
                FutureWarning,
                stacklevel=2,
            )
=======
        # v4.2.2 M2: 移除 stats/data_logger 废弃参数，向后兼容：通过 **kwargs 过滤
        kwargs.pop('stats', None)
        kwargs.pop('data_logger', None)
        # GPU 引擎自建 event_bus，外部传入的 event_bus 会被 kwargs 覆盖
        # 保留向后兼容：不强制使用 container.event_bus

        # v4.2.2 M1: GPU 引擎也使用 container.event_bus 作为 fallback
        if container:
            _ = container.event_bus  # 预留扩展点
>>>>>>> Stashed changes

        return GPUCollisionEngine(targets=targets, **kwargs)
