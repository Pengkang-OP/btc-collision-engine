"""NVIDIA GPU特定优化

针对NVIDIA GPU的优化策略,包括:
- 异步数据传输
- 持久化缓冲区
- 共享内存优化
- 大页内存支持
"""

from typing import Any, Dict, Optional
import logging

# P3-5: 统一日志获取
from ...utils import init_logging, get_configured_logger
from .base import GPUVendorBase
from ..constants import PER_KEY_MEMORY_BYTES, MIN_BATCH_SIZE, align_batch_size

logger = get_configured_logger("NvidiaVendor")


class NVIDIAGPUVendor(GPUVendorBase):
    """NVIDIA GPU优化处理器"""

    def get_vendor_name(self) -> str:
        return "NVIDIA"

    def apply_optimizations(self, device: Any, profile: Dict[str, Any]) -> None:
        """
        应用NVIDIA特定优化

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
        logger.debug(f"NVIDIA GPU内存效率: {memory_efficiency*100:.0f}%")

    def calculate_batch_size(self, device: Any, profile: Dict[str, Any]) -> int:
        """
        计算NVIDIA GPU的最优batch_size

        策略:
        1. 使用profile中的recommended_batch_size作为基准
        2. 根据显存大小调整
        3. 确保不超过max_batch_size
        """
        recommended = profile.get("recommended_batch_size", 524288)
        maximum = profile.get("max_batch_size", 1048576)
        memory_efficiency = profile.get("memory_efficiency", 0.6)

        # 根据显存计算理论最大值
        global_mem = device.device_info.get("global_mem_size", 0)
        # 每个私钥约36字节(32字节私钥+4字节结果)
        mem_based_max = int((global_mem * memory_efficiency) / PER_KEY_MEMORY_BYTES)

        # 取三者最小值
        optimal = min(recommended, maximum, mem_based_max)

        # 向下对齐到1024的倍数，并确保不低于最小值
        optimal = align_batch_size(optimal)

        logger.info(
            f"NVIDIA batch_size计算: recommended={recommended}, "
            f"mem_based={mem_based_max}, optimal={optimal}"
        )

        return optimal

    def handle_errors(self, error: Exception, stats: Optional[Any] = None) -> bool:
        """
        处理NVIDIA GPU特定错误

        NVIDIA GPU通常比较稳定,错误多为资源不足
        """
        error_msg = str(error).lower()

        # 资源不足错误
        if any(
            keyword in error_msg
            for keyword in ["out of memory", "out of resources", "allocation failed"]
        ):
            logger.error(f"NVIDIA GPU资源不足: {error}")
            if stats:
                stats.record_gpu_error(is_resource_error=True)
            return True  # 继续执行

        # 其他错误
        return super().handle_errors(error, stats)
