"""GPU引擎外观层 - 统一GPU引擎入口

提供 GPUEngineFacade 类，封装设备管理、内核执行和异步管道。
降低外部调用方与底层 GPU 模块的耦合。

组件:
- DeviceManagerAdapter: GPU设备管理
- GPUKernelAdapter: GPU内核执行
- AsyncPipelineAdapter: 异步执行管道

版本: v1.0.0 (Phase 2)
创建日期: 2026-04-30
"""

import logging
from typing import Optional, Dict, Any, List, cast

from .device_manager_adapter import DeviceManagerAdapter
from .kernel_adapter import GPUKernelAdapter
from .async_pipeline_adapter import AsyncPipelineAdapter
from .protocols import GPUDevice, GPUContext, GPUKernel

logger = logging.getLogger(__name__)


class GPUEngineFacade:
    """GPU引擎外观层

    统一封装 GPU 设备管理、内核执行和异步管道，
    为上层引擎提供简洁的接口。

    Usage:
        facade = GPUEngineFacade(config=config)
        facade.initialize(device_index=0, batch_size=1_000_000)
        # ... 使用 facade.kernel, facade.device 等
        facade.cleanup()
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """初始化 GPU 引擎外观

        Args:
            config: GPU 配置字典
        """
        self.config = config or {}
        self._initialized = False

        # Phase 2 适配器
        self._device_manager = DeviceManagerAdapter(config=self.config)
        self._kernel_adapter = GPUKernelAdapter(config=self.config)
        self._async_pipeline = AsyncPipelineAdapter(config=self.config)

        # 暴露属性（向后兼容）
        self.device: Optional[GPUDevice] = None
        self.context: Optional[GPUContext] = None
        self.kernel: Optional[GPUKernel] = None
        self.async_executor = self._async_pipeline

    def initialize(
        self,
        device_index: int = 0,
        batch_size: Optional[int] = None,
        targets: Any = None,
        check_uncompressed: int = 0,
    ) -> None:
        """初始化 GPU 设备、上下文和内核

        Args:
            device_index: GPU 设备索引
            batch_size: 批次大小
            targets: 目标地址（可选）
            check_uncompressed: 是否检查未压缩地址
        """
        if self._initialized:
            logger.warning("GPUEngineFacade 已初始化，跳过重复初始化")
            return

        # 选择并创建设备
        device = self._device_manager.select_device(device_index)
        if device is not None:
            self.device = device
            self.context = self._device_manager.create_context(device)

        # 编译内核
        if self.context is not None and device is not None:
            try:
                kernel = self._kernel_adapter.compile_kernel(device, self.context)
                self.kernel = kernel
            except Exception as e:
                logger.error(f"内核编译失败: {e}")

        # 初始化异步管道
        try:
            assert self.kernel is not None
            self._async_pipeline.initialize(
                kernel=self.kernel,
                batch_size=batch_size or 1_000_000,
            )
        except Exception as e:
            logger.error(f"异步管道初始化失败: {e}")

        self._initialized = True
        logger.info(f"GPUEngineFacade 初始化完成: device={device}")

    def get_device_info(self) -> Dict[str, Any]:
        """获取 GPU 设备信息

        Returns:
            设备信息字典
        """
        if self.device is not None:
            return cast(Any, self.device).to_dict()
        return {"status": "not_initialized"}

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    def list_devices(self) -> List[GPUDevice]:
        """列出所有可用 GPU 设备

        Returns:
            GPU 设备列表
        """
        return self._device_manager.list_devices()

    def cleanup(self) -> None:
        """清理 GPU 资源"""
        try:
            if self._async_pipeline is not None:
                self._async_pipeline.cleanup()
        except Exception as e:
            logger.error(f"清理异步管道失败: {e}")

        try:
            if self._device_manager is not None:
                self._device_manager.release_all()
        except Exception as e:
            logger.error(f"清理设备管理器失败: {e}")

        self.device = None
        self.context = None
        self.kernel = None
        self._initialized = False
        logger.info("GPUEngineFacade 资源清理完成")

    def __repr__(self) -> str:
        status = "initialized" if self._initialized else "not_initialized"
        device_name = self.device.name if self.device else "None"
        return f"GPUEngineFacade(status={status}, device={device_name})"
