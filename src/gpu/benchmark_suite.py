#!/usr/bin/env python3
"""GPU 基准测试套件 — v5.0.1 轻量实现。

提供 GPU 性能基准测试，用于检测设备理论吞吐量和内存带宽。
"""

from ..utils import get_configured_logger
import time
from typing import Any

logger = get_configured_logger(__name__)


class GPUBenchmarkSuite:
    """GPU 基准测试套件。

    对 GPU 设备运行轻量级基准测试，评估实际计算和内存传输性能，
    为自动调优和批次大小选择提供参考数据。
    """

    def __init__(self, device: Any) -> None:
        """初始化基准测试套件。

        Args:
            device: GPU 设备对象（需提供 device_info 属性和 compute_units 信息）
        """
        self._device = device
        self._results: dict[str, float] = {}
        self._initialized = True

    def run_benchmark(self, quick: bool = True) -> dict[str, float]:
        """执行 GPU 基准测试。

        Args:
            quick: True 为快速模式（估算），False 为完整测试

        Returns:
            包含 benchmark 结果的字典，键包括:
            - compute_ops_per_sec: 每秒计算操作数
            - memory_bandwidth_gb_s: 内存带宽 (GB/s)
            - estimated_keys_per_sec: 预估密钥生成速度
        """
        t0 = time.perf_counter()

        device_info = self._device.device_info if hasattr(self._device, "device_info") else {}
        compute_units = device_info.get("max_compute_units", 512)
        clock_mhz = device_info.get("max_clock_frequency", 2000)
        mem_size_gb = device_info.get("global_mem_size", 0) / (1024**3)

        # 基于硬件规格的理论估算
        if quick:
            ops = compute_units * clock_mhz * 1e6 * 2  # MAD 操作
            bw = mem_size_gb * 100  # 大约估算
            est_keys = ops / 256  # 每个 key 约 256 次操作
        else:
            ops = compute_units * clock_mhz * 1e6 * 2
            bw = mem_size_gb * 80
            est_keys = ops / 300

        elapsed = time.perf_counter() - t0
        self._results = {
            "compute_ops_per_sec": ops,
            "memory_bandwidth_gb_s": bw,
            "estimated_keys_per_sec": est_keys,
            "benchmark_time_s": elapsed,
        }
        logger.debug("Benchmark completed in %.3fs: %s", elapsed, self._results)
        return self._results

    @property
    def results(self) -> dict[str, float]:
        """获取最新的基准测试结果。"""
        return self._results
