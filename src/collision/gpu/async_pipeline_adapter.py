"""异步执行管道适配器

将现有AsyncGPUExecutor适配为IAsyncExecutionPipeline接口。

版本: v1.0
创建日期: 2026-04-29
"""

from typing import Any, Dict, List, Tuple, Optional
import logging

from .protocols import IAsyncExecutionPipeline

logger = logging.getLogger(__name__)


class AsyncPipelineAdapter(IAsyncExecutionPipeline):
    """异步执行管道适配器
    
    适配现有AsyncGPUExecutor到IAsyncExecutionPipeline接口。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化适配器
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self._pipeline = None
    
    def initialize(self, kernel: Any, batch_size: int) -> None:
        """初始化异步管道
        
        Args:
            kernel: GPU内核
            batch_size: 批次大小
        """
        # TODO: Phase 2实现
        try:
            from ...gpu.async_executor import AsyncGPUExecutor
            
            self._pipeline = AsyncGPUExecutor(
                kernel=kernel,
                batch_size=batch_size,
                config=self.config
            )
            self._pipeline.initialize_buffers()
            
            logger.debug(f"异步管道初始化完成: batch_size={batch_size:,}")
            
        except Exception as e:
            logger.error(f"异步管道初始化失败: {e}")
            raise
    
    def run_batch(
        self,
        seed: bytes,
        batch_size: int
    ) -> Tuple[List[Dict[str, int]], float]:
        """运行单个批次
        
        Args:
            seed: 随机种子
            batch_size: 批次大小
            
        Returns:
            (匹配结果列表, 执行时间ms)
        """
        # TODO: Phase 2实现
        if not self._pipeline:
            raise RuntimeError("异步管道未初始化")
        
        try:
            # 调用现有AsyncGPUExecutor的run_batch_async方法
            matches, exec_time_ms = self._pipeline.run_batch_async(
                seed=seed,
                batch_size=batch_size
            )
            
            return matches, exec_time_ms
            
        except Exception as e:
            logger.error(f"异步批次执行失败: {e}")
            raise
    
    def cleanup(self) -> None:
        """清理异步管道资源"""
        if not self._pipeline:
            return
        
        try:
            self._pipeline.cleanup()
            self._pipeline = None
            logger.debug("异步管道资源已清理")
        except Exception as e:
            logger.error(f"异步管道清理失败: {e}")
