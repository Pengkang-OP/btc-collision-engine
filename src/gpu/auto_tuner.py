#!/usr/bin/env python3
"""GPU 自动调优器 — v5.0.1 轻量实现。

根据设备硬件规格和基准测试结果，自动推荐最优的内核参数配置。
"""

from typing import Any

from ..utils import get_configured_logger

logger = get_configured_logger(__name__)


class GPUAutoTuner:
    """GPU 内核参数自动调优器。

    分析 GPU 硬件特性，推荐最优的 work_group_size、batch_size
    和 memory_usage_ratio 等参数。
    """

    # 厂商默认配置
    _VENDOR_DEFAULTS = {
        "intel": {"work_group_size": 256, "memory_ratio": 0.75, "queue_depth": 8},
        "nvidia": {"work_group_size": 512, "memory_ratio": 0.80, "queue_depth": 4},
        "amd": {"work_group_size": 256, "memory_ratio": 0.70, "queue_depth": 8},
    }

    def __init__(self, device: Any) -> None:
        """初始化自动调优器。

        Args:
            device: GPU 设备对象

        """
        self._device = device
        self._tuned_params: dict[str, Any] = {}
        self._tuned = False

    def auto_tune(self, benchmark_results: dict | None = None) -> dict[str, Any]:
        """自动调优 GPU 参数。

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
        if mem_gb >= 16:
            batch_size = 16777216
        elif mem_gb >= 8:
            batch_size = 8388608
        elif mem_gb >= 4:
            batch_size = 4194304
        else:
            batch_size = 2097152

        self._tuned_params = {
            "work_group_size": wgs,
            "batch_size": batch_size,
            "memory_usage_ratio": defaults["memory_ratio"],
            "queue_depth": defaults["queue_depth"],
        }
        self._tuned = True
        logger.info("GPU auto-tuning complete: %s", self._tuned_params)
        return self._tuned_params

    @property
    def tuned_params(self) -> dict[str, Any] | None:
        """获取当前调优结果。"""
        return self._tuned_params if self._tuned else None
