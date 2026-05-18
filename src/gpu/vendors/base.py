"""GPU厂商基础接口

定义所有GPU厂商优化模块必须实现的接口。
"""

from abc import ABC, abstractmethod
from typing import Any

# 统一日志获取
from ...utils import get_configured_logger

logger = get_configured_logger("BaseVendor")


class GPUVendorBase(ABC):
    """GPU厂商基础抽象类"""

    @abstractmethod
    def get_vendor_name(self) -> str:
        """
        获取厂商名称

        Returns:
            厂商名称字符串
        """

    @abstractmethod
    def apply_optimizations(self, device: Any, profile: dict[str, Any]) -> None:
        """
        应用厂商特定的优化策略

        Args:
            device: GPUDevice实例
            profile: GPU型号配置字典
        """

    @abstractmethod
    def calculate_batch_size(self, device: Any, profile: dict[str, Any]) -> int:
        """
        计算最优batch_size

        Args:
            device: GPUDevice实例
            profile: GPU型号配置字典

        Returns:
            推荐的batch_size值
        """

    def handle_errors(self, error: Exception, stats: Any | None = None) -> bool:
        """
        处理厂商特定的错误

        Args:
            error: 捕获的异常
            stats: 统计对象(可选)

        Returns:
            True表示应该继续执行,False表示应该停止
        """
        # 默认实现:记录错误并继续
        logger.error(f"GPU错误: {type(error).__name__}: {error}")
        return True

    def get_optimization_flags(self, profile: dict[str, Any]) -> dict[str, bool]:
        """
        获取优化标志

        Args:
            profile: GPU型号配置字典

        Returns:
            优化标志字典
        """
        optimizations = profile.get("optimizations", [])

        return {
            "async_transfer": "async_transfer" in optimizations,
            "persistent_buffers": "persistent_buffers" in optimizations,
            "shared_memory_optimization": "shared_memory_optimization" in optimizations,
            "memory_coalescing": "memory_coalescing" in optimizations,
        }
