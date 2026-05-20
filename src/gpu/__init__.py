"""GPU模块 - GPU设备检测、配置管理和厂商优化

提供完整的GPU管理功能:
- GPU设备自动检测(过滤CPU和核显,2015年至今的GPU型号)
- 按厂商分类的GPU处理模块(NVIDIA/AMD/Intel)
- 厂商特定的优化策略
- 驱动版本检测和健康检查
- 基于型号数据库的功能配置
- 基于性能表现的差异化配置调用
"""

from .amd_optimizer import AmdGPUOptimizer  # noqa: E402
from .auto_config import (  # noqa: E402
    GPUAutoConfigurator,
    get_gpu_configurator,
    reset_gpu_configurator,
)  # noqa: E402
from .config import GPUConfig  # noqa: E402

# GPU全局常量模块
from .constants import (  # noqa: E402
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
from .context import GPUContext  # noqa: E402
from .data_monitor import DataMonitor, DataQualityIssue  # noqa: E402
from .device import GPUDevice, GPUDeviceDetector, identify_vendor  # noqa: E402
from .double_buffer import ENV_DOUBLE_BUFFER, DoubleBuffer  # noqa: E402
from .driver_manager import DriverManager, DriverVersionParser  # noqa: E402
from .engine_monitor import GPUEngineMonitor  # noqa: E402
from .gpu_config import (  # noqa: E402
    DataMonitorConfig,
    GPURecoveryConfig,
    MultiGPUConfig,
    WorkerConfig,
)  # noqa: E402

# 提取的独立模块
from .intel_optimizer import IntelGPUOptimizer  # noqa: E402
from .kernel import (  # noqa: E402
    OPENCL_KERNEL_SOURCE,
)
from .load_balancer import GPULoadBalancer  # noqa: E402
from .lock_monitor import (  # noqa: E402
    LockMonitor,
    MonitoredLock,
    create_monitored_lock,
    get_lock_monitor,
)  # noqa: E402
from .memory_calculator import GPUMemoryCalculator  # noqa: E402
from .metrics import GPUMetricsCollector, get_metrics_collector  # noqa: E402
from .multi_format_multi_gpu_engine import (  # noqa: E402
    create_engine,
    create_multi_format_multi_gpu_engine,
)
from .multi_gpu_engine import MultiGPUCollisionEngine  # noqa: E402
from .nvidia_optimizer import NvidiaGPUOptimizer  # noqa: E402
from .optimization_pipeline import PerformanceOptimizationPipeline  # noqa: E402
from .scorer import GPUDeviceScorer, get_gpu_scorer, reset_gpu_scorer  # noqa: E402

# 多GPU支持模块
from .selector import GPUDeviceSelector, get_gpu_selector, reset_gpu_selector  # noqa: E402
from .worker import SingleGPUWorker  # noqa: E402

__version__ = (
    "4.4.0"  # v4.4.0: 安全修复增强(安全清零/侧信道防护/敏感数据脱敏/线程安全), 文档一致性整理
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
