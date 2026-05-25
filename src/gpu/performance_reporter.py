#!/usr/bin/env python3
"""GPU 性能报告生成器 — v5.0.1 轻量实现。

汇总 GPU 运行性能指标，生成结构化性能报告。
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class PerformanceReportGenerator:
    """GPU 性能报告生成器。

    收集 GPU 引擎运行期间的关键性能指标（吞吐量、延迟、
    内存使用等），生成结构化的性能分析报告。
    """

    def __init__(self) -> None:
        """初始化性能报告生成器。"""
        self._metrics: list[dict[str, Any]] = []
        self._start_time: float = 0.0
        self._running = False

    def start(self) -> None:
        """开始性能数据采集。"""
        self._start_time = time.perf_counter()
        self._running = True
        self._metrics = []
        logger.debug("Performance reporter started")

    def record(self, **metrics: Any) -> None:
        """记录一条性能指标数据点。

        Args:
            **metrics: 键值对形式的性能指标，可包含:
                - keys_checked: 本次检查私钥数
                - elapsed_ms: 耗时（毫秒）
                - memory_used_mb: 显存使用量 (MB)
                - batch_id: 批次编号
        """
        if self._running:
            self._metrics.append({
                "timestamp": time.perf_counter() - self._start_time,
                **metrics,
            })

    def stop(self) -> dict[str, Any]:
        """停止采集并生成汇总报告。

        Returns:
            汇总性能报告，包含:
            - total_keys: 总检查私钥数
            - total_time_s: 总耗时（秒）
            - avg_keys_per_sec: 平均速度
            - peak_memory_mb: 峰值显存 (MB)
            - sample_count: 数据点数量
        """
        self._running = False
        elapsed = time.perf_counter() - self._start_time

        if not self._metrics:
            logger.debug("No performance metrics recorded")
            return {"total_keys": 0, "total_time_s": elapsed, "avg_keys_per_sec": 0}

        total_keys = sum(m.get("keys_checked", 0) for m in self._metrics)
        peak_mem = max((m.get("memory_used_mb", 0) for m in self._metrics), default=0)

        report = {
            "total_keys": total_keys,
            "total_time_s": elapsed,
            "avg_keys_per_sec": total_keys / elapsed if elapsed > 0 else 0,
            "peak_memory_mb": peak_mem,
            "sample_count": len(self._metrics),
        }
        logger.info("Performance report: %s", report)
        return report
