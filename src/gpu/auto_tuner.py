"""GPU 自动调优器

基于性能监控和基准测试数据，自动优化 GPU 碰撞引擎参数：
1. 自动调整 batch_size
2. 优化工作负载分配
3. 动态调整执行策略
4. 性能瓶颈识别和优化

核心策略：
- 探索阶段：测试不同参数组合
- 利用阶段：使用最优参数
- 持续监控：检测性能变化并重新调优
"""

import statistics
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..utils import get_configured_logger

logger = get_configured_logger("GPUAutoTuner")


class TuningPhase(Enum):
    """调优阶段"""

    EXPLORATION = "exploration"  # 探索阶段：测试不同参数
    EXPLOITATION = "exploitation"  # 利用阶段：使用最优参数
    MONITORING = "monitoring"  # 监控阶段：持续观察


@dataclass
class TuningConfig:
    """调优配置"""

    # batch_size 范围
    min_batch_size: int = 1024
    max_batch_size: int = 10485760  # 10M

    # 探索策略
    exploration_iterations: int = 5  # 每个参数测试次数
    exploration_batch_sizes: list[int] = field(
        default_factory=lambda: [10000, 25000, 50000, 100000, 250000, 500000, 1000000]
    )

    # 调整阈值
    performance_improvement_threshold: float = 0.05  # 5% 改进才调整
    degradation_threshold: float = 0.10  # 10% 退化触发重新调优

    # 监控
    monitoring_interval_sec: float = 60.0  # 监控间隔
    re_tuning_interval_sec: float = 3600.0  # 重新调优间隔（1小时）


@dataclass
class PerformanceRecord:
    """性能记录"""

    batch_size: int
    throughput: float  # keys/sec
    execution_time_ms: float
    timestamp: float
    error_rate: float = 0.0


