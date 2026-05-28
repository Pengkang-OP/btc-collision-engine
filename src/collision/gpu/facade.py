"""GPU引擎外观层 - 统一GPU引擎入口.

提供 GPUEngineFacade 类，封装设备管理、内核执行和异步管道。
降低外部调用方与底层 GPU 模块的耦合。

组件:
- DeviceManagerAdapter: GPU设备管理
- GPUKernelAdapter: GPU内核执行
- AsyncPipelineAdapter: 异步执行管道

版本: v4.2.1 (Phase 2)
创建日期: 2026-04-30
"""

import threading
from typing import Any, cast

from src.utils import get_configured_logger

from .async_pipeline_adapter import AsyncPipelineAdapter
from .device_manager_adapter import DeviceManagerAdapter
from .kernel_adapter import GPUKernelAdapter
from .protocols import GPUContext, GPUDevice, GPUKernel

__all__ = ["GPUEngineFacade"]


logger = get_configured_logger(__name__)


class GPUEngineFacade:
    """GPU引擎外观层.

    统一封装 GPU 设备管理、内核执行和异步管道，
    为上层引擎提供简洁的接口。

    Usage:
        facade = GPUEngineFacade(config=config)
        facade.initialize(device_index=0, batch_size=1_000_000)
        # ... 使用 facade.kernel, facade.device 等
        facade.cleanup()
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """初始化 GPU 引擎外观.

        Args:
            config: GPU 配置字典

        """
        self.config = config or {}
        self._initialized = False
        self._lock = threading.Lock()

        # Phase 2 适配器
        self._device_manager = DeviceManagerAdapter(config=self.config)
        self._kernel_adapter = GPUKernelAdapter(config=self.config)
        self._async_pipeline = AsyncPipelineAdapter(config=self.config)

        # 暴露属性（向后兼容）
        self.device: GPUDevice | None = None
        self.context: GPUContext | None = None
        self.kernel: GPUKernel | None = None
        self.async_executor = self._async_pipeline

    def __enter__(self) -> "GPUEngineFacade":
        """上下文管理器入口."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """上下文管理器退出，自动清理资源."""
        self.cleanup()

    def initialize(
        self,
        device_index: int = 0,
        batch_size: int | None = None,
        targets: Any = None,
        check_uncompressed: int = 0,
    ) -> None:
        """初始化 GPU 设备、上下文和内核.

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
                logger.error("内核编译失败: %s", e)

        # 初始化异步管道
        try:
            if self.kernel is None:
                raise RuntimeError("GPUDeviceManager.kernel is None when initializing async pipeline")
            self._async_pipeline.initialize(
                kernel=self.kernel,
                batch_size=batch_size or 1_000_000,
            )
        except Exception as e:
            logger.error("异步管道初始化失败: %s", e)

        self._initialized = True
        logger.info("GPUEngineFacade 初始化完成: device=%s", device)

    def get_device_info(self) -> dict[str, Any]:
        """获取 GPU 设备信息.

        Returns:
            设备信息字典

        """
        if self.device is not None:
            return cast("Any", self.device).to_dict()
        return {"status": "not_initialized"}

    def is_initialized(self) -> bool:
        """检查是否已初始化."""
        return self._initialized

    def list_devices(self) -> list[GPUDevice]:
        """列出所有可用 GPU 设备.

        Returns:
            GPU 设备列表

        """
        return self._device_manager.list_devices()

    def cleanup(self) -> None:
        """清理 GPU 资源（线程安全）."""
        with self._lock:
            try:
                if self._async_pipeline is not None:
                    self._async_pipeline.cleanup()
            except Exception as e:
                logger.error("清理异步管道失败: %s", e)

            try:
                if self._device_manager is not None:
                    self._device_manager.release_all()
            except Exception as e:
                logger.error("清理设备管理器失败: %s", e)

            self.device = None
            self.context = None
            self.kernel = None
            self._initialized = False
            logger.info("GPUEngineFacade 资源清理完成")

    def __repr__(self) -> str:
        """返回对象的字符串表示。."""
        status = "initialized" if self._initialized else "not_initialized"
        device_name = self.device.name if self.device else "None"
        return f"GPUEngineFacade(status={status}, device={device_name})"
