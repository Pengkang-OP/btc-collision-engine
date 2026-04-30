"""GPU模块 - 提供GPU设备检测、厂商优化和配置管理

该模块实现了GPU调用的模块化设计,支持:
- GPU设备自动检测(过滤CPU和核显,2015年至今的GPU型号)
- 按厂商分类的GPU处理模块(NVIDIA/AMD/Intel)
- 基于型号数据库的功能配置
- 基于性能表现的差异化配置调用
"""

"""GPU模块 - GPU设备检测、配置管理和厂商优化

提供完整的GPU管理功能:
- GPU设备自动检测和选择
- 厂商特定的优化策略
- 驱动版本检测和健康检查
- 型号数据库驱动的配置
"""

from .device import GPUDeviceDetector, GPUDevice, identify_vendor
from .config import GPUConfig
from .context import GPUContext
from .driver_manager import DriverManager, DriverVersionParser
from .kernel import (
    OPENCL_KERNEL_SOURCE,
    get_kernel_version,
    validate_kernel_version,
    get_version_changelog,
)
from .gpu_config import MultiGPUConfig, GPURecoveryConfig, DataMonitorConfig, WorkerConfig
from .metrics import GPUMetricsCollector, get_metrics_collector

# 多GPU支持模块
from .selector import GPUDeviceSelector, get_gpu_selector, reset_gpu_selector
from .load_balancer import GPULoadBalancer
from .scorer import GPUDeviceScorer, get_gpu_scorer, reset_gpu_scorer
from .worker import SingleGPUWorker
from .multi_gpu_engine import MultiGPUCollisionEngine
from .auto_config import GPUAutoConfigurator, get_gpu_configurator, reset_gpu_configurator
from .lock_monitor import LockMonitor, MonitoredLock, get_lock_monitor, create_monitored_lock
from .data_monitor import DataMonitor, DataQualityIssue

# 提取的独立模块
from .intel_optimizer import IntelGPUOptimizer
from .nvidia_optimizer import NvidiaGPUOptimizer
from .amd_optimizer import AmdGPUOptimizer
from .memory_calculator import GPUMemoryCalculator
from .optimization_pipeline import PerformanceOptimizationPipeline
from .engine_monitor import GPUEngineMonitor

# GPU全局常量模块
from .constants import (
    PER_KEY_MEMORY_BYTES,
    BYTES_PER_MB,
    BATCH_SIZE_ALIGNMENT,
    MIN_BATCH_SIZE,
    MAX_BATCH_SIZE,
    DEFAULT_BATCH_SIZE,
    MEMORY_EFFICIENCY_MIN,
    MEMORY_EFFICIENCY_MAX,
    DEFAULT_MEMORY_EFFICIENCY,
    align_batch_size,
    clamp_batch_size,
)

__version__ = (
    "3.5.1"  # 与主项目版本同步 (v3.5.1: 数据日志系统修复 + 导入路径优化 + pre-commit/贡献指南)
)

__all__ = [
    "GPUDeviceDetector",
    "GPUDevice",
    "GPUConfig",
    "GPUContext",
    "identify_vendor",
    "DriverManager",
    "DriverVersionParser",
    "OPENCL_KERNEL_SOURCE",
    # GPU配置数据结构
    "MultiGPUConfig",
    "GPURecoveryConfig",
    "DataMonitorConfig",
    "WorkerConfig",
    # GPU可观测性
    "GPUMetricsCollector",
    "get_metrics_collector",
    # 多GPU支持
    "GPUDeviceSelector",
    "get_gpu_selector",
    "reset_gpu_selector",
    "GPULoadBalancer",
    # P3-11: 统一GPU评分
    "GPUDeviceScorer",
    "get_gpu_scorer",
    "reset_gpu_scorer",
    "SingleGPUWorker",
    "MultiGPUCollisionEngine",
    "GPUAutoConfigurator",
    "get_gpu_configurator",
    "reset_gpu_configurator",
    # 锁监控
    "LockMonitor",
    "MonitoredLock",
    "get_lock_monitor",
    "create_monitored_lock",
    # 数据监控
    "DataMonitor",
    "DataQualityIssue",
    # 提取的独立模块
    "IntelGPUOptimizer",
    "NvidiaGPUOptimizer",
    "AmdGPUOptimizer",
    "GPUMemoryCalculator",
    "PerformanceOptimizationPipeline",
    # Task#3: 引擎监控模块
    "GPUEngineMonitor",
    # Task#7: GPU全局常量模块
    "PER_KEY_MEMORY_BYTES",
    "BYTES_PER_MB",
    "BATCH_SIZE_ALIGNMENT",
    "MIN_BATCH_SIZE",
    "MAX_BATCH_SIZE",
    "DEFAULT_BATCH_SIZE",
    "MEMORY_EFFICIENCY_MIN",
    "MEMORY_EFFICIENCY_MAX",
    "DEFAULT_MEMORY_EFFICIENCY",
    "align_batch_size",
    "clamp_batch_size",
]