class GPUAutoTuner:
    """GPU 自动调优器

    使用示例:
        >>> tuner = GPUAutoTuner(gpu_engine)
        >>> # 开始调优
        >>> tuner.start_tuning()
        >>> # 获取最优配置
        >>> optimal = tuner.get_optimal_config()
        >>> print(f"最优 batch_size: {optimal['batch_size']}")
    """

    def __init__(self, gpu_engine: Any, config: TuningConfig | None = None) -> None:
        """初始化自动调优器

        Args:
            gpu_engine: GPU 碰撞引擎实例
            config: 调优配置（可选）
        """
        self.gpu_engine = gpu_engine
        self.config = config or TuningConfig()

        # 状态
        self.phase = TuningPhase.EXPLORATION
        self.is_tuning = False

        # 性能记录
        self.performance_history: list[PerformanceRecord] = []
        self.best_config: dict | None = None
        self.best_throughput: float = 0.0

        # 时间跟踪
        self.last_tuning_time: float = 0
        self.last_monitoring_time: float = 0

        # 统计
        self.total_tuning_cycles = 0
        self.total_adjustments = 0

        logger.info("GPU 自动调优器已初始化")

    def start_tuning(self) -> dict:
        """开始自动调优

        Returns:
            最优配置
        """
        logger.info("=" * 60)
        logger.info("🔧 开始 GPU 自动调优")
        logger.info("=" * 60)

        self.is_tuning = True
        self.phase = TuningPhase.EXPLORATION

        # 探索阶段
        optimal = self._explore_optimal_batch_size()

        # 切换到利用阶段
        self.phase = TuningPhase.EXPLOITATION
        self.is_tuning = False
        self.last_tuning_time = time.time()

        logger.info("=" * 60)
        logger.info(f"✅ 自动调优完成: batch_size={optimal.get('batch_size')}")
        logger.info("=" * 60)

        return optimal

    def _explore_optimal_batch_size(self) -> dict:
        """探索最优 batch_size

        Returns:
            最优配置
        """
        logger.info("📊 探索阶段：测试不同 batch_size")

        results = []

        for batch_size in self.config.exploration_batch_sizes:
            # 检查是否在有效范围内
            if batch_size < self.config.min_batch_size or batch_size > self.config.max_batch_size:
                logger.debug(f"  跳过 batch_size={batch_size}（超出范围）")
                continue

            # 测试这个 batch_size
            logger.info(f"  测试 batch_size={batch_size:,}...")

            try:
                performance = self._test_batch_size(batch_size)

                if performance:
                    results.append(performance)
                    logger.info(
                        f"    ✅ 吞吐量: {performance['throughput']:,.0f} keys/sec, "
                        f"耗时: {performance['avg_time_ms']:.0f}ms"
                    )
                else:
                    logger.warning("    ❌ 测试失败")

            except Exception as e:
                logger.error(f"    ❌ 测试异常: {e}")

        # 选择最优配置
        if results:
            best = max(results, key=lambda r: r["throughput"])

            self.best_config = {
                "batch_size": best["batch_size"],
                "throughput": best["throughput"],
                "avg_time_ms": best["avg_time_ms"],
            }
            self.best_throughput = best["throughput"]

            _bs = best['batch_size']
            _tp = best['throughput']
            logger.info(
                f"\n🏆 最优配置: batch_size={_bs:,}, 吞吐量={_tp:,.0f} keys/sec"
            )

            return self.best_config
        else:
            logger.warning("未找到有效配置，使用默认值")
            return {"batch_size": 100000, "throughput": 0}

    def _test_batch_size(self, batch_size: int) -> dict | None:
        """测试特定 batch_size 的性能

        Args:
            batch_size: 批次大小

        Returns:
            性能数据
        """
        import os

        exec_times = []
        iterations = self.config.exploration_iterations

        for i in range(iterations):
            # 准备测试数据（PRNG模式：仅需 32 字节随机种子）
            seed = os.urandom(32)

            start_time = time.time()

            try:
                # 执行批次
                if hasattr(self.gpu_engine, "_gpu_kernel"):
                    matches = self.gpu_engine._gpu_kernel.run_batch(  # noqa: F841
                        seed=seed,
                        num_keys=batch_size,
                    )

                duration_ms = (time.time() - start_time) * 1000
                exec_times.append(duration_ms)

            except Exception as e:
                logger.debug(f"  迭代 {i + 1} 失败: {e}")
                continue

        if not exec_times:
            return None

        # 计算统计
        avg_time = statistics.mean(exec_times)
        throughput = (batch_size / avg_time * 1000) if avg_time > 0 else 0

        # 记录性能
        record = PerformanceRecord(
            batch_size=batch_size,
            throughput=throughput,
            execution_time_ms=avg_time,
            timestamp=time.time(),
        )
        self.performance_history.append(record)

        return {
            "batch_size": batch_size,
            "throughput": throughput,
            "avg_time_ms": avg_time,
            "min_ms": min(exec_times),
            "max_ms": max(exec_times),
        }

    def get_optimal_config(self) -> dict:
        """获取最优配置

        Returns:
            最优配置字典
        """
        if self.best_config:
            return self.best_config

        # 如果没有调优过，执行一次
        return self.start_tuning()

    def should_re_tune(self) -> bool:
        """判断是否应该重新调优

        Returns:
            如果需要重新调优返回 True
        """
        now = time.time()

        # 检查时间间隔
        if now - self.last_tuning_time < self.config.re_tuning_interval_sec:
            return False

        # 检查性能是否退化
        if self._check_performance_degradation():
            logger.info("检测到性能退化，建议重新调优")
            return True

        return False

    def monitor_performance(self) -> dict:
        """监控当前性能

        Returns:
            监控结果
        """
        now = time.time()

        # 检查是否需要监控
        if now - self.last_monitoring_time < self.config.monitoring_interval_sec:
            return {"status": "too_soon"}

        self.last_monitoring_time = now

        # 获取当前性能
        current_throughput = self._measure_current_throughput()

        # 检查是否退化
        degraded = False
        if self.best_throughput > 0:
            degradation_ratio = (self.best_throughput - current_throughput) / self.best_throughput
            if degradation_ratio > self.config.degradation_threshold:
                degraded = True
                logger.warning(
                    f"性能退化: {current_throughput:,.0f} vs "
                    f"最优 {self.best_throughput:,.0f} "
                    f"({degradation_ratio * 100:.1f}%)"
                )

        return {
            "status": "ok",
            "current_throughput": current_throughput,
            "best_throughput": self.best_throughput,
            "degraded": degraded,
            "timestamp": now,
        }

    def _measure_current_throughput(self) -> float:
        """测量当前吞吐量

        Returns:
            当前吞吐量（keys/sec）
        """
        import os

        batch_size = self.best_config.get("batch_size", 100000) if self.best_config else 100000

        try:
            seed = os.urandom(32)

            start_time = time.time()

            if hasattr(self.gpu_engine, "_gpu_kernel"):
                self.gpu_engine._gpu_kernel.run_batch(
                    seed=seed,
                    num_keys=batch_size,
                )

            duration_ms = (time.time() - start_time) * 1000
            throughput = (batch_size / duration_ms * 1000) if duration_ms > 0 else 0

            return throughput

        except Exception as e:
            logger.error(f"测量吞吐量失败: {e}")
            return 0

    def _check_performance_degradation(self) -> bool:
        """检查性能退化

        Returns:
            如果退化返回 True
        """
        if not self.performance_history:
            return False

        # 获取最近的记录
        recent = self.performance_history[-10:]
        if len(recent) < 3:
            return False

        # 计算平均吞吐量
        recent_throughput = statistics.mean([r.throughput for r in recent])

        # 与最优对比
        if self.best_throughput > 0:
            degradation = (self.best_throughput - recent_throughput) / self.best_throughput
            return degradation > self.config.degradation_threshold

        return False

    def get_tuning_report(self) -> str:
        """生成调优报告

        Returns:
            格式化的报告字符串
        """
        report_lines = [
            "=" * 60,
            "🔧 GPU 自动调优报告",
            "=" * 60,
            f"调优阶段: {self.phase.value}",
            f"调优周期: {self.total_tuning_cycles}",
            f"调整次数: {self.total_adjustments}",
            "",
        ]

        if self.best_config:
            report_lines.append("最优配置:")
            report_lines.append(f"  batch_size: {self.best_config['batch_size']:,}")
            report_lines.append(f"  吞吐量: {self.best_config['throughput']:,.0f} keys/sec")
            report_lines.append(f"  平均时间: {self.best_config['avg_time_ms']:.0f}ms")
        else:
            report_lines.append("最优配置: 未调优")

        report_lines.append("")
        report_lines.append(f"性能历史记录: {len(self.performance_history)} 条")

        if self.performance_history:
            # 显示最近的记录
            recent = self.performance_history[-5:]
            report_lines.append("\n最近性能记录:")
            for record in recent:
                report_lines.append(
                    f"  batch_size={record.batch_size:,}, "
                    f"throughput={record.throughput:,.0f}/s, "
                    f"time={record.execution_time_ms:.0f}ms"
                )

        report_lines.append("=" * 60)

        return "\n".join(report_lines)

    def reset(self) -> None:
        """重置调优器状态"""
        self.phase = TuningPhase.EXPLORATION
        self.is_tuning = False
        self.performance_history.clear()
        self.best_config = None
        self.best_throughput = 0.0
        self.last_tuning_time = 0
        self.total_tuning_cycles = 0
        self.total_adjustments = 0

        logger.info("GPU 自动调优器已重置")
