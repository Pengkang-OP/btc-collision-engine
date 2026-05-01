"""GPU 性能优化管道

协调 auto_tuner、benchmark_suite、performance_reporter 的初始化与调用，
从 GPUCollisionEngine 中解耦性能优化相关逻辑。
"""

import logging

# P3-5: 统一日志获取
from ..utils import get_configured_logger
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..gpu.auto_tuner import GPUAutoTuner
    from ..gpu.benchmark_suite import GPUBenchmarkSuite
    from ..gpu.performance_reporter import PerformanceReportGenerator

logger = get_configured_logger("GPUOptimizationPipeline")


class PerformanceOptimizationPipeline:
    """性能优化管道

    协调调优器、基准测试套件、性能报告生成器的生命周期与调用。
    可独立测试，通过委托集成到 GPUCollisionEngine。

    Attributes:
        auto_tuner:          自动调优器实例
        benchmark_suite:     基准测试套件实例
        performance_reporter: 性能报告生成器实例
    """

    def __init__(
        self,
        auto_tuner: Optional["GPUAutoTuner"] = None,
        benchmark_suite: Optional["GPUBenchmarkSuite"] = None,
        reporter: Optional["PerformanceReportGenerator"] = None,
        logger_instance: Optional[logging.Logger] = None,
    ) -> None:
        """初始化性能优化管道

        Args:
            auto_tuner:       GPUAutoTuner 实例（可选）
            benchmark_suite:  GPUBenchmarkSuite 实例（可选）
            reporter:         PerformanceReportGenerator 实例（可选）
            logger_instance:  日志记录器（默认使用模块级 logger）
        """
        self.auto_tuner: Optional[GPUAutoTuner] = auto_tuner
        self.benchmark_suite: Optional[GPUBenchmarkSuite] = benchmark_suite
        self.performance_reporter: Optional[PerformanceReportGenerator] = reporter
        self._logger = logger_instance or logger

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def initialize(self, device_info: Dict[str, Any]) -> None:
        """根据设备信息进行管道级初始化（留作扩展点）

        Args:
            device_info: GPU 设备信息字典
        """
        self._logger.debug(
            "PerformanceOptimizationPipeline.initialize called: "
            f"device={device_info.get('name', 'unknown')}"
        )

    # ------------------------------------------------------------------
    # 批处理大小优化
    # ------------------------------------------------------------------

    def optimize_batch_size(self, current_size: int, metrics: Dict[str, Any]) -> int:
        """根据性能指标推荐最优 batch_size

        委托给 auto_tuner（若存在），否则返回当前大小。

        Args:
            current_size: 当前 batch_size
            metrics:      最新性能指标字典（至少包含 keys_per_second 等字段）

        Returns:
            推荐的 batch_size（整数）
        """
        if self.auto_tuner is None:
            return current_size

        try:
            tuner: Any = self.auto_tuner
            suggestion = tuner.suggest_batch_size(current_size, metrics)
            return int(suggestion) if suggestion else current_size
        except (AttributeError, TypeError, ValueError) as exc:
            self._logger.debug(f"optimize_batch_size 委托失败，保持原值: {exc}")
            return current_size

    # ------------------------------------------------------------------
    # 基准测试
    # ------------------------------------------------------------------

    def run_benchmark(self, iterations: int = 5) -> Dict[str, Any]:
        """运行 GPU 性能基准测试

        Args:
            iterations: 迭代次数

        Returns:
            基准测试结果字典；若套件未初始化返回空字典
        """
        if not self.benchmark_suite:
            self._logger.warning("基准测试套件未初始化")
            return {}

        self._logger.info("\n" + "=" * 60)
        self._logger.info("开始运行 GPU 性能基准测试")
        self._logger.info("=" * 60)

        suite: Any = self.benchmark_suite
        results = suite.run_all_benchmarks(iterations)
        summary = suite.get_summary(results)
        self._logger.info("\n" + summary)
        return results

    # ------------------------------------------------------------------
    # 自动调优
    # ------------------------------------------------------------------

    def start_auto_tuning(
        self,
        max_iterations: int = 30,
        on_new_batch_size: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """启动自动调优

        Args:
            max_iterations:      最大迭代次数
            on_new_batch_size:   新 batch_size 建议回调 callable(new_size)

        Returns:
            调优结果字典；若调优器未初始化返回空字典
        """
        if not self.auto_tuner:
            self._logger.warning("自动调优器未初始化")
            return {}

        self._logger.info("\n" + "=" * 60)
        self._logger.info("开始自动调优")
        self._logger.info("=" * 60)

        tuner: Any = self.auto_tuner
        results = tuner.start_tuning(
            max_iterations=max_iterations,
            callback=on_new_batch_size,
        )

        optimal_size = results.get("optimal_batch_size")
        self._logger.info(
            f"调优完成！最优 batch_size: {optimal_size}, "
            f"预期吞吐量: {results.get('expected_throughput', 0):,.0f} keys/s"
        )
        return results

    # ------------------------------------------------------------------
    # 报告生成
    # ------------------------------------------------------------------

    def generate_report(
        self,
        include_benchmarks: bool = True,
        include_tuning: bool = True,
        include_history: bool = True,
        include_recommendations: bool = True,
        include_comparison: bool = False,
        output_dir: Optional[str] = None,
    ) -> str:
        """生成性能报告

        Args:
            include_benchmarks:     包含基准测试结果
            include_tuning:         包含调优结果
            include_history:        包含历史趋势
            include_recommendations: 包含优化建议
            include_comparison:     包含历史对比
            output_dir:             输出目录

        Returns:
            报告文件路径；若报告器未初始化返回空字符串
        """
        if not self.performance_reporter:
            self._logger.warning("性能报告生成器未初始化")
            return ""

        # 延迟导入避免循环依赖
        try:
            from ..gpu.performance_reporter import ReportConfig
        except ImportError:
            self._logger.error("无法导入 ReportConfig")
            return ""

        self._logger.info("\n" + "=" * 60)
        self._logger.info("生成 GPU 性能报告")
        self._logger.info("=" * 60)

        reporter: Any = self.performance_reporter
        report_path = reporter.generate_report(
            config=ReportConfig(
                include_device_info=True,
                include_benchmark_results=include_benchmarks,
                include_tuning_results=include_tuning,
                include_history=include_history,
                include_recommendations=include_recommendations,
                include_comparison=include_comparison,
            ),
            output_dir=output_dir,
        )
        return report_path
