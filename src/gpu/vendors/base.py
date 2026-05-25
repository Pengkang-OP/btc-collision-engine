"""GPU厂商基础接口

定义所有GPU厂商优化模块必须实现的接口。
"""

from abc import ABC, abstractmethod
from typing import Any

# 统一日志获取
from ...utils import get_configured_logger
from ..constants import PER_KEY_MEMORY_BYTES, align_batch_size

logger = get_configured_logger("BaseVendor")


class GPUVendorBase(ABC):
    """GPU厂商基础抽象类

    子类可覆盖以下类常量以自定义 batch_size 计算默认值:
        _RECOMMENDED_BATCH: 推荐 batch_size (默认 524288)
        _MAX_BATCH: 最大 batch_size (默认 1048576)
        _MEMORY_EFFICIENCY: 显存效率系数 (默认 0.60)
    """

    _RECOMMENDED_BATCH: int = 524288
    _MAX_BATCH: int = 1048576
    _MEMORY_EFFICIENCY: float = 0.60

    @abstractmethod
    def get_vendor_name(self) -> str:
        """获取厂商名称

        Returns:
            厂商名称字符串

        """

    @abstractmethod
    def apply_optimizations(self, device: Any, profile: dict[str, Any]) -> None:
        """应用厂商特定的优化策略

        Args:
            device: GPUDevice实例
            profile: GPU型号配置字典

        """

    def calculate_batch_size(self, device: Any, profile: dict[str, Any]) -> int:
        """计算最优 batch_size (Task 11 refactor: 从 3 个子类提取到基类)

        策略:
        1. 使用 profile 中的 recommended_batch_size (回退到类常量)
        2. 根据显存大小调整
        3. 确保不超过 max_batch_size

        Args:
            device: GPUDevice实例
            profile: GPU型号配置字典

        Returns:
            推荐的 batch_size 值

        """
        recommended = profile.get(
            "recommended_batch_size",
            self._RECOMMENDED_BATCH,
        )
        maximum = profile.get("max_batch_size", self._MAX_BATCH)
        memory_efficiency = profile.get(
            "memory_efficiency",
            self._MEMORY_EFFICIENCY,
        )

        global_mem = device.device_info.get("global_mem_size", 0)
        mem_based_max = int((global_mem * memory_efficiency) / PER_KEY_MEMORY_BYTES)

        optimal = min(recommended, maximum, mem_based_max)
        optimal = align_batch_size(optimal)

        logger.info(
            "%s batch_size: recommended=%s, mem_based=%s, optimal=%s",
            self.get_vendor_name(),
            recommended,
            mem_based_max,
            optimal,
        )

        return optimal

    @staticmethod
    def _is_resource_error(error_msg: str) -> bool:
        """检查是否为 GPU 资源不足错误"""
        return any(
            keyword in error_msg.lower()
            for keyword in ["out of memory", "out of resources", "allocation failed"]
        )

    def handle_errors(self, error: Exception, stats: Any | None = None) -> bool:
        """处理厂商特定的错误 (Task 11 refactor: 资源错误检测提升到基类)

        子类可覆盖以添加厂商特定错误处理，但应调用 super().handle_errors()。

        Args:
            error: 捕获的异常
            stats: 统计对象(可选)

        Returns:
            True表示应该继续执行, False表示应该停止

        """
        error_msg = str(error)

        if self._is_resource_error(error_msg):
            logger.error("%s GPU资源不足: %s", self.get_vendor_name(), error)
            if stats:
                stats.record_gpu_error(is_resource_error=True)
            return True

        logger.error("GPU错误: %s: %s", type(error).__name__, error)
        return True

    def get_optimization_flags(self, profile: dict[str, Any]) -> dict[str, bool]:
        """获取优化标志

        Args:
            profile: GPU型号配置字典

        Returns:
            优化标志字典

        """
        optimizations = profile.get("optimizations", [])

        return {
            "enable_fast_math": "fast_math" in optimizations,
            "enable_async_compute": "async_compute" in optimizations,
            "conservative_mode": "conservative" in optimizations,
            "enable_shader_cache": "shader_cache" in optimizations,
        }
