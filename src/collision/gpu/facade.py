"""GPU引擎外观层

封装GPU设备、上下文、内核的初始化和执行逻辑，
提供统一的简化接口给上层引擎使用。

职责:
- GPU资源生命周期管理
- 内核编译与加载
- 异步执行调度
- 缓冲区管理

版本: v1.0
创建日期: 2026-04-29
"""

from typing import Optional, Dict, Any, List, Tuple
import logging

from .protocols import (
    IGPUDeviceManager,
    IKernelExecutor,
    IAsyncExecutionPipeline,
    GPUExecutionContext,
    GPUDevice,
    GPUContext,
    GPUKernel,
    CollisionResult,
)

logger = logging.getLogger(__name__)


class GPUEngineFacade:
    """GPU引擎外观类
    
    职责:
    - 封装GPU设备/上下文/内核的复杂性
    - 提供统一的执行接口
    - 管理异步执行管道
    - 资源生命周期管理
    
    使用示例:
        >>> facade = GPUEngineFacade(config=config)
        >>> facade.initialize(device_index=-1, batch_size=1000000)
        >>> matches, time_ms = facade.execute_batch(seed, batch_size)
        >>> facade.cleanup()
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化GPU引擎外观
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self._context: Optional[GPUExecutionContext] = None
        self._initialized = False
        
        # 延迟初始化组件
        self._device_manager: Optional[IGPUDeviceManager] = None
        self._kernel_executor: Optional[IKernelExecutor] = None
        self._async_pipeline: Optional[IAsyncExecutionPipeline] = None
        
        logger.debug("GPUEngineFacade 初始化完成")
    
    def initialize(
        self,
        device_index: int = -1,
        batch_size: Optional[int] = None
    ) -> None:
        """初始化GPU资源
        
        Args:
            device_index: GPU设备索引，-1表示自动选择
            batch_size: 批次大小，None表示自动计算
            
        Raises:
            RuntimeError: GPU初始化失败
        """
        if self._initialized:
            logger.warning("GPU引擎已初始化，跳过重复初始化")
            return
        
        try:
            # 1. 创建执行上下文
            batch_size = batch_size or self.config.get('batch_size', 1_000_000)
            self._context = GPUExecutionContext(
                batch_size=batch_size,
                vendor="unknown",  # 将在设备选择后更新
                config=self.config
            )
            
            # 2. 选择GPU设备
            self._device_manager = self._create_device_manager()
            device = self._device_manager.select_device(device_index)
            self._context.device = device
            self._context.vendor = self._detect_vendor(device)
            
            # 3. 创建GPU上下文
            context = self._device_manager.create_context(device)
            self._context.context = context
            
            # 4. 编译内核
            self._kernel_executor = self._create_kernel_executor()
            kernel = self._kernel_executor.compile_kernel(device, context)
            self._context.kernel = kernel
            
            # 5. 初始化异步管道
            self._async_pipeline = self._create_async_pipeline()
            self._async_pipeline.initialize(kernel, batch_size)
            
            self._initialized = True
            logger.info(
                f"GPU引擎初始化完成: "
                f"device_index={device_index}, "
                f"batch_size={batch_size:,}, "
                f"vendor={self._context.vendor}"
            )
            
        except Exception as e:
            logger.error(f"GPU引擎初始化失败: {e}")
            self.cleanup()
            raise RuntimeError(f"GPU引擎初始化失败: {e}") from e
    
    def execute_batch(
        self,
        seed: bytes,
        batch_size: Optional[int] = None
    ) -> CollisionResult:
        """执行单个批次
        
        Args:
            seed: 32字节随机种子
            batch_size: 批次大小，None使用初始化时的值
            
        Returns:
            CollisionResult: 碰撞结果
            
        Raises:
            RuntimeError: 引擎未初始化
        """
        if not self._initialized:
            raise RuntimeError("GPU引擎未初始化，请先调用initialize()")
        
        if not self._context:
            raise RuntimeError("GPU执行上下文未创建")
        
        batch_size = batch_size or self._context.batch_size
        
        try:
            # 委托给异步管道执行
            matches, exec_time_ms = self._async_pipeline.run_batch(
                seed=seed,
                batch_size=batch_size
            )
            
            return CollisionResult(
                matches=matches,
                execution_time_ms=exec_time_ms,
                batch_size=batch_size
            )
            
        except Exception as e:
            logger.error(f"GPU批次执行失败: {e}")
            raise
    
    def cleanup(self) -> None:
        """清理所有GPU资源"""
        if not self._initialized:
            return
        
        try:
            # 1. 清理异步管道
            if self._async_pipeline:
                self._async_pipeline.cleanup()
                self._async_pipeline = None
            
            # 2. 释放设备资源
            if self._device_manager:
                self._device_manager.release_all()
                self._device_manager = None
            
            # 3. 重置上下文
            self._context = None
            self._kernel_executor = None
            self._initialized = False
            
            logger.info("GPU引擎资源清理完成")
            
        except Exception as e:
            logger.error(f"GPU引擎资源清理失败: {e}")
    
    def is_initialized(self) -> bool:
        """检查引擎是否已初始化"""
        return self._initialized
    
    def get_context(self) -> Optional[GPUExecutionContext]:
        """获取GPU执行上下文"""
        return self._context
    
    # ========== 私有方法 ==========
    
    def _create_device_manager(self) -> IGPUDeviceManager:
        """创庺GPU设备管理器
            
        Returns:
            GPU设备管理器实例
        """
        # TODO: Phase 2实现 - 从现有GPUDeviceManager适配
        from ...gpu.device_manager import GPUDeviceManager
        return GPUDeviceManager(config=self.config)
    
    def _create_kernel_executor(self) -> IKernelExecutor:
        """创建GPU内核执行器
        
        Returns:
            GPU内核执行器实例
        """
        # TODO: Phase 2实现 - 从现有GPUKernel适配
        from .kernel_adapter import GPUKernelAdapter
        return GPUKernelAdapter(config=self.config)
    
    def _create_async_pipeline(self) -> IAsyncExecutionPipeline:
        """创建异步执行管道
        
        Returns:
            异步执行管道实例
        """
        # TODO: Phase 2实现 - 从现有AsyncGPUExecutor适配
        from .async_pipeline_adapter import AsyncPipelineAdapter
        return AsyncPipelineAdapter(config=self.config)
    
    def _detect_vendor(self, device: GPUDevice) -> str:
        """检测GPU厂商
        
        Args:
            device: GPU设备实例
            
        Returns:
            厂商标识符: 'intel', 'nvidia', 'amd', 'unknown'
        """
        # 如果设备对象已有vendor信息，直接使用
        if device and device.vendor != "unknown":
            return device.vendor
        
        # TODO: Phase 2实现 - 从现有vendor检测逻辑提取
        try:
            if device.device_obj:
                from ...gpu.device import identify_vendor
                return identify_vendor(device.device_obj)
        except Exception:
            pass
        
        return "unknown"
