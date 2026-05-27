"""GPU碰撞引擎重构模块.

本模块包含从GPUCollisionEngine解耦出来的核心组件:
- GPUEngineFacade: GPU引擎外观层，封装设备/内核/管道管理
- DeviceManagerAdapter: GPU设备管理器适配器
- GPUKernelAdapter: GPU内核执行器适配器
- AsyncPipelineAdapter: 异步执行管道适配器
- PerformanceMonitoringPipeline: 性能监控管道
- CollisionCore: 碰撞核心逻辑
- VendorOptimizationFactory: 厂商优化策略工厂

重构目标:
- 降低代码复杂度73% (1466行 -> <400行)
- 减少导入模块70% (49个 -> <15个)
- 提高可测试性 (Mock层从7+降到1-2)
- 保持向后兼容 (API不变)

版本: v4.2.2 Phase 6.1
创建日期: 2026-04-29
更新日期: 2026-05-23
"""

from src import __version__ as __version__  # noqa: F401

__author__ = "BTC Project"

# v4.2.2 S1: __init__.py 提供清晰的导入映射

# 直接导入（非延迟），避免循环依赖
from .async_pipeline_adapter import AsyncPipelineAdapter
from .core import CollisionCore

# Phase 3 新增适配器
from .data_logger_adapter import DataLoggerAdapter

# Phase 2 新增适配器
from .device_manager_adapter import DeviceManagerAdapter
from .engine import GPUCollisionEngine, GPUEngineConfig
from .facade import GPUEngineFacade
from .kernel_adapter import GPUKernelAdapter
from .monitoring import PerformanceMonitoringPipeline
from .vendor_strategy import VendorOptimizationFactory


# 工厂函数（向后兼容：支持延迟导入/依赖注入场景）
def get_gpu_engine_facade():
    """返回 GPUEngineFacade 类（非实例）."""
    return GPUEngineFacade


def get_monitoring_pipeline():
    """返回 PerformanceMonitoringPipeline 类（非实例）."""
    return PerformanceMonitoringPipeline


def get_collision_core():
    """返回 CollisionCore 类（非实例）."""
    return CollisionCore


def get_vendor_factory():
    """返回 VendorOptimizationFactory 类（非实例）."""
    return VendorOptimizationFactory


def get_device_manager_adapter():
    """返回 DeviceManagerAdapter 类（非实例）."""
    return DeviceManagerAdapter


def get_kernel_adapter():
    """返回 GPUKernelAdapter 类（非实例）."""
    return GPUKernelAdapter


def get_async_pipeline_adapter():
    """返回 AsyncPipelineAdapter 类（非实例）."""
    return AsyncPipelineAdapter


def get_data_logger_adapter():
    """返回 DataLoggerAdapter 类（非实例）."""
    return DataLoggerAdapter


__all__ = [
    "AsyncPipelineAdapter",
    "CollisionCore",
    "DataLoggerAdapter",
    "DeviceManagerAdapter",
    "GPUCollisionEngine",
    "GPUEngineConfig",
    "GPUEngineFacade",
    "GPUKernelAdapter",
    "PerformanceMonitoringPipeline",
    "VendorOptimizationFactory",
    "get_async_pipeline_adapter",
    "get_collision_core",
    "get_data_logger_adapter",
    "get_device_manager_adapter",
    "get_gpu_engine_facade",
    "get_kernel_adapter",
    "get_monitoring_pipeline",
    "get_vendor_factory",
]
