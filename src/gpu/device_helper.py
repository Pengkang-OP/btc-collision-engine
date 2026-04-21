"""GPU设备辅助工具函数

提供GPU错误处理、设备信息查询等静态方法。
从gpu_collision_engine.py迁移出来，解耦循环依赖（P1-2修复）。

迁移日期: 2026-04-22
"""
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class GPUDeviceHelper:
    """GPU设备辅助类
    
    提供静态方法供GPUKernel和其他模块使用。
    独立于GPU引擎，避免循环依赖。
    
    使用示例:
        >>> from src.gpu.device_helper import GPUDeviceHelper
        >>> GPUDeviceHelper.handle_gpu_batch_error("random", exception, stats)
    """
    
    @staticmethod
    def handle_gpu_batch_error(mode: str, e: Exception, 
                              stats: Optional[Any] = None) -> bool:
        """统一处理GPU计算批次异常
        
        Args:
            mode: 计算模式（随机碰撞/范围扫描/暴力穷举）
            e: 捕获的异常
            stats: 统计对象（可选）
            
        Returns:
            bool: 是否应该继续执行（总是返回True）
        """
        if isinstance(e, (RuntimeError, ValueError)):
            # OpenCL运行时错误或数据验证错误
            # 这些是可恢复的错误，跳过当前批次继续执行
            # 常见原因：GPU内存不足、内核参数错误、目标地址格式错误
            error_msg = str(e).lower()
            # 扩展资源不足关键词匹配，覆盖不同OpenCL实现的错误消息
            resource_keywords = [
                "out of resources", "memory", "out of memory", 
                "allocation failed", "insufficient", "resource exhausted",
                "cl_out_of_resources", "cl_mem_object_allocation_failure"
            ]
            is_resource_error = any(keyword in error_msg for keyword in resource_keywords)
            if is_resource_error:
                logger.error(f"GPU {mode}失败（资源不足）: {type(e).__name__}: {e}")
                if stats:
                    stats.record_gpu_error(is_resource_error=True)
            else:
                logger.error(f"GPU {mode}失败（运行时错误）: {type(e).__name__}: {e}")
                if stats:
                    stats.record_gpu_error(is_resource_error=False)
        elif isinstance(e, (TypeError, OverflowError)):
            # WIF编码或数据处理错误
            logger.error(f"GPU {mode}失败（数据错误）: {type(e).__name__}: {e}")
            if stats:
                stats.record_gpu_error(is_resource_error=False)
                stats.record_wif_encode_error()
        else:
            # 未知错误：记录完整堆栈
            logger.exception(f"GPU {mode}失败（未知错误）")
            if stats:
                stats.record_gpu_error(is_resource_error=False)
        return True  # 总是继续执行
    
    @staticmethod
    def get_device_capabilities(device: Any) -> dict:
        """获取设备能力信息
        
        Args:
            device: GPUDevice实例
            
        Returns:
            设备能力字典
        """
        return {
            'max_work_group_size': getattr(device, 'max_work_group_size', 256),
            'max_compute_units': getattr(device, 'max_compute_units', 1),
            'global_mem_size': getattr(device, 'global_mem_size', 0),
            'local_mem_size': getattr(device, 'local_mem_size', 0),
            'enable_async_execution': getattr(device, 'enable_async_execution', False),
        }
    
    @staticmethod
    def is_resource_error(exception: Exception) -> bool:
        """判断是否为资源不足错误
        
        Args:
            exception: 异常对象
            
        Returns:
            bool: 是否为资源错误
        """
        if not isinstance(exception, (RuntimeError, ValueError)):
            return False
        
        error_msg = str(exception).lower()
        resource_keywords = [
            "out of resources", "memory", "out of memory", 
            "allocation failed", "insufficient", "resource exhausted",
            "cl_out_of_resources", "cl_mem_object_allocation_failure"
        ]
        return any(keyword in error_msg for keyword in resource_keywords)
