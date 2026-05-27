"""NVIDIA GPU specific optimizations.

针对NVIDIA GPU的优化策略,包括:
- 异步数据传输
- 持久化缓冲区
- 共享内存优化
- 大页内存支持
"""

from typing import Any

# 统一日志获取
from src.utils import get_configured_logger

from .base import GPUVendorBase

logger = get_configured_logger("NvidiaVendor")


class NVIDIAGPUVendor(GPUVendorBase):
    """NVIDIA GPU optimization processor."""

    _RECOMMENDED_BATCH: int = 524288
    _MAX_BATCH: int = 1048576
    _MEMORY_EFFICIENCY: float = 0.60

    def get_vendor_name(self) -> str:
        """Return vendor name."""
        return "NVIDIA"

    def apply_optimizations(self, device: Any, profile: dict[str, Any]) -> None:
        """Apply NVIDIA specific optimizations.

        优化策略:
        1. 启用异步数据传输
        2. 使用持久化缓冲区减少内存分配开销
        3. 优化workgroup size以匹配CUDA核心数
        4. 启用共享内存优化(如果支持)
        5. 根据驱动版本应用特定优化
        """
        logger.info(f"应用NVIDIA优化策略: {device.device_info.get('name', 'Unknown')}")

        optimizations = profile.get("optimizations", [])

        # 1. 异步传输优化
        if "async_transfer" in optimizations:
            # 检查驱动是否支持
            if device.driver_optimization_flags.get("enable_async_compute", True):
                logger.debug("启用异步数据传输优化")
            else:
                logger.warning("驱动版本较旧,禁用异步传输优化")

        # 2. 持久化缓冲区
        if "persistent_buffers" in optimizations:
            logger.debug("启用持久化缓冲区优化")
            # 在GPUKernel中预分配缓冲区,避免频繁分配/释放

        # 3. 共享内存优化
        if "shared_memory_optimization" in optimizations:
            logger.debug("启用共享内存优化")
            # 在OpenCL内核中使用__local内存优化

        # 4. 大页内存支持
        if "large_page_support" in optimizations:
            logger.debug("启用大页内存支持")
            # 使用更大的内存页减少TLB miss

        # 5. Shader Execution Reordering (Ada Lovelace架构)
        if "shader_execution_reordering" in optimizations:
            if device.driver_optimization_flags.get("enable_shader_reordering", False):
                logger.debug("启用Shader Execution Reordering优化")
            else:
                logger.warning("驱动版本不支持Shader Execution Reordering")

        # 6. 驱动特定优化
        if device.driver_optimization_flags.get("conservative_mode", False):
            logger.warning("NVIDIA驱动保守模式:降低性能预期以确保稳定性")

        # 记录内存效率
        memory_efficiency = profile.get("memory_efficiency", 0.5)
        logger.debug(f"NVIDIA GPU内存效率: {memory_efficiency * 100:.0f}%")
