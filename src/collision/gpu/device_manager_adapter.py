"""GPU设备管理器适配器

将现有 GPUDevice / GPUDeviceDetector / GPUContext 适配为
IGPUDeviceManager 协议接口，使外观层能够通过统一协议管理设备。

版本: v2.0 (Phase 2)
创建日期: 2026-04-30
"""

from typing import Any, Dict, List, Optional
import logging

from .protocols import GPUDevice, GPUContext

logger = logging.getLogger(__name__)


class DeviceManagerAdapter:
    """GPU设备管理器适配器

    适配现有 GPUDevice + GPUDeviceDetector + GPUContext
    到 IGPUDeviceManager 协议。

    职责:
    - 设备发现与列举
    - 设备选择与初始化
    - 上下文创建
    - 资源释放

    使用示例:
        >>> adapter = DeviceManagerAdapter(config=config)
        >>> devices = adapter.list_devices()
        >>> device = adapter.select_device(device_index=0)
        >>> context = adapter.create_context(device)
        >>> adapter.release_all()
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        device_index: int = -1,
    ) -> None:
        """初始化设备管理器适配器

        Args:
            config: 配置字典
            device_index: 默认设备索引，-1 表示自动选择
        """
        self.config = config or {}
        self._default_device_index = device_index

        # 内部状态：持有底层 GPUDevice 和 GPUContext 实例
        self._gpu_device: Any = None  # src.gpu.device.GPUDevice
        self._gpu_context: Any = None  # src.gpu.context.GPUContext
        self._selected_device: Optional[GPUDevice] = None
        self._selected_context: Optional[GPUContext] = None

    def list_devices(self) -> List[GPUDevice]:
        """列出所有可用 GPU 设备

        通过 GPUDeviceDetector.detect_devices() 发现设备，
        并转换为统一的 GPUDevice 数据对象。

        Returns:
            GPUDevice 列表
        """
        try:
            from ...gpu.device import GPUDeviceDetector, identify_vendor

            raw_devices = GPUDeviceDetector.detect_devices()

            devices: List[GPUDevice] = []
            for idx, dev_info in enumerate(raw_devices):
                name = dev_info.get("name", "Unknown")
                vendor_str = dev_info.get("vendor", "")
                vendor = identify_vendor(name, vendor_str)
                memory_total = dev_info.get("global_mem_size", 0)

                device = GPUDevice(
                    device_id=idx,
                    vendor=vendor,
                    name=name,
                    memory_total=memory_total,
                    device_obj=dev_info.get("device"),
                )
                devices.append(device)

            logger.debug(f"设备列表: 发现 {len(devices)} 个可用 GPU")
            return devices

        except Exception as e:
            logger.error(f"列举 GPU 设备失败: {e}")
            return []

    def select_device(self, device_index: int = -1) -> GPUDevice:
        """选择 GPU 设备

        Args:
            device_index: 设备索引，-1 表示自动选择最佳设备

        Returns:
            GPUDevice 实例

        Raises:
            RuntimeError: 没有可用设备或设备初始化失败
        """
        idx = device_index if device_index >= 0 else self._default_device_index

        try:
            from ...gpu.device import GPUDevice as GPUDeviceImpl, GPUDeviceDetector, identify_vendor

            # 检查 GPU 可用性
            if not GPUDeviceDetector.is_gpu_available():
                raise RuntimeError("没有可用的 GPU 设备")

            # 创建底层 GPUDevice 并初始化
            self._gpu_device = GPUDeviceImpl()

            # 读取异步配置
            enable_async = self._read_async_config()

            # 初始化设备（-1 表示自动选择最佳）
            self._gpu_device.initialize(idx, enable_async=enable_async)

            # 获取设备信息
            dev_info = self._gpu_device.get_device_info()
            name = dev_info.get("name", "Unknown")
            vendor_str = dev_info.get("vendor", "")
            vendor_identifier = dev_info.get("vendor_identifier", identify_vendor(name, vendor_str))
            memory_total = dev_info.get("global_mem_size", 0)
            actual_index = dev_info.get("device_index", idx)

            # 创建协议层 GPUDevice
            self._selected_device = GPUDevice(
                device_id=actual_index,
                vendor=vendor_identifier,
                name=name,
                memory_total=memory_total,
                device_obj=self._gpu_device,
            )

            logger.info(
                f"GPU 设备已选择: {name} "
                f"(vendor={vendor_identifier}, memory={memory_total / (1024**3):.1f}GB)"
            )

            return self._selected_device

        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"选择 GPU 设备失败: {e}")
            raise RuntimeError(f"选择 GPU 设备失败: {e}") from e

    def create_context(self, device: GPUDevice) -> GPUContext:
        """创建 GPU 上下文

        Args:
            device: GPUDevice 实例

        Returns:
            GPUContext 实例

        Raises:
            RuntimeError: 上下文创建失败
        """
        try:
            from ...gpu.context import GPUContext as GPUContextImpl

            # 底层 GPUDevice 已经在 select_device 中初始化
            if self._gpu_device is None:
                raise RuntimeError("GPU 设备未初始化，请先调用 select_device()")

            # 创建上下文
            self._gpu_context = GPUContextImpl(self._gpu_device)

            # 应用优化
            if hasattr(self._gpu_context, "apply_optimizations"):
                self._gpu_context.apply_optimizations()

            # 创建协议层 GPUContext
            self._selected_context = GPUContext(
                context_obj=self._gpu_context,
                device=device,
            )

            logger.info("GPU 上下文已创建并优化")
            return self._selected_context

        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"创建 GPU 上下文失败: {e}")
            raise RuntimeError(f"创建 GPU 上下文失败: {e}") from e

    def release_all(self) -> None:
        """释放所有 GPU 资源

        按照上下文 → 设备的顺序释放。
        """
        try:
            # 释放上下文
            if self._gpu_context and hasattr(self._gpu_context, "cleanup"):
                self._gpu_context.cleanup()
                self._gpu_context = None
                self._selected_context = None

            # 释放设备
            if self._gpu_device and hasattr(self._gpu_device, "cleanup"):
                self._gpu_device.cleanup()
                self._gpu_device = None
                self._selected_device = None

            logger.info("设备管理器：GPU 资源已释放")

        except Exception as e:
            logger.error(f"释放 GPU 资源失败: {e}")

    def get_native_device(self) -> Any:
        """获取底层 GPUDevice 实例

        用于需要直接访问底层 API 的场景（如内存池、内核编译等）。

        Returns:
            底层 GPUDevice 实例，未初始化时返回 None
        """
        return self._gpu_device

    def get_native_context(self) -> Any:
        """获取底层 GPUContext 实例

        Returns:
            底层 GPUContext 实例，未初始化时返回 None
        """
        return self._gpu_context

    def _read_async_config(self) -> bool:
        """读取异步执行配置

        Returns:
            是否启用异步执行
        """
        enable_async = True

        # 从构造函数传入的配置中读取
        gpu_config = self.config.get("gpu", {})
        if "async_execution" in gpu_config:
            enable_async = bool(gpu_config["async_execution"])

        return enable_async
