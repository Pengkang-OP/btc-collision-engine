"""Intel GPU特定优化

针对Intel GPU(特别是Arc系列)的优化策略,包括:
- uint32 workaround避免global char* hang bug
- 超时保护机制
- 保守的batch_size策略
"""

from typing import Dict, Any
import logging
from .base import GPUVendorBase

logger = logging.getLogger(__name__)


class IntelGPUVendor(GPUVendorBase):
    """Intel GPU优化处理器"""
    
    def get_vendor_name(self) -> str:
        return "Intel"
    
    def apply_optimizations(self, device, profile: Dict[str, Any]):
        """
        应用Intel特定优化
        
        优化策略:
        1. uint32 workaround(避免global char* hang bug)
        2. 超时保护机制
        3. 保守的内存使用策略
        4. Arc驱动特定优化
        5. 根据驱动版本应用特定优化
        """
        logger.info(f"应用Intel优化策略: {device.device_info.get('name', 'Unknown')}")
        
        optimizations = profile.get('optimizations', [])
        known_issues = profile.get('known_issues', [])
        
        # 1. uint32 workaround - 关键优化
        if 'uint32_workaround' in optimizations:
            logger.info("启用uint32 workaround(避免Intel Arc global char* hang bug)")
            # 在GPUKernel中使用uint32*替代uchar*
            # 这是Intel Arc驱动的关键bug workaround
        
        # 2. 超时保护
        if 'timeout_protection' in optimizations:
            logger.info("启用超时保护机制")
            # 在GPUKernel.run_batch中添加30秒超时
            # 防止内核hang住导致GUI永久阻塞
        
        # 3. 异步传输
        if 'async_transfer' in optimizations:
            # 检查驱动是否支持
            if device.driver_optimization_flags.get('enable_async_compute', True):
                logger.debug("启用异步数据传输优化")
            else:
                logger.warning("Intel驱动版本较旧,禁用异步传输")
        
        # 4. 专业驱动优化
        if 'pro_driver_optimization' in optimizations:
            logger.debug("启用Intel Pro驱动优化")
            # Arc Pro系列使用专业驱动,更稳定
        
        # 5. 驱动特定优化
        if device.driver_optimization_flags.get('conservative_mode', False):
            logger.warning(
                "Intel驱动保守模式: "
                "使用更小的batch_size和更严格的超时"
            )
        
        # 记录已知问题
        if 'global_char_hang_bug' in known_issues:
            logger.warning(
                "Intel Arc存在global char* hang bug, "
                "已启用uint32 workaround"
            )
        
        memory_efficiency = profile.get('memory_efficiency', 0.45)
        logger.debug(f"Intel GPU内存效率: {memory_efficiency*100:.0f}% (保守策略)")
    
    def calculate_batch_size(self, device, profile: Dict[str, Any]) -> int:
        """
        计算Intel GPU的最优batch_size
        
        策略:
        1. Intel Arc需要使用更保守的batch_size
        2. 避免显存占用过高导致不稳定
        3. 优先考虑稳定性而非性能
        """
        recommended = profile.get('recommended_batch_size', 262144)
        maximum = profile.get('max_batch_size', 524288)
        memory_efficiency = profile.get('memory_efficiency', 0.45)
        
        # 根据显存计算理论最大值(使用更保守的memory_efficiency)
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
            f"Intel batch_size计算: recommended={recommended}, "
            f"mem_based={mem_based_max}, optimal={optimal} "
            f"(保守策略)"
        )
        
        return optimal
    
    def handle_errors(self, error: Exception, stats=None) -> bool:
        """
        处理Intel GPU特定错误
        
        Intel Arc容易出现超时和hang错误
        """
        error_msg = str(error).lower()
        
        # 超时错误
        if 'timeout' in error_msg or 'timed out' in error_msg:
            logger.error(f"Intel GPU执行超时: {error}")
            if stats:
                stats.record_gpu_error(is_resource_error=False)
            return True  # 继续执行,但记录错误
        
        # 内核hang错误
        if 'hang' in error_msg or 'stall' in error_msg:
            logger.error(f"Intel GPU内核hang: {error}")
            if stats:
                stats.record_gpu_error(is_resource_error=True)
            return True  # 继续执行
        
        # 资源不足
        if any(keyword in error_msg for keyword in [
            'out of memory', 'out of resources', 'allocation failed'
        ]):
            logger.error(f"Intel GPU资源不足: {error}")
            if stats:
                stats.record_gpu_error(is_resource_error=True)
            return True
        
        return super().handle_errors(error, stats)
