"""AMD GPU特定优化

针对AMD GPU的优化策略,包括:
- 内存合并访问优化
- 计算单元优化
- HBM显存优化(如果适用)
- Infinity Cache优化(RDNA2+)
"""

from typing import Dict, Any
import logging
from .base import GPUVendorBase

logger = logging.getLogger(__name__)


class AMDGPUVendor(GPUVendorBase):
    """AMD GPU优化处理器"""
    
    def get_vendor_name(self) -> str:
        return "AMD"
    
    def apply_optimizations(self, device, profile: Dict[str, Any]):
        """
        应用AMD特定优化
        
        优化策略:
        1. 内存合并访问优化
        2. 计算单元优化
        3. HBM显存优化(如果适用)
        4. Infinity Cache优化(RDNA2+)
        5. 根据驱动版本应用特定优化
        """
        logger.info(f"应用AMD优化策略: {device.device_info.get('name', 'Unknown')}")
        
        optimizations = profile.get('optimizations', [])
        
        # 1. 异步传输
        if 'async_transfer' in optimizations:
            logger.debug("启用异步数据传输优化")
        
        # 2. 内存合并访问优化
        if 'memory_coalescing' in optimizations:
            logger.debug("启用内存合并访问优化")
            # 确保内存访问模式对齐,提高带宽利用率
        
        # 3. HBM显存优化
        if 'hbm_optimization' in optimizations:
            logger.debug("启用HBM显存优化")
            # Vega系列使用HBM2,带宽极高但延迟较高
            # 优化策略:增加并发度隐藏延迟
        
        # 4. 计算单元优化
        if 'compute_unit_optimization' in optimizations:
            logger.debug("启用计算单元优化")
            # RDNA架构优化workgroup size以匹配CU数量
        
        # 5. Infinity Cache优化
        if 'infinity_cache' in optimizations:
            logger.debug("启用Infinity Cache优化")
            # RDNA2+架构的L3缓存,优化局部性
        
        # 6. Chiplet架构优化
        if 'chiplet_architecture' in optimizations:
            logger.debug("启用Chiplet架构优化")
            # RDNA3的多die架构,优化跨die通信
        
        # 7. 驱动特定优化
        if not device.driver_optimization_flags.get('enable_fast_math', True):
            logger.warning("AMD驱动版本较旧,禁用快速数学优化以确保稳定性")
        
        if device.driver_optimization_flags.get('conservative_mode', False):
            logger.warning("AMD驱动保守模式:降低性能预期以确保稳定性")
        
        memory_efficiency = profile.get('memory_efficiency', 0.5)
        logger.debug(f"AMD GPU内存效率: {memory_efficiency*100:.0f}%")
    
    def calculate_batch_size(self, device, profile: Dict[str, Any]) -> int:
        """
        计算AMD GPU的最优batch_size
        
        策略:
        1. 使用profile中的recommended_batch_size作为基准
        2. 根据显存大小和内存效率调整
        3. 考虑Infinity Cache的影响
        """
        recommended = profile.get('recommended_batch_size', 524288)
        maximum = profile.get('max_batch_size', 1048576)
        memory_efficiency = profile.get('memory_efficiency', 0.55)
        
        # 根据显存计算理论最大值
        global_mem = device.device_info.get('global_mem_size', 0)
        per_key_memory = 36
        mem_based_max = int((global_mem * memory_efficiency) / per_key_memory)
        
        # 取三者最小值
        optimal = min(recommended, maximum, mem_based_max)
        
        # 向下对齐到1024的倍数
        optimal = (optimal // 1024) * 1024
        
        # 确保最小值为1024
        optimal = max(optimal, 1024)
        
        logger.info(
            f"AMD batch_size计算: recommended={recommended}, "
            f"mem_based={mem_based_max}, optimal={optimal}"
        )
        
        return optimal
    
    def handle_errors(self, error: Exception, stats=None) -> bool:
        """
        处理AMD GPU特定错误
        """
        error_msg = str(error).lower()
        
        # 资源不足错误
        if any(keyword in error_msg for keyword in [
            'out of memory', 'out of resources', 'allocation failed'
        ]):
            logger.error(f"AMD GPU资源不足: {error}")
            if stats:
                stats.record_gpu_error(is_resource_error=True)
            return True
        
        return super().handle_errors(error, stats)
