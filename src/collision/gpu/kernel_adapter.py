"""GPU内核适配器

将现有GPUKernel适配为IKernelExecutor接口。

版本: v1.0
创建日期: 2026-04-29
"""

from typing import Any, Dict, List, Tuple, Optional
import logging

from .protocols import IKernelExecutor

logger = logging.getLogger(__name__)


class GPUKernelAdapter(IKernelExecutor):
    """GPU内核适配器
    
    适配现有GPUKernel到IKernelExecutor接口。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化适配器
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
    
    def compile_kernel(self, device: Any, context: Any) -> Any:
        """编译GPU内核
        
        Args:
            device: GPU设备
            context: GPU上下文
            
        Returns:
            GPU内核实例
        """
        # TODO: Phase 2实现
        try:
            from ...gpu.kernel_impl import GPUKernel
            from ...gpu.kernel import OPENCL_KERNEL_SOURCE
            
            kernel = GPUKernel(
                device=device,
                context=context,
                kernel_source=OPENCL_KERNEL_SOURCE,
                config=self.config
            )
            
            logger.debug("GPU内核编译完成")
            return kernel
            
        except Exception as e:
            logger.error(f"GPU内核编译失败: {e}")
            raise
    
    def execute_batch(
        self,
        kernel: Any,
        seed: bytes,
        batch_size: int,
        stop_event: Any = None
    ) -> Tuple[List[Dict[str, int]], float]:
        """执行单个批次
        
        Args:
            kernel: GPU内核
            seed: 32字节随机种子
            batch_size: 批次大小
            stop_event: 停止事件
            
        Returns:
            (匹配结果列表, 执行时间ms)
        """
        # TODO: Phase 2实现
        import time
        
        start_time = time.time()
        
        try:
            # 调用现有GPUKernel的run_batch方法
            matches = kernel.run_batch(
                seed=seed,
                batch_size=batch_size,
                stop_event=stop_event
            )
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            return matches, execution_time_ms
            
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(f"GPU批次执行失败: {e}")
            raise
