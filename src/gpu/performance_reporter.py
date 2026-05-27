#!/usr/bin/env python3
"""GPU 性能报告生成器 — v5.0.1 轻量实现。.

汇总 GPU 运行性能指标，生成结构化性能报告。

v5.2.4: 新增 ReportConfig dataclass 和 PerformanceReportGenerator.generate_report()，
        修复 optimization_pipeline 中 ReportConfig 缺失导致的死代码问题。
"""

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from ..utils import get_configured_logger

logger = get_configured_logger(__name__)


@dataclass
class ReportConfig:
    """性能报告生成配置项。.

    v5.2.4: 新增，供 PerformanceReportGenerator.generate_report() 使用。

    Attributes:
        include_device_info: 包含设备信息
        include_benchmark_results: 包含基准测试结果
        include_tuning_results: 包含调优结果
        include_history: 包含历史趋势
        include_recommendations: 包含优化建议
        include_comparison: 包含历史对比

    """

    include_device_info: bool = True
    include_benchmark_results: bool = True
    include_tuning_results: bool = True
    include_history: bool = True
    include_recommendations: bool = True
    include_comparison: bool = False


class PerformanceReportGenerator:
    """GPU 性能报告生成器。.

    收集 GPU 引擎运行期间的关键性能指标（吞吐量、延迟、
    内存使用等），生成结构化的性能分析报告。
    """

    def __init__(self) -> None:
        """初始化性能报告生成器。."""
        self._metrics: list[dict[str, Any]] = []
        self._start_time: float = 0.0
        self._running = False

    def start(self) -> None:
        """开始性能数据采集。."""
        self._start_time = time.perf_counter()
        self._running = True
        self._metrics = []
        logger.debug("Performance reporter started")

    def record(self, **metrics: Any) -> None:
        """记录一条性能指标数据点。.

        Args:
            **metrics: 键值对形式的性能指标，可包含:
                - keys_checked: 本次检查私钥数
                - elapsed_ms: 耗时（毫秒）
                - memory_used_mb: 显存使用量 (MB)
                - batch_id: 批次编号

        """
        if self._running:
            self._metrics.append(
                {
                    "timestamp": time.perf_counter() - self._start_time,
                    **metrics,
                },
            )

    def stop(self) -> dict[str, Any]:
        """停止采集并生成汇总报告。.

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

    def generate_report(
        self,
        config: ReportConfig | None = None,
        output_dir: str | None = None,
    ) -> str:
        """生成结构化性能报告文件（JSON格式）。.

        v5.2.4: 新增方法，补全 ReportConfig + generate_report 缺失的 API，
        修复 optimization_pipeline.generate_report() 中的死代码问题。

        Args:
            config: 报告配置（默认使用全部启用）
            output_dir: 输出目录（默认使用当前工作目录）

        Returns:
            报告文件路径；写入失败返回空字符串

        """
        cfg = config or ReportConfig()

        # 确认已停止采集，获取汇总数据
        summary: dict[str, Any] = self.stop() if self._running else {}

        # 构建报告内容
        report_data: dict[str, Any] = {
            "generated_at": datetime.now().isoformat(),
            "config": asdict(cfg),
        }
        if cfg.include_benchmark_results or cfg.include_recommendations:
            report_data["summary"] = summary or self.stop()
        if cfg.include_history:
            report_data["raw_metrics"] = self._metrics

        # 写入文件
        out_dir = output_dir or os.getcwd()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(out_dir, f"gpu_performance_report_{timestamp}.json")

        try:
            os.makedirs(out_dir, exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            logger.info("性能报告已生成: %s", report_path)
            return report_path
        except (OSError, TypeError) as exc:
            logger.error("写入性能报告失败: %s", exc)
            return ""
