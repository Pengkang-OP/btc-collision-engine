"""GPU碰撞引擎 - 向后兼容重导出模块 (Shim)

原 GPUCollisionEngine 类已迁移至 src.collision.gpu.engine。
此文件作为薄 shim 保持向后兼容，所有现有导入和 Monkey-patch 继续工作。

版本: v4.2.1 (Phase 6)
"""

# ========== 从新位置导入核心类 ==========
# GPU性能优化
from ..gpu.async_executor import AsyncGPUExecutor
from ..gpu.config_manager import GPUConfigManager
from ..gpu.context import GPUContext

# ========== 重导出工具函数 ==========
# ========== 向后兼容: 保留原模块级导入 ==========
# 以下导入保证 Monkey-patch (如 patch('src.collision.gpu_collision_engine.GPUDevice')) 继续工作
# 回调类型
# GPU设备与上下文
from ..gpu.device import GPUDevice, GPUDeviceDetector

# 提取的独立模块
from ..gpu.device_manager import GPUDeviceManager
from ..gpu.engine_monitor import GPUEngineMonitor
from ..gpu.kernel_impl import GPUKernel

# GPU内核与协议
from ..gpu.profiles.loader import GPUProfileLoader
from ..gpu.search_mode_coordinator import SearchModeCoordinator

# 缓冲区追踪器与搜索模式
from ..gpu.search_modes import BruteForceSearchMode, RandomSearchMode, RangeScanSearchMode

# 日志
from ..utils import get_configured_logger

# ========== 重导出常量 ==========
from .gpu.engine import (
    ASYNC_LOG_AVAILABLE,
    GPU_CONFIG_MANAGER_AVAILABLE,
    GPU_MAX_BATCH_SIZE,
    INITIAL_BATCH_SIZE,
    PYOPENCL_AVAILABLE,
    UINT32_MAX,
    GPUCollisionEngine,
)

logger = get_configured_logger(__name__)

# v4.5.1: Shim 层弃用警告
# 计划 v5.0.0 移除: 使用 'from src.collision.gpu.engine import GPUCollisionEngine' 替代
logger.warning(
    "gpu_collision_engine.py (Shim) 已弃用，建议直接导入 src.collision.gpu.engine。"
    "此 shim 将在 v5.0.0 移除。"
)

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
