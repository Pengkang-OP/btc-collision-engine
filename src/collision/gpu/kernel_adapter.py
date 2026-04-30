"""GPU内核适配器

将现有GPUKernel适配为IKernelExecutor接口。

版本: v2.0 (Phase 2)
创建日期: 2026-04-29
更新日期: 2026-04-29
"""

from typing import Any, Dict, List, Tuple, Optional
import logging
import time

from .protocols import IKernelExecutor, GPUDevice, GPUContext, GPUKernel, MatchResult

logger = logging.getLogger(__name__)


class GPUKernelAdapter(IKernelExecutor):
    """GPU内核适配器
    
    适配现有GPUKernel到IKernelExecutor接口。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """初始化适配器
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
    
    def compile_kernel(
        self,
        device: GPUDevice,
        context: GPUContext
    ) -> GPUKernel:
        """编译GPU内核
        
        Args:
            device: GPU设备
            context: GPU上下文
            
        Returns:
            GPU内核实例
            
        Raises:
            RuntimeError: 内核编译失败
        """
        try:
            from ...gpu.kernel_impl import GPUKernel as GPUKernelImpl
            from ...gpu.kernel import OPENCL_KERNEL_SOURCE
            
            logger.debug(f"开始编译GPU内核: device={device.name}, vendor={device.vendor}")
            
            # 使用底层GPUKernelImpl创建内核
            kernel_impl = GPUKernelImpl(  # type: ignore[call-arg]
                device=device.device_obj,
                context=context.context_obj,
                kernel_source=OPENCL_KERNEL_SOURCE,
                config=self.config
            )
            
            # 封装为统一的GPUKernel对象
            kernel = GPUKernel(
                kernel_obj=kernel_impl,
                name="batch_check",
                context=context
            )
            
            logger.info("GPU内核编译完成")
            return kernel
            
        except Exception as e:
            logger.error(f"GPU内核编译失败: {e}")
            raise RuntimeError(f"GPU内核编译失败: {e}") from e
    
    def execute_batch(
        self,
        kernel: GPUKernel,
        seed: bytes,
        batch_size: int,
        stop_event: Any = None
    ) -> Tuple[List[MatchResult], float]:
        """执行单个批次
        
        Args:
            kernel: GPU内核
            seed: 32字节随机种子
            batch_size: 批次大小
            stop_event: 停止事件
            
        Returns:
            (匹配结果列表, 执行时间ms)
            
        Raises:
            RuntimeError: 批次执行失败
        """
        if not kernel or not kernel.kernel_obj:
            raise RuntimeError("GPU内核未初始化")
        
        start_time = time.time()
        
        try:
            # 调用底层GPUKernel的run_batch方法
            kernel_impl = kernel.kernel_obj
            
            # 执行批次
            raw_matches = kernel_impl.run_batch(
                seed=seed,
                batch_size=batch_size,
                stop_event=stop_event
            )
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            # 转换为MatchResult格式
            matches = self._convert_matches(raw_matches)
            
            logger.debug(
                f"批次执行完成: "
                f"batch_size={batch_size:,}, "
                f"matches={len(matches)}, "
                f"time={execution_time_ms:.0f}ms"
            )
            
            return matches, execution_time_ms
            
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(f"GPU批次执行失败: {e}")
            raise RuntimeError(f"GPU批次执行失败: {e}") from e
    
    def _convert_matches(self, raw_matches: List[Dict]) -> List[MatchResult]:
        """转换匹配结果格式
        
        Args:
            raw_matches: 原始匹配结果列表
            
        Returns:
            MatchResult格式列表
        """
        matches = []
        
        for match in raw_matches:
            match_result: MatchResult = {
                'address': match.get('address', ''),
                'private_key': match.get('private_key', ''),
                'public_key': match.get('public_key', ''),
                'hash160': match.get('hash160', ''),
                'index': match.get('index', 0),
                'seed': match.get('seed', ''),
            }
            matches.append(match_result)
        
        return matches
