"""智能批次大小优化器

根据GPU性能、内存使用和系统负载动态调整批次大小，提高性能和稳定性。

功能特点：
- 基于历史性能数据自动调整批次大小
- 考虑GPU显存使用情况
- 响应系统负载变化
- 支持不同GPU厂商的特性
- 自适应学习机制
"""

import threading
import time

# P3-5: 统一日志获取
from ..utils import get_configured_logger

logger = get_configured_logger("BatchSizeOptimizer")


class SmartBatchSizeOptimizer:
    """智能批次大小优化器

    根据GPU性能、内存使用和系统负载动态调整批次大小。
    """

    def __init__(
        self,
        initial_batch_size: int,
        min_batch_size: int = 1024,
        max_batch_size: int = 1048576,
        gpu_model: str = "default",
    ) -> None:
        """
        初始化智能批次大小优化器

        Args:
            initial_batch_size: 初始批次大小
            min_batch_size: 最小批次大小
            max_batch_size: 最大批次大小
            gpu_model: GPU型号标识
        """
        # GPU型号特定配置
        self._gpu_model = gpu_model

        # 根据GPU型号调整默认值
        gpu_config = self._get_gpu_config(gpu_model)

        # 使用GPU特定配置或默认值
        self._initial_batch_size: int = gpu_config.get("initial_batch_size", initial_batch_size)
        self._min_batch_size: int = gpu_config.get("min_batch_size", min_batch_size)
        self._max_batch_size: int = gpu_config.get("max_batch_size", max_batch_size)

        # 性能历史数据
        self._performance_history: list[dict] = []
        # 内存使用历史
        self._memory_history: list[dict] = []
        # 系统负载历史
        self._load_history: list[dict] = []

        # 调整参数
        self._adjustment_interval = 20  # 20批次调整一次，减少调整频率
        self._history_window = 30  # 考虑最近30次性能数据，增加数据量
        self._performance_threshold = 0.15  # 性能变化阈值，增加阈值，减少调整频率
        self._adjustment_counter = 0  # 调整计数器，用于控制调整频率

        # 锁
        self._lock = threading.Lock()

        # 当前批次大小
        self._current_batch_size: int = self._initial_batch_size

        logger.info(
            f"智能批次大小优化器初始化: GPU型号={gpu_model}, 初始批次={
                self._initial_batch_size
            }, 范围={self._min_batch_size}-{self._max_batch_size}"
        )

    def _get_gpu_config(self, gpu_model: str) -> dict:
        """
        获取GPU特定配置

        Args:
            gpu_model: GPU型号标识

        Returns:
            GPU配置字典
        """
        gpu_configs = {
            "1660": {
                "initial_batch_size": 131072,
                "min_batch_size": 16384,
                "max_batch_size": 524288,
            },
            "rtx40": {
                "initial_batch_size": 524288,
                "min_batch_size": 32768,
                "max_batch_size": 2097152,
            },
            "rtx30": {
                "initial_batch_size": 262144,
                "min_batch_size": 32768,
                "max_batch_size": 1048576,
            },
            "rtx": {
                "initial_batch_size": 262144,
                "min_batch_size": 32768,
                "max_batch_size": 1048576,
            },
            "10": {
                "initial_batch_size": 131072,
                "min_batch_size": 16384,
                "max_batch_size": 524288,
            },
            "9": {
                "initial_batch_size": 65536,
                "min_batch_size": 8192,
                "max_batch_size": 262144,
            },
            "amd7000": {
                "initial_batch_size": 524288,
                "min_batch_size": 32768,
                "max_batch_size": 2097152,
            },
            "amd6000": {
                "initial_batch_size": 262144,
                "min_batch_size": 32768,
                "max_batch_size": 1048576,
            },
            "amd": {
                "initial_batch_size": 262144,
                "min_batch_size": 32768,
                "max_batch_size": 1048576,
            },
            "intel": {
                "initial_batch_size": 4194304,  # 提高初始批次大小到400万
                "min_batch_size": 262144,  # 提高最小批次大小到256K
                "max_batch_size": 16777216,  # 匹配gpu_profiles.json的配置（1600万）
            },
            "default": {
                "initial_batch_size": 65536,
                "min_batch_size": 8192,
                "max_batch_size": 262144,
            },
        }
        return gpu_configs.get(gpu_model, gpu_configs.get("default", {}))

    def record_performance(
        self, batch_size: int, execution_time_ms: float, throughput: float
    ) -> None:
        """
        记录性能数据

        Args:
            batch_size: 批次大小
            execution_time_ms: 执行时间(毫秒)
            throughput: 吞吐量(keys/s)
        """
        with self._lock:
            self._performance_history.append(
                {
                    "timestamp": time.time(),
                    "batch_size": batch_size,
                    "execution_time_ms": execution_time_ms,
                    "throughput": throughput,
                }
            )

            # 保持历史数据大小
            if len(self._performance_history) > self._history_window:
                self._performance_history = self._performance_history[-self._history_window :]

    def record_memory_usage(self, used_memory_mb: float, total_memory_mb: float) -> None:
        """
        记录内存使用情况

        Args:
            used_memory_mb: 已使用内存(MB)
            total_memory_mb: 总内存(MB)
        """
        with self._lock:
            self._memory_history.append(
                {
                    "timestamp": time.time(),
                    "used_memory_mb": used_memory_mb,
                    "total_memory_mb": total_memory_mb,
                    "usage_ratio": used_memory_mb / total_memory_mb if total_memory_mb > 0 else 0,
                }
            )

            # 保持历史数据大小
            if len(self._memory_history) > self._history_window:
                self._memory_history = self._memory_history[-self._history_window :]

    def record_system_load(self, cpu_load: float, gpu_load: float) -> None:
        """
        记录系统负载

        Args:
            cpu_load: CPU负载(0-1)
            gpu_load: GPU负载(0-1)
        """
        with self._lock:
            self._load_history.append(
                {"timestamp": time.time(), "cpu_load": cpu_load, "gpu_load": gpu_load}
            )

            # 保持历史数据大小
            if len(self._load_history) > self._history_window:
                self._load_history = self._load_history[-self._history_window :]

    def get_optimal_batch_size(self) -> int:
        """
        获取优化后的批次大小

        Returns:
            优化后的批次大小
        """
        with self._lock:
            # 如果历史数据不足，返回当前批次大小
            if len(self._performance_history) < 10:  # 增加历史数据要求
                return self._current_batch_size

            # 增加调整计数器
            self._adjustment_counter += 1

            # 只有当计数器达到调整间隔时才进行调整
            if self._adjustment_counter < self._adjustment_interval:
                return self._current_batch_size

            # 重置调整计数器
            self._adjustment_counter = 0

            # 分析性能趋势
            optimal_size = self._analyze_performance_trend()

            # 考虑内存使用
            optimal_size = self._adjust_for_memory(optimal_size)

            # 考虑系统负载
            optimal_size = self._adjust_for_system_load(optimal_size)

            # 限制在合理范围内
            optimal_size = max(self._min_batch_size, min(optimal_size, self._max_batch_size))

            # 对齐到2的幂
            optimal_size = self._align_to_power_of_two(optimal_size)

            # 更新当前批次大小
            if optimal_size != self._current_batch_size:
                # 平滑过渡：如果调整幅度太大，逐步调整
                if abs(optimal_size - self._current_batch_size) > self._current_batch_size:
                    # 只调整到当前批次大小的两倍或一半
                    if optimal_size > self._current_batch_size:
                        new_size = self._current_batch_size * 2
                    else:
                        new_size = self._current_batch_size // 2
                    # 确保在合理范围内
                    new_size = max(self._min_batch_size, min(new_size, self._max_batch_size))
                    logger.info(
                        f"批次大小调整: {self._current_batch_size} -> {new_size} (平滑过渡)"
                    )
                    self._current_batch_size = new_size
                else:
                    logger.info(f"批次大小调整: {self._current_batch_size} -> {optimal_size}")
                    self._current_batch_size = optimal_size

            return self._current_batch_size

    def _analyze_performance_trend(self) -> int:
        """
        分析性能趋势，确定最优批次大小

        Returns:
            推荐的批次大小
        """
        # 计算不同批次大小的平均吞吐量
        batch_performance: dict[int, list[float]] = {}
        for record in self._performance_history:
            batch_size = record["batch_size"]
            if batch_size not in batch_performance:
                batch_performance[batch_size] = []
            batch_performance[batch_size].append(record["throughput"])

        # 计算每个批次大小的平均吞吐量和标准差
        avg_throughput = {}
        std_throughput = {}
        for batch_size, throughputs in batch_performance.items():
            avg_throughput[batch_size] = sum(throughputs) / len(throughputs)
            # 计算标准差，衡量性能稳定性
            variance = sum((t - avg_throughput[batch_size]) ** 2 for t in throughputs) / len(
                throughputs
            )
            std_throughput[batch_size] = variance**0.5

        # 找出吞吐量最高且性能稳定的批次大小
        # 综合考虑平均吞吐量和标准差，优先选择吞吐量高且稳定的批次大小
        best_batch_size = None
        best_score = -1
        for batch_size in avg_throughput:
            # 计算综合得分：吞吐量越高，标准差越小，得分越高
            stability_factor = 1.0 / (1.0 + std_throughput[batch_size] / avg_throughput[batch_size])
            score = avg_throughput[batch_size] * stability_factor
            if score > best_score:
                best_score = score
                best_batch_size = batch_size

        if best_batch_size is None:
            return self._current_batch_size

        # 分析趋势
        recent_performance = self._performance_history[-10:]  # 增加最近数据量
        recent_throughputs = [r["throughput"] for r in recent_performance]
        recent_batch_sizes = [r["batch_size"] for r in recent_performance]

        # 计算趋势
        if len(recent_throughputs) >= 5:  # 增加数据点要求
            # 计算最近的趋势
            trend = recent_throughputs[-1] / recent_throughputs[0]

            if trend > 1.15:  # 性能提升，增加阈值
                # 如果最近批次大小在增加且性能提升，继续增加
                if recent_batch_sizes[-1] > recent_batch_sizes[0]:
                    return best_batch_size * 2
            elif trend < 0.85:  # 性能下降，增加阈值
                # 如果最近批次大小在增加且性能下降，减小批次大小
                if recent_batch_sizes[-1] > recent_batch_sizes[0]:
                    return best_batch_size // 2

        return best_batch_size

    def _adjust_for_memory(self, batch_size: int) -> int:
        """
        根据内存使用情况调整批次大小

        Args:
            batch_size: 基础批次大小

        Returns:
            调整后的批次大小
        """
        if not self._memory_history:
            return batch_size

        # 获取最近的内存使用情况
        recent_memory = self._memory_history[-10:]  # 增加最近数据量
        avg_usage_ratio = sum(r["usage_ratio"] for r in recent_memory) / len(recent_memory)

        # 如果内存使用超过85%，减小批次大小
        if avg_usage_ratio > 0.85:
            return batch_size // 2
        # 如果内存使用低于40%，可以考虑增加批次大小
        elif avg_usage_ratio < 0.4:
            return batch_size * 2

        return batch_size

    def _adjust_for_system_load(self, batch_size: int) -> int:
        """
        根据系统负载调整批次大小

        Args:
            batch_size: 基础批次大小

        Returns:
            调整后的批次大小
        """
        if not self._load_history:
            return batch_size

        # 获取最近的系统负载
        recent_load = self._load_history[-10:]  # 增加最近数据量
        avg_cpu_load = sum(r["cpu_load"] for r in recent_load) / len(recent_load)
        avg_gpu_load = sum(r["gpu_load"] for r in recent_load) / len(recent_load)

        # 如果CPU负载超过85%，减小批次大小
        if avg_cpu_load > 0.85 or avg_gpu_load > 0.95:
            return batch_size // 2
        # 如果GPU负载低于40%，可以考虑增加批次大小
        elif avg_gpu_load < 0.4:
            return batch_size * 2

        return batch_size

    def _align_to_power_of_two(self, size: int) -> int:
        """
        将大小对齐到最近的2的幂

        Args:
            size: 原始大小

        Returns:
            对齐后的大小
        """
        if size <= 0:
            return self._min_batch_size

        # 计算最接近的2的幂
        power = size.bit_length() - 1
        lower = 1 << power
        upper = 1 << (power + 1)

        if size - lower < upper - size:
            return lower
        else:
            return upper

    def get_stats(self) -> dict:
        """
        获取优化器统计信息

        Returns:
            统计信息字典
        """
        with self._lock:
            stats = {
                "current_batch_size": self._current_batch_size,
                "initial_batch_size": self._initial_batch_size,
                "performance_history_count": len(self._performance_history),
                "memory_history_count": len(self._memory_history),
                "load_history_count": len(self._load_history),
                "min_batch_size": self._min_batch_size,
                "max_batch_size": self._max_batch_size,
            }

            # 计算平均性能
            if self._performance_history:
                avg_throughput = sum(r["throughput"] for r in self._performance_history) / len(
                    self._performance_history
                )
                stats["avg_throughput"] = avg_throughput

            # 计算平均内存使用
            if self._memory_history:
                avg_usage = sum(r["usage_ratio"] for r in self._memory_history) / len(
                    self._memory_history
                )
                stats["avg_memory_usage"] = avg_usage

            return stats

    def reset(self) -> None:
        """
        重置优化器状态
        """
        with self._lock:
            self._performance_history.clear()
            self._memory_history.clear()
            self._load_history.clear()
            self._current_batch_size = self._initial_batch_size
            logger.info("智能批次大小优化器已重置")


# 全局智能批次大小优化器实例
global_batch_optimizer = None
global_optimizer_lock = threading.Lock()


def get_batch_size_optimizer(
    initial_batch_size: int = 1048576, gpu_model: str = "default"
) -> SmartBatchSizeOptimizer:
    """
    获取全局智能批次大小优化器实例

    Args:
        initial_batch_size: 初始批次大小
        gpu_model: GPU型号标识

    Returns:
        SmartBatchSizeOptimizer实例
    """
    global global_batch_optimizer

    with global_optimizer_lock:
        if global_batch_optimizer is None:
            global_batch_optimizer = SmartBatchSizeOptimizer(
                initial_batch_size, gpu_model=gpu_model
            )

    return global_batch_optimizer


def reset_batch_size_optimizer() -> None:
    """
    重置全局智能批次大小优化器
    """
    global global_batch_optimizer

    with global_optimizer_lock:
        if global_batch_optimizer is not None:
            global_batch_optimizer.reset()
        global_batch_optimizer = None
