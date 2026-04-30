"""GPU 详细性能报告生成器

生成全面的 GPU 性能报告，包括：
1. 设备信息
2. 性能基准测试结果
3. 自动调优结果
4. 历史性能趋势
5. 优化建议
6. 与其他设备的对比

支持导出格式：
- Markdown
- JSON
- HTML (可选)
"""

import os
import sys
import time
import json
from src.utils.fast_json import fast_dumps
import logging
from ..utils import init_logging, get_configured_logger
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass

logger = get_configured_logger("GPUPerformanceReporter")


@dataclass
class ReportConfig:
    """报告配置"""

    include_device_info: bool = True
    include_benchmark_results: bool = True
    include_tuning_results: bool = True
    include_history: bool = True
    include_recommendations: bool = True
    include_comparison: bool = False

    # 输出格式
    format: str = "markdown"  # markdown, json, html

    # 文件路径
    output_dir: str = "./logs"


class PerformanceReportGenerator:
    """性能报告生成器

    使用示例:
        >>> generator = PerformanceReportGenerator(gpu_engine)
        >>> # 生成报告
        >>> report = generator.generate_report()
        >>> # 保存报告
        >>> generator.save_report(report, "gpu_performance_report.md")
    """

    def __init__(
        self,
        gpu_engine: Any,
        benchmark_suite: Optional[Any] = None,
        auto_tuner: Optional[Any] = None,
    ) -> None:
        """初始化报告生成器

        Args:
            gpu_engine: GPU 碰撞引擎实例
            benchmark_suite: 基准测试套件（可选）
            auto_tuner: 自动调优器（可选）
        """
        self.gpu_engine = gpu_engine
        self.benchmark_suite = benchmark_suite
        self.auto_tuner = auto_tuner

        logger.info("性能报告生成器已初始化")

    def generate_report(self, config: Optional[ReportConfig] = None) -> str:
        """生成性能报告

        Args:
            config: 报告配置（可选）

        Returns:
            格式化的报告字符串
        """
        config = config or ReportConfig()

        if config.format == "markdown":
            return self._generate_markdown_report(config)
        elif config.format == "json":
            return self._generate_json_report(config)
        else:
            raise ValueError(f"不支持的报告格式: {config.format}")

    def _generate_markdown_report(self, config: ReportConfig) -> str:
        """生成 Markdown 格式报告

        Args:
            config: 报告配置

        Returns:
            Markdown 字符串
        """
        sections = []

        # 标题
        sections.append("# GPU 性能详细报告\n")
        sections.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        sections.append("---\n")

        # 1. 设备信息
        if config.include_device_info:
            sections.append(self._generate_device_info_section())

        # 2. 基准测试结果
        if config.include_benchmark_results and self.benchmark_suite:
            sections.append(self._generate_benchmark_section())

        # 3. 自动调优结果
        if config.include_tuning_results and self.auto_tuner:
            sections.append(self._generate_tuning_section())

        # 4. 历史性能趋势
        if config.include_history:
            sections.append(self._generate_history_section())

        # 5. 优化建议
        if config.include_recommendations:
            sections.append(self._generate_recommendations_section())

        # 6. 对比分析
        if config.include_comparison:
            sections.append(self._generate_comparison_section())

        # 页脚
        sections.append("---\n")
        sections.append("*报告由 BTC Collision Engine 自动生成*\n")

        return "\n".join(sections)

    def _generate_device_info_section(self) -> str:
        """生成设备信息章节"""
        lines = [
            "## 📱 GPU 设备信息\n",
        ]

        # 获取设备信息
        device_info = self._get_device_info()

        lines.append("| 属性 | 值 |")
        lines.append("|------|-----|")

        for key, value in device_info.items():
            lines.append(f"| {key} | {value} |")

        lines.append("")
        return "\n".join(lines)

    def _generate_benchmark_section(self) -> str:
        """生成基准测试章节"""
        lines = [
            "## 📊 基准测试结果\n",
        ]

        # 获取基准测试结果
        if self.benchmark_suite is not None and hasattr(self.benchmark_suite, "results") and self.benchmark_suite.results:
            lines.append(self.benchmark_suite.generate_report())
        else:
            lines.append("*暂无基准测试数据*\n")

        lines.append("")
        return "\n".join(lines)

    def _generate_tuning_section(self) -> str:
        """生成自动调优章节"""
        lines = [
            "## 🔧 自动调优结果\n",
        ]

        if self.auto_tuner:
            lines.append(self.auto_tuner.get_tuning_report())
        else:
            lines.append("*暂无调优数据*\n")

        lines.append("")
        return "\n".join(lines)

    def _generate_history_section(self) -> str:
        """生成历史性能章节"""
        lines = [
            "## 📈 历史性能趋势\n",
        ]

        # 如果有调优器，显示历史记录
        if self.auto_tuner and self.auto_tuner.performance_history:
            history = self.auto_tuner.performance_history

            lines.append("| 时间 | Batch Size | 吞吐量 (keys/sec) | 执行时间 (ms) |")
            lines.append("|------|-----------|------------------|--------------|")

            # 显示最近 20 条记录
            recent = history[-20:]
            for record in recent:
                timestamp = datetime.fromtimestamp(record.timestamp).strftime("%H:%M:%S")
                lines.append(
                    f"| {timestamp} | {record.batch_size:,} | "
                    f"{record.throughput:,.0f} | {record.execution_time_ms:.0f} |"
                )
        else:
            lines.append("*暂无历史数据*\n")

        lines.append("")
        return "\n".join(lines)

    def _generate_recommendations_section(self) -> str:
        """生成优化建议章节"""
        lines = [
            "## 💡 优化建议\n",
        ]

        recommendations = self._generate_recommendations()

        if recommendations:
            for i, rec in enumerate(recommendations, 1):  # type: ignore[arg-type]
                lines.append(f"{i}. {rec}")
        else:
            lines.append("当前配置已优化，暂无额外建议。\n")

        lines.append("")
        return "\n".join(lines)

    def _generate_comparison_section(self) -> str:
        """生成对比分析章节"""
        lines = [
            "## 🔄 性能对比\n",
        ]

        # 获取当前设备性能
        current_performance = self._get_current_performance()

        # 典型 GPU 性能数据（来自调研）
        reference_gpus = {
            "NVIDIA RTX 3060": {"throughput": 850000, "batch_size": 2097152},
            "NVIDIA RTX 3080": {"throughput": 1200000, "batch_size": 4194304},
            "AMD RX 6600 XT": {"throughput": 620000, "batch_size": 1048576},
            "Intel Arc A750": {"throughput": 380000, "batch_size": 262144},
            "Intel Arc A770": {"throughput": 520000, "batch_size": 524288},
        }

        lines.append("| GPU 型号 | 最佳吞吐量 | 最佳 Batch Size | 相对性能 |")
        lines.append("|---------|-----------|----------------|---------|")

        current_throughput = current_performance.get("throughput", 0)
        current_device = self._get_device_info().get("name", "Current")

        for gpu_name, perf in reference_gpus.items():
            relative = (
                (current_throughput / perf["throughput"] * 100) if perf["throughput"] > 0 else 0
            )

            marker = " ← 当前" if gpu_name == current_device else ""
            lines.append(
                f"| {gpu_name}{marker} | {perf['throughput']:,}/s | "
                f"{perf['batch_size']:,} | {relative:.1f}% |"
            )

        lines.append("")
        return "\n".join(lines)

    def _generate_json_report(self, config: ReportConfig) -> str:
        """生成 JSON 格式报告

        Args:
            config: 报告配置

        Returns:
            JSON 字符串
        """
        report_data = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "generator": "BTC Collision Engine Performance Reporter",
                "version": "1.0",
            },
            "device_info": self._get_device_info() if config.include_device_info else None,
            "benchmark_results": None,
            "tuning_results": None,
            "performance_history": None,
            "recommendations": (
                self._generate_recommendations() if config.include_recommendations else None
            ),
        }

        # 添加基准测试结果
        if config.include_benchmark_results and self.benchmark_suite:
            if hasattr(self.benchmark_suite, "results"):
                report_data["benchmark_results"] = [
                    {
                        "test_name": r.test_name,
                        "test_type": r.test_type.value,
                        "throughput": r.throughput,
                        "duration_ms": r.duration_ms,
                        "parameters": r.parameters,
                    }
                    for r in self.benchmark_suite.results  # type: ignore[union-attr]
                ]

        # 添加调优结果
        if config.include_tuning_results and self.auto_tuner:
            report_data["tuning_results"] = {
                "best_config": self.auto_tuner.best_config,
                "best_throughput": self.auto_tuner.best_throughput,
                "tuning_cycles": self.auto_tuner.total_tuning_cycles,
            }

        # 添加历史数据
        if config.include_history and self.auto_tuner:
            report_data["performance_history"] = [
                {
                    "batch_size": r.batch_size,
                    "throughput": r.throughput,
                    "execution_time_ms": r.execution_time_ms,
                    "timestamp": r.timestamp,
                }
                for r in self.auto_tuner.performance_history[-50:]  # 最近 50 条
            ]

        return fast_dumps(report_data, indent=2, ensure_ascii=False)

    def save_report(self, report: str, filepath: str) -> None:
        """保存报告到文件

        Args:
            report: 报告内容
            filepath: 文件路径
        """
        # 确保目录存在
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)

        logger.info(f"性能报告已保存到: {filepath}")

    def _get_device_info(self) -> Dict:
        """获取设备信息"""
        if hasattr(self.gpu_engine, "_gpu_device") and self.gpu_engine._gpu_device:
            device = self.gpu_engine._gpu_device
            return {
                "设备名称": device.device_info.get("name", "Unknown"),
                "厂商": device.device_info.get("vendor", "Unknown"),
                "平台": device.device_info.get("platform", "Unknown"),
                "全局显存": f"{device.device_info.get('global_mem_size', 0) / 1024**3:.1f} GB",
                "计算单元": device.device_info.get("max_compute_units", "Unknown"),
                "驱动版本": getattr(device, "driver_version", "Unknown"),
                "OpenCL 版本": (
                    "3.0" if "Intel" in str(device.device_info.get("vendor", "")) else "Unknown"
                ),
            }
        return {}

    def _get_current_performance(self) -> Dict:
        """获取当前性能数据"""
        if self.auto_tuner and self.auto_tuner.best_config:
            return {
                "throughput": self.auto_tuner.best_config.get("throughput", 0),
                "batch_size": self.auto_tuner.best_config.get("batch_size", 0),
            }
        return {"throughput": 0, "batch_size": 0}

    def _generate_recommendations(self) -> List[str]:
        """生成优化建议"""
        recommendations = []

        # 获取当前配置
        device_info = self._get_device_info()
        vendor = device_info.get("厂商", "")
        current_perf = self._get_current_performance()

        # 厂商特定建议
        if "Intel" in vendor:
            recommendations.append(
                "Intel Arc GPU: 确保已启用 uint32 workaround 避免 global char* hang bug"
            )
            recommendations.append(
                "Intel Arc GPU: 建议使用保守的 batch_size (≤524,288) 以确保稳定性"
            )
            recommendations.append("Intel Arc GPU: 保持驱动版本 ≥ 31.0.101.4500")

        # 性能建议
        if current_perf.get("throughput", 0) < 100000:
            recommendations.append("吞吐量较低，建议运行自动调优以找到最优 batch_size")

        # 显存建议
        mem_size = device_info.get("全局显存", "0 GB")
        if "GB" in mem_size:
            try:
                mem_gb = float(mem_size.split()[0])
                if mem_gb >= 16:
                    recommendations.append("显存充足 (≥16GB)，可以尝试更大的 batch_size 提升吞吐量")
                elif mem_gb < 4:
                    recommendations.append(
                        "显存较小 (<4GB)，建议使用较小的 batch_size 避免显存不足"
                    )
            except (KeyError, TypeError, ValueError) as e:
                logger.debug(f"获取GPU显存信息失败: {e}")

        # 通用建议
        recommendations.append("定期运行基准测试以监控性能变化")
        recommendations.append("保持 GPU 驱动为最新版本")

        return recommendations
