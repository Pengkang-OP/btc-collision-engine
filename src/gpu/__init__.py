"""GPU模块 - GPU设备检测、配置管理和厂商优化.

提供完整的GPU管理功能:
- GPU设备自动检测和选择
- 厂商特定的优化策略 (NVIDIA/AMD/Intel)
- 驱动版本检测和健康检查
- 型号数据库驱动的配置
- 多GPU负载均衡与评分
- GPU内存计算与锁监控
- 种子端序转换工具 (seed_utils)

v4.2.2 S1: 统一模块说明，移除重复 docstring。
"""

from .amd_optimizer import AmdGPUOptimizer
from .auto_config import (
    GPUAutoConfigurator,
    get_gpu_configurator,
    reset_gpu_configurator,
)
from .config import GPUConfig

# GPU全局常量模块
from .constants import (
    BATCH_SIZE_ALIGNMENT,
    BYTES_PER_MB,
    DEFAULT_BATCH_SIZE,
    DEFAULT_MEMORY_EFFICIENCY,
    MAX_BATCH_SIZE,
    MEMORY_EFFICIENCY_MAX,
    MEMORY_EFFICIENCY_MIN,
    MIN_BATCH_SIZE,
    PER_KEY_MEMORY_BYTES,
    align_batch_size,
    clamp_batch_size,
)
from .context import GPUContext
from .data_monitor import DataMonitor, DataQualityIssue
from .device import GPUDevice, GPUDeviceDetector, identify_vendor
from .double_buffer import ENV_DOUBLE_BUFFER, DoubleBuffer
from .driver_manager import DriverManager, DriverVersionParser
from .engine_monitor import GPUEngineMonitor
from .gpu_config import (
    DataMonitorConfig,
    GPURecoveryConfig,
    MultiGPUConfig,
    WorkerConfig,
)

# 提取的独立模块
from .intel_optimizer import IntelGPUOptimizer
from .kernel import (
    OPENCL_KERNEL_SOURCE,
)
from .load_balancer import GPULoadBalancer
from .lock_monitor import (
    LockMonitor,
    MonitoredLock,
    create_monitored_lock,
    get_lock_monitor,
)
from .memory_calculator import GPUMemoryCalculator
from .metrics import GPUMetricsCollector, get_metrics_collector
from .multi_format_multi_gpu_engine import (
    MultiFormatMultiGPUEngine,
    create_engine,
    create_multi_format_multi_gpu_engine,
)
from .multi_gpu_engine import MultiGPUCollisionEngine
from .nvidia_optimizer import NvidiaGPUOptimizer
from .optimization_pipeline import PerformanceOptimizationPipeline
from .scorer import GPUDeviceScorer, get_gpu_scorer, reset_gpu_scorer

# 多GPU支持模块
from .selector import GPUDeviceSelector, get_gpu_selector, reset_gpu_selector
from .worker import SingleGPUWorker

from src import __version__ as __version__  # noqa: F401 — 从包根统一读取

__all__ = [
    "GPUDeviceDetector",
    "GPUDevice",
    "GPUConfig",
    "GPUContext",
    "identify_vendor",
    "DriverManager",
    "DriverVersionParser",
    "OPENCL_KERNEL_SOURCE",
    "MultiFormatMultiGPUEngine",
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
    # 统一GPU评分
    "GPUDeviceScorer",
    "get_gpu_scorer",
    "reset_gpu_scorer",
    "SingleGPUWorker",
    "MultiGPUCollisionEngine",
    # v4.3.0 新增: 多格式多GPU支持
    "create_engine",
    "create_multi_format_multi_gpu_engine",
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
    # Task#10: CPU-GPU 双缓冲优化 (PERF-1)
    "DoubleBuffer",
    "ENV_DOUBLE_BUFFER",
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
