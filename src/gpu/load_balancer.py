"""GPU负载均衡器.

为多GPU环境提供智能的任务分配和负载均衡。
支持按性能分配和平均分配两种策略。

增强功能：
- 基于历史性能数据的动态负载重平衡
- 负载不均衡检测和自动调整
- 内存使用考虑
- 性能预测和自适应调整
- 细粒度负载调整
"""

import statistics
import time
from typing import Any, cast

# 统一日志获取
from ..utils import get_configured_logger

# 统一GPU评分
from .scorer import GPUDeviceScorer, get_gpu_scorer

logger = get_configured_logger("GPULoadBalancer")


class GPULoadBalancer:
    """GPU负载均衡器.

    根据GPU设备性能智能分配私钥搜索任务。

    负载分配策略:
    1. performance(按性能): 根据显存和计算单元分配权重
    2. equal(平均分配): 所有GPU平均分配任务

    使用示例:
        balancer = GPULoadBalancer(devices, strategy='performance')

        # 计算负载权重
        weights = balancer.calculate_weights()

        # 为GPU分配私钥范围
        start, end = balancer.assign_key_range(1000000, device_idx=0)
    """

    # 厂商性能系数已迁移到 GPUDeviceScorer (P3-11)

    __slots__ = (
        "_historical_performance",
        "_key_ranges",
        "_last_rebalance_time",
        "_load_history",
        "_memory_stats",
        "_performance_stats",
        "_scorer",
        "_weights",
        "devices",
        "memory_usage_threshold",
        "min_rebalance_threshold",
        "rebalance_interval",
        "strategy",
    )

    def __init__(
        self,
        devices: list[dict],
        strategy: str = "performance",
        rebalance_interval: int = 30,  # 减少重平衡间隔，提高响应速度
        min_rebalance_threshold: float = 0.05,  # 减少重平衡阈值，提高负载均衡的准确性
        memory_usage_threshold: float = 0.75,  # 减少内存使用阈值，避免内存不足
        scorer: GPUDeviceScorer | None = None,
    ) -> None:
        """初始化负载均衡器.

        Args:
            devices: GPU设备列表
            strategy: 负载策略 ('performance' 或 'equal')
            rebalance_interval: 动态重平衡间隔(秒)
            min_rebalance_threshold: 最小重平衡阈值(0.0-1.0)
            memory_usage_threshold: 内存使用阈值(0.0-1.0)
            scorer: GPU设备评分器，为None时使用全局单例

        """
        if not devices:
            raise ValueError("设备列表不能为空")

        self.devices = devices
        self.strategy = strategy
        self.rebalance_interval = rebalance_interval
        self.min_rebalance_threshold = min_rebalance_threshold
        self.memory_usage_threshold = memory_usage_threshold
        self._scorer = scorer or get_gpu_scorer()

        self._weights: dict[int, float] = {}
        self._key_ranges: dict[int, tuple[int, int]] = {}
        self._last_rebalance_time: float = time.time()
        self._performance_stats: dict[int, dict[str, Any]] = {}
        self._memory_stats: dict[int, dict[str, Any]] = {}
        self._historical_performance: dict[int, list[dict[str, Any]]] = {}
        self._load_history: dict[int, list[dict[str, Any]]] = {}

        # 计算初始权重
        self._calculate_initial_weights()

        _n = len(devices)
        _interval = rebalance_interval
        logger.info("GPU负载均衡器已初始化: 设备数=%s, 策略=%s, 重平衡间隔=%ss", _n, strategy, _interval)

    def _calculate_initial_weights(self) -> None:
        """计算初始负载权重."""
        if self.strategy == "equal":
            # 平均分配
            weight = 1.0 / len(self.devices)
            self._weights = {device["global_index"]: weight for device in self.devices}
        else:
            # 按性能分配
            self._weights = self._calculate_performance_weights()

        logger.info(f"初始负载权重: {self._weights}")

    def _calculate_performance_weights(self) -> dict[int, float]:
        """基于设备性能计算权重.

        委托给统一的 GPUDeviceScorer 计算归一化权重。

        Returns:
            设备索引 -> 权重映射 (总和为1.0)

        """
        return self._scorer.calculate_performance_weights(self.devices)

    def calculate_weights(self) -> dict[int, float]:
        """获取当前负载权重.

        Returns:
            设备索引 -> 权重映射

        """
        return self._weights.copy()

    def assign_key_range(
        self,
        total_keys: int,
        device_idx: int,
        key_offset: int = 0,
    ) -> tuple[int, int]:
        """为指定GPU分配私钥搜索范围.

        Args:
            total_keys: 总私钥数量
            device_idx: GPU设备索引
            key_offset: 私钥起始偏移量

        Returns:
            (start_key, end_key) 私钥范围

        """
        if device_idx not in self._weights:
            raise ValueError(f"设备索引 {device_idx} 不存在于负载均衡器中")

        weight = self._weights[device_idx]

        # 计算该GPU分配的私钥数量
        device_keys = int(total_keys * weight)

        # 计算范围
        start_key = key_offset + int(total_keys * self._get_cumulative_weight(device_idx))
        end_key = start_key + device_keys

        # 缓存范围
        self._key_ranges[device_idx] = (start_key, end_key)

        logger.debug(
            f"设备 {device_idx} 分配范围: [{start_key},{end_key}), "
            f"量={device_keys:,}, 权重={weight:.3f}",
        )

        return start_key, end_key

    def _get_cumulative_weight(self, device_idx: int) -> float:
        """获取设备的累积权重(用于计算偏移).

        Args:
            device_idx: 设备索引

        Returns:
            累积权重(0.0-1.0)

        """
        # 按设备索引排序
        sorted_indices = sorted(self._weights.keys())

        cumulative = 0.0
        for idx in sorted_indices:
            if idx == device_idx:
                break
            cumulative += self._weights[idx]

        return cumulative

    def assign_all_key_ranges(
        self,
        total_keys: int,
        key_offset: int = 0,
    ) -> dict[int, tuple[int, int]]:
        """为所有GPU分配私钥范围.

        Args:
            total_keys: 总私钥数量
            key_offset: 私钥起始偏移量

        Returns:
            设备索引 -> (start, end) 映射

        """
        ranges = {}
        current_offset = key_offset

        # 按权重排序,确保大权重GPU先分配
        sorted_devices = sorted(
            self.devices,
            key=lambda d: self._weights.get(d["global_index"], 0),
            reverse=True,
        )

        for device in sorted_devices:
            idx = device["global_index"]
            weight = self._weights[idx]
            device_keys = int(total_keys * weight)

            start_key = current_offset
            end_key = start_key + device_keys

            ranges[idx] = (start_key, end_key)
            self._key_ranges[idx] = (start_key, end_key)

            current_offset = end_key

            logger.debug(f"设备 {idx} 分配: [{start_key}, {end_key}), 数量={device_keys:,}")

        return ranges

    def record_performance(
        self,
        device_idx: int,
        throughput: float,
        error_rate: float = 0.0,
    ) -> None:
        """记录GPU实际性能.

        Args:
            device_idx: 设备索引
            throughput: 吞吐量(keys/s)
            error_rate: 错误率(0.0-1.0)

        """
        timestamp = time.time()

        # 记录当前性能
        self._performance_stats[device_idx] = {
            "throughput": throughput,
            "error_rate": error_rate,
            "timestamp": timestamp,
        }

        # 记录历史性能
        if device_idx not in self._historical_performance:
            self._historical_performance[device_idx] = []

        self._historical_performance[device_idx].append(
            {"throughput": throughput, "error_rate": error_rate, "timestamp": timestamp},
        )

        # 保持历史数据大小
        if len(self._historical_performance[device_idx]) > 50:
            self._historical_performance[device_idx] = self._historical_performance[device_idx][-50:]

    def record_memory_usage(
        self,
        device_idx: int,
        used_memory_mb: float,
        total_memory_mb: float,
    ) -> None:
        """记录GPU内存使用情况.

        Args:
            device_idx: 设备索引
            used_memory_mb: 已使用内存(MB)
            total_memory_mb: 总内存(MB)

        """
        usage_ratio = used_memory_mb / total_memory_mb if total_memory_mb > 0 else 0

        self._memory_stats[device_idx] = {
            "used_memory_mb": used_memory_mb,
            "total_memory_mb": total_memory_mb,
            "usage_ratio": usage_ratio,
            "timestamp": time.time(),
        }

    def should_rebalance(self) -> bool:
        """检查是否需要重新平衡负载.

        Returns:
            True表示需要重新平衡

        """
        now = time.time()
        elapsed = now - self._last_rebalance_time

        # 时间间隔检查
        if elapsed >= self.rebalance_interval:
            return True

        # 负载不均衡检查
        if self._detect_load_imbalance():
            return True

        # 内存使用检查
        return bool(self._detect_memory_pressure())

    def _detect_load_imbalance(self) -> bool:
        """检测负载不均衡情况.

        Returns:
            True表示负载不均衡

        """
        if not self._performance_stats:
            return False

        throughputs = []
        for stats in self._performance_stats.values():
            throughputs.append(stats["throughput"])

        if len(throughputs) < 2:
            return False

        # 计算标准差
        std_dev = statistics.stdev(throughputs)
        mean = statistics.mean(throughputs)

        # 计算变异系数
        if mean > 0:
            cv = std_dev / mean
            if cv > self.min_rebalance_threshold:
                logger.debug(f"检测到负载不均衡: 变异系数={cv:.3f}")
                return True

        return False

    def _detect_memory_pressure(self) -> bool:
        """检测内存压力.

        Returns:
            True表示存在内存压力

        """
        if not self._memory_stats:
            return False

        for stats in self._memory_stats.values():
            if stats["usage_ratio"] > self.memory_usage_threshold:
                logger.debug(f"检测到内存压力: 使用率={stats['usage_ratio']:.3f}")
                return True

        return False

    def redistribute_load(self) -> dict[int, float]:
        """根据实际性能重新分配负载.

        Returns:
            新的权重映射

        """
        if not self._performance_stats:
            logger.debug("无性能数据,保持当前权重")
            return self._weights

        # 检查是否需要重新平衡
        if not self.should_rebalance():
            return self._weights

        logger.info("开始动态负载重平衡...")

        # 基于实际吞吐量计算新权重
        new_weights = {}
        total_throughput = 0

        # GPU厂商性能系数
        vendor_performance_factors = {"nvidia": 1.0, "amd": 0.95, "intel": 0.9}

        for idx, stats in self._performance_stats.items():
            # 考虑历史性能
            historical_perf = self._calculate_historical_performance(idx)
            current_throughput = stats["throughput"]
            error_rate = stats["error_rate"]

            # 计算动态学习率
            history_length = len(self._historical_performance.get(idx, []))
            learning_rate = 0.9 if history_length < 3 else 0.7

            # 结合历史和当前性能
            if historical_perf > 0:
                effective_throughput = (
                    learning_rate * current_throughput + (1 - learning_rate) * historical_perf
                )
            else:
                effective_throughput = current_throughput

            # 考虑错误率
            effective_throughput = effective_throughput * (1 - error_rate)

            # 考虑内存使用情况
            memory_factor = self._get_memory_factor(idx)
            effective_throughput = effective_throughput * memory_factor

            # 考虑GPU厂商特性
            vendor = "unknown"
            for device in self.devices:
                if device["global_index"] == idx:
                    vendor = device.get("vendor", "unknown").lower()
                    break

            vendor_factor = vendor_performance_factors.get(vendor, 0.8)
            effective_throughput = effective_throughput * vendor_factor

            # 考虑预测性能
            predicted_perf = self.get_performance_prediction(idx)
            if predicted_perf and predicted_perf > 0:
                # 结合预测性能，提前调整负载
                effective_throughput = 0.8 * effective_throughput + 0.2 * predicted_perf

            new_weights[idx] = effective_throughput
            total_throughput += effective_throughput

        # 归一化
        if total_throughput > 0:
            # 计算新权重
            raw_weights = {idx: tp / total_throughput for idx, tp in new_weights.items()}

            # 负载平滑：避免权重剧烈变化
            smoothed_weights = {}
            for idx, new_weight in raw_weights.items():
                old_weight = self._weights.get(idx, 1.0 / len(self.devices))
                # 平滑因子，0.3表示30%的新权重，70%的旧权重
                smoothed_weight = 0.3 * new_weight + 0.7 * old_weight
                smoothed_weights[idx] = smoothed_weight

            # 重新归一化
            smoothed_total = sum(smoothed_weights.values())
            if smoothed_total > 0:
                self._weights = {idx: w / smoothed_total for idx, w in smoothed_weights.items()}
            else:
                # 降级为平均分配
                self._weights = {idx: 1.0 / len(self.devices) for idx in self._weights}
        else:
            # 降级为平均分配
            self._weights = {idx: 1.0 / len(self.devices) for idx in self._weights}

        # 记录负载历史
        self._record_load_history()

        self._last_rebalance_time = time.time()

        logger.info(f"负载重平衡完成: {self._weights}")
        return self._weights

    def _calculate_historical_performance(self, device_idx: int) -> float:
        """计算设备的历史性能.

        Args:
            device_idx: 设备索引

        Returns:
            平均历史吞吐量

        """
        if device_idx not in self._historical_performance:
            return 0

        history = self._historical_performance[device_idx]
        if not history:
            return 0

        # 计算最近10次的平均值
        recent_history = history[-10:]
        throughputs = [h["throughput"] for h in recent_history]

        return cast("float", statistics.mean(throughputs))

    def _get_memory_factor(self, device_idx: int) -> float:
        """获取内存影响因子.

        Args:
            device_idx: 设备索引

        Returns:
            内存因子(0.0-1.0)

        """
        if device_idx not in self._memory_stats:
            return 1.0

        stats = self._memory_stats[device_idx]
        usage_ratio = stats["usage_ratio"]

        # 内存使用越高，因子越低
        if usage_ratio < 0.5:
            return 1.0
        if usage_ratio < 0.8:
            return cast("float", 1.0 - (usage_ratio - 0.5) * 0.5)
        return cast("float", 0.8 - (usage_ratio - 0.8) * 0.5)

    def _record_load_history(self) -> None:
        """记录负载历史."""
        timestamp = time.time()

        for idx, weight in self._weights.items():
            if idx not in self._load_history:
                self._load_history[idx] = []

            self._load_history[idx].append({"weight": weight, "timestamp": timestamp})

            # 保持历史数据大小
            if len(self._load_history[idx]) > 100:
                self._load_history[idx] = self._load_history[idx][-100:]

    def get_device_load(self, device_idx: int) -> dict | None:
        """获取指定GPU的负载信息.

        Args:
            device_idx: 设备索引

        Returns:
            负载信息字典

        """
        if device_idx not in self._weights:
            return None

        weight = self._weights[device_idx]
        key_range = self._key_ranges.get(device_idx, (0, 0))
        perf_stats = self._performance_stats.get(device_idx, {})
        memory_stats = self._memory_stats.get(device_idx, {})

        return {
            "device_idx": device_idx,
            "weight": weight,
            "key_range": key_range,
            "throughput": perf_stats.get("throughput", 0),
            "error_rate": perf_stats.get("error_rate", 0),
            "memory_usage": memory_stats.get("usage_ratio", 0),
            "last_update": perf_stats.get("timestamp", 0),
        }

    def get_all_loads(self) -> dict[int, dict]:
        """获取所有GPU的负载信息.

        Returns:
            设备索引 -> 负载信息映射

        """
        loads = {}
        for device in self.devices:
            idx = device["global_index"]
            load = self.get_device_load(idx)
            if load:
                loads[idx] = load

        return loads

    def get_strategy(self) -> str:
        """获取当前负载策略.

        Returns:
            策略名称

        """
        return self.strategy

    def set_strategy(self, strategy: str) -> None:
        """设置负载策略.

        Args:
            strategy: 'performance' 或 'equal'

        """
        if strategy not in ("performance", "equal"):
            raise ValueError(f"无效的策略: {strategy}, 必须是 'performance' 或 'equal'")

        self.strategy = strategy
        self._calculate_initial_weights()

        logger.info("负载策略已更改为: %s", strategy)

    def get_performance_prediction(self, device_idx: int) -> float | None:
        """预测设备性能.

        Args:
            device_idx: 设备索引

        Returns:
            预测的吞吐量

        """
        if device_idx not in self._historical_performance:
            return None

        history = self._historical_performance[device_idx]
        if len(history) < 5:
            return None

        # 简单线性预测
        recent_history = history[-5:]
        throughputs = [h["throughput"] for h in recent_history]

        if len(throughputs) < 2:
            return throughputs[0] if throughputs else None

        # 计算趋势
        trend = (throughputs[-1] - throughputs[0]) / (len(throughputs) - 1)

        # 预测下一个值
        predicted = throughputs[-1] + trend

        return cast("float", max(predicted, 0))

    def reset(self) -> None:
        """重置负载均衡器."""
        self._weights = {}
        self._key_ranges = {}
        self._performance_stats = {}
        self._memory_stats = {}
        self._historical_performance = {}
        self._load_history = {}
        self._last_rebalance_time = time.time()

        self._calculate_initial_weights()

        logger.info("负载均衡器已重置")

    def get_stats(self) -> dict[str, Any]:
        """获取负载均衡器统计信息.

        Returns:
            统计信息字典

        """
        stats = {
            "device_count": len(self.devices),
            "strategy": self.strategy,
            "rebalance_interval": self.rebalance_interval,
            "current_weights": self._weights,
            "performance_stats": self._performance_stats,
            "memory_stats": self._memory_stats,
            "last_rebalance": self._last_rebalance_time,
        }

        # 计算整体性能
        if self._performance_stats:
            total_throughput = sum(s["throughput"] for s in self._performance_stats.values())
            stats["total_throughput"] = total_throughput

        return stats
