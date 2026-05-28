#!/usr/bin/env python3
"""GPU 自动调优器 — v5.0.1 轻量实现。.

根据设备硬件规格和基准测试结果，自动推荐最优的内核参数配置。
"""

from typing import Any

from ..utils import get_configured_logger

__all__ = ["GPUAutoTuner"]


logger = get_configured_logger(__name__)


class GPUAutoTuner:
    """GPU 内核参数自动调优器。.

    分析 GPU 硬件特性，推荐最优的 work_group_size、batch_size
    和 memory_usage_ratio 等参数。
    """

    # 厂商默认配置
    _VENDOR_DEFAULTS = {
        "intel": {"work_group_size": 256, "memory_ratio": 0.75, "queue_depth": 8},
        "nvidia": {"work_group_size": 512, "memory_ratio": 0.80, "queue_depth": 4},
        "amd": {"work_group_size": 256, "memory_ratio": 0.70, "queue_depth": 8},
    }

    # 显存阈值分档 (GB → batch_size)
    _MEMORY_TIERS = (
        (16, 16777216),
        (8, 8388608),
        (4, 4194304),
    )

    def __init__(self, device: Any) -> None:
        """初始化自动调优器。.

        Args:
            device: GPU 设备对象

        """
        self._device = device
        self._tuned_params: dict[str, Any] = {}
        self._tuned = False

    def auto_tune(self, benchmark_results: dict | None = None) -> dict[str, Any]:
        """自动调优 GPU 参数。.

        Args:
            benchmark_results: 可选，GPUBenchmarkSuite.run_benchmark() 的结果

        Returns:
            推荐参数配置字典，包含:
            - work_group_size: 推荐工作组大小
            - batch_size: 推荐批次大小
            - memory_usage_ratio: 推荐内存使用比例
            - queue_depth: 推荐命令队列深度

        """
        device_info = self._device.device_info if hasattr(self._device, "device_info") else {}
        vendor_name = str(device_info.get("vendor_name", device_info.get("vendor", ""))).lower()

        # 检测厂商并加载默认配置
        vendor = (
            "intel"
            if "intel" in vendor_name
            else ("nvidia" if "nvidia" in vendor_name else ("amd" if "amd" in vendor_name else "intel"))
        )
        defaults = self._VENDOR_DEFAULTS.get(vendor, self._VENDOR_DEFAULTS["intel"])

        # 基于计算单元数微调
        cu = device_info.get("max_compute_units", 512)
        wgs = min(defaults["work_group_size"], max(64, (cu // 4) * 4))

        # 基于显存大小调整 batch_size
        mem_gb = device_info.get("global_mem_size", 0) / (1024**3)
        batch_size = self._compute_hardware_batch_size(mem_gb)

        self._tuned_params = {
            "work_group_size": wgs,
            "batch_size": batch_size,
            "memory_usage_ratio": defaults["memory_ratio"],
            "queue_depth": defaults["queue_depth"],
        }
        self._tuned = True
        logger.info("GPU auto-tuning complete: %s", self._tuned_params)
        return self._tuned_params

    @staticmethod
    def _compute_hardware_batch_size(mem_gb: float) -> int:
        """根据显存大小计算硬件推荐的 batch_size.

        v5.2.4: 从 ``auto_tune`` 中提取为独立静态方法，
        供新增的 ``suggest_batch_size`` 和 ``start_tuning`` 复用。

        Args:
            mem_gb: 显存大小（GB）

        Returns:
            硬件推荐的 batch_size

        """
        for threshold, size in GPUAutoTuner._MEMORY_TIERS:
            if mem_gb >= threshold:
                return size
        return 2097152

    def suggest_batch_size(
        self,
        current_size: int,
        metrics: dict[str, Any] | None = None,
    ) -> int:
        """根据硬件规格和当前运行指标推荐 batch_size.

        优先使用硬件推荐的 batch_size；若当前运行指标（如 keys_per_second）
        显示当前大小性能更优，则保留当前值。

        Args:
            current_size: 当前使用的 batch_size
            metrics:      可选，当前性能指标字典（至少包含 keys_per_second）

        Returns:
            推荐的 batch_size

        """
        # 确保已调优
        if not self._tuned:
            self.auto_tune()

        hw_size = self._tuned_params.get("batch_size", 2097152)

        # 若提供性能指标且当前值小于硬件推荐，检查当前值是否明显更优
        if metrics and current_size < hw_size:
            cur_kps = metrics.get("keys_per_second", 0)
            hw_kps = metrics.get("hw_keys_per_second", 0)
            # 当前 batch_size 吞吐量不低于硬件推荐的 90%，保留当前值避免抖动
            if hw_kps and cur_kps and cur_kps >= hw_kps * 0.9:
                return current_size

        return hw_size

    @property
    def tuned_params(self) -> dict[str, Any] | None:
        """获取当前调优结果。."""
        return self._tuned_params if self._tuned else None
