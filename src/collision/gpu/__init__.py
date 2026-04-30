"""GPU碰撞引擎重构模块

本模块包含从GPUCollisionEngine解耦出来的核心组件:
- GPUEngineFacade: GPU外观层，封装设备/上下文/内核管理
- PerformanceMonitoringPipeline: 性能监控管道
- CollisionCore: 碰撞核心逻辑
- VendorOptimizationFactory: 厂商优化策略工厂

重构目标:
- 降低代码复杂度73% (1466行 -> <400行)
- 减少导入模块70% (49个 -> <15个)
- 提高可测试性 (Mock层从7+降到1-2)
- 保持向后兼容 (API不变)

版本: v1.0
创建日期: 2026-04-29
"""

__version__ = "1.0.0"
__author__ = "BTC Project"

# 直接导入（非延迟），避免循环依赖
from .facade import GPUEngineFacade
from .monitoring import PerformanceMonitoringPipeline
from .core import CollisionCore
from .vendor_strategy import VendorOptimizationFactory


# 工厂函数（向后兼容：支持延迟导入/依赖注入场景）
def get_gpu_engine_facade():
    """返回 GPUEngineFacade 类（非实例）"""
    return GPUEngineFacade


def get_monitoring_pipeline():
    """返回 PerformanceMonitoringPipeline 类（非实例）"""
    return PerformanceMonitoringPipeline


def get_collision_core():
    """返回 CollisionCore 类（非实例）"""
    return CollisionCore


def get_vendor_factory():
    """返回 VendorOptimizationFactory 类（非实例）"""
    return VendorOptimizationFactory


__all__ = [
    "GPUEngineFacade",
    "PerformanceMonitoringPipeline",
    "CollisionCore",
    "VendorOptimizationFactory",
    "get_gpu_engine_facade",
    "get_monitoring_pipeline",
    "get_collision_core",
    "get_vendor_factory",
]
