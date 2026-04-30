"""GPU碰撞引擎 - 向后兼容重导出模块 (Shim)

原 GPUCollisionEngine 类已迁移至 src.collision.gpu.engine。
此文件作为薄 shim 保持向后兼容，所有现有导入和 Monkey-patch 继续工作。

版本: v6.0.0 (Phase 6)
"""

import os
import time
import signal
import threading
import logging
from typing import Set, Optional, Tuple, List, Dict, Any, Callable

# ========== 从新位置导入核心类 ==========
from .gpu.engine import GPUCollisionEngine

# ========== 重导出常量 ==========
from .gpu.engine import (
    UINT32_MAX,
    GPU_MAX_BATCH_SIZE,
    INITIAL_BATCH_SIZE,
    ASYNC_KEY_GEN_TIMEOUT,
    BATCH_LOG_FREQUENCY,
    INITIAL_BATCHES_LOG,
    THREAD_JOIN_TIMEOUT,
    MONITOR_THREAD_JOIN_TIMEOUT,
    EXCEPTION_RECOVERY_DELAY,
    ASYNC_KEY_GEN_BASE_TIMEOUT,
    ASYNC_KEY_GEN_PER_KEY_TIME,
    ASYNC_KEY_GEN_SAFETY_FACTOR,
    PYOPENCL_AVAILABLE,
    ASYNC_LOG_AVAILABLE,
    GPU_CONFIG_MANAGER_AVAILABLE,
)

# ========== 重导出工具函数 ==========
from .gpu.engine import _seed_bytes_to_u32_be_array, _get_gpu_monitor

# ========== 向后兼容: 保留原模块级导入 ==========
# 以下导入保证 Monkey-patch (如 patch('src.collision.gpu_collision_engine.GPUDevice')) 继续工作

# 回调类型
from .types import ProgressCallback, MatchCallback, CompleteCallback

# GPU设备与上下文
from ..gpu.device import GPUDevice, GPUDeviceDetector
from ..gpu.context import GPUContext
from ..gpu.device_helper import GPUDeviceHelper

# GPU内核与协议
from ..gpu.profiles.loader import GPUProfileLoader
from ..gpu.kernel import OPENCL_KERNEL_SOURCE
from ..gpu.kernel_protocol import GPUKernelProtocol, GPUKernelFactory
from ..gpu.kernel_impl import GPUKernel

# GPU性能优化
from ..gpu.performance_optimizer import get_gpu_optimizer, PerformanceMetrics
from ..gpu.auto_config import get_gpu_configurator, GPUAutoConfigurator
from ..gpu.intel_timeout_manager import AdaptiveTimeoutManager
from ..gpu.intel_memory_monitor import IntelMemoryMonitor
from ..gpu.benchmark_suite import GPUBenchmarkSuite
from ..gpu.auto_tuner import GPUAutoTuner
from ..gpu.performance_reporter import PerformanceReportGenerator, ReportConfig
from ..gpu.async_executor import AsyncGPUExecutor
from ..utils.exception_handler import ExceptionHandler
from ..utils.performance_monitor import EnhancedPerformanceMonitor

# 提取的独立模块
from ..gpu.intel_optimizer import IntelGPUOptimizer
from ..gpu.memory_calculator import GPUMemoryCalculator
from ..gpu.optimization_pipeline import PerformanceOptimizationPipeline
from ..gpu.device_manager import GPUDeviceManager
from ..gpu.config_manager import GPUConfigManager
from ..gpu.search_mode_coordinator import SearchModeCoordinator

# 缓冲区追踪器与搜索模式
from ..gpu.buffer_tracker import GPUBufferTracker
from ..gpu.search_modes import RandomSearchMode, BruteForceSearchMode, RangeScanSearchMode
from ..gpu.engine_monitor import GPUEngineMonitor

# 日志
from ..utils import get_configured_logger

logger = get_configured_logger(__name__)

NEW_GPU_MODULE_AVAILABLE = True

__all__ = [
    "GPUCollisionEngine",
    "GPU_MAX_BATCH_SIZE",
    "UINT32_MAX",
    "INITIAL_BATCH_SIZE",
    "GPUDevice",
    "GPUContext",
    "GPUKernel",
    "GPUDeviceDetector",
    "GPUDeviceManager",
    "GPUConfigManager",
    "GPUEngineMonitor",
    "GPUProfileLoader",
    "SearchModeCoordinator",
    "RandomSearchMode",
    "BruteForceSearchMode",
    "RangeScanSearchMode",
    "AsyncGPUExecutor",
    "PYOPENCL_AVAILABLE",
    "ASYNC_LOG_AVAILABLE",
    "GPU_CONFIG_MANAGER_AVAILABLE",
]
