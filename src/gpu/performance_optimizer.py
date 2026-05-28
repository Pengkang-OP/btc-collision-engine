"""GPU自适应性能优化器.

基于性能监控数据动态调整GPU碰撞引擎参数，实现：
1. 根据GPU设备类型和性能特征自动优化参数
2. 实时监测性能瓶颈并自适应调整
3. 跨厂商优化（NVIDIA/AMD/Intel）
4. 防止内存溢出和资源竞争
"""

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# 统一日志获取
from ..utils import get_configured_logger
from .constants import clamp_batch_size

__all__ = [
    "GPUPerformanceOptimizer",
    "GPUProfile",
    "GPUVendor",
    "PerformanceMetrics",
    "get_gpu_optimizer",
]


logger = get_configured_logger("GPUPerformanceOptimizer")


# ===== 厂商特定调整策略 =====
# v4.2.1 修复: 统一使用乘法增长/减少，对称调整
# 减少: batch_size * reduction_ratio (如 0.75)
# 增长: batch_size * growth_ratio (如 1.25)
VENDOR_ADJUST_STRATEGY: dict[str, dict[str, float]] = {
    "nvidia": {"growth_ratio": 1.25, "reduction_ratio": 0.75},  # 对称: 增长25%, 减少25%
    "amd": {"growth_ratio": 1.20, "reduction_ratio": 0.80},  # 对称: 增长20%, 减少20%
    "intel": {"growth_ratio": 1.20, "reduction_ratio": 0.80},  # 对称: 增长20%, 减少20%
}
DEFAULT_ADJUST_STRATEGY: dict[str, float] = {"growth_ratio": 1.15, "reduction_ratio": 0.85}


class GPUVendor(Enum):
    """GPU厂商枚举."""

    NVIDIA = "nvidia"
    AMD = "amd"
    INTEL = "intel"
    UNKNOWN = "unknown"


@dataclass
class PerformanceMetrics:
    """性能指标数据类."""

    kernel_compile_time_ms: float = 0.0  # 内核编译时间
    engine_init_time_ms: float = 0.0  # 引擎初始化时间
    batch_execution_time_ms: float = 0.0  # 批次执行时间
    keys_per_second: float = 0.0  # 每秒处理密钥数
    memory_usage_mb: float = 0.0  # 显存使用量
    error_count: int = 0  # 错误计数
    timestamp: float = field(default_factory=time.time)


@dataclass
class GPUProfile:
    """GPU性能配置文件."""

    vendor: GPUVendor
    device_name: str

    # 核心参数
    max_batch_size: int = 65536
    work_group_size: int = 256
    memory_usage_ratio: float = 0.5

    # 计算模式
    preferred_mode: str = "random_collision"  # random_collision/range_scan/brute_force

    # 优化标志
    use_uint32_workaround: bool = False  # Intel Arc workaround
    enable_async_execution: bool = True
    enable_buffer_pooling: bool = True

    # 性能阈值
    slow_compile_threshold_ms: float = 30000.0
    slow_execution_threshold_ms: float = 1000.0
    error_rate_threshold: float = 0.01  # 1%错误率

    # v4.2.1: GPU 利用率目标（Intel Arc A770 实际预期 30-50%）
    min_gpu_utilization_target: float = 0.30  # 最低目标: 30%
    max_gpu_utilization_target: float = 0.50  # 期望目标: 50%（Intel Arc 难以达到更高）

    # 调整策略
    batch_size_step: int = 8192  # 批次调整步长
    min_batch_size: int = 1024
    max_batch_size_limit: int = 16777216  # 16M上限

    def __post_init__(self) -> None:
        """P3-02修复 + CR-04增强: 验证字段值范围."""
        if self.max_batch_size < 1:
            raise ValueError(f"max_batch_size 必须 >= 1, 实际: {self.max_batch_size}")
        if self.work_group_size < 1:
            raise ValueError(f"work_group_size 必须 >= 1, 实际: {self.work_group_size}")
        if not 0.0 <= self.memory_usage_ratio <= 1.0:
            raise ValueError(
                f"memory_usage_ratio 必须在 [0.0, 1.0], 实际: {self.memory_usage_ratio}",
            )
        if self.min_batch_size < 1:
            raise ValueError(f"min_batch_size 必须 >= 1, 实际: {self.min_batch_size}")
        if self.min_batch_size > self.max_batch_size:
            raise ValueError(
                f"min_batch_size ({self.min_batch_size}) 不能大于 "
                f"max_batch_size ({self.max_batch_size})",
            )
        # CR-04增强: 补充遗漏字段验证
        if not 0.0 <= self.error_rate_threshold <= 1.0:
            raise ValueError(
                f"error_rate_threshold 必须在 [0.0, 1.0], 实际: {self.error_rate_threshold}",
            )
        if self.slow_execution_threshold_ms <= 0:
            raise ValueError(
                f"slow_execution_threshold_ms 必须 > 0, 实际: {self.slow_execution_threshold_ms}",
            )
        if self.slow_compile_threshold_ms <= 0:
            raise ValueError(
                f"slow_compile_threshold_ms 必须 > 0, 实际: {self.slow_compile_threshold_ms}",
            )
        if self.batch_size_step < 1:
            raise ValueError(f"batch_size_step 必须 >= 1, 实际: {self.batch_size_step}")
        if self.min_batch_size > self.max_batch_size_limit:
            _mbs = self.min_batch_size
            _mbl = self.max_batch_size_limit
            raise ValueError(f"min_batch_size ({_mbs}) 不能大于 max_batch_size_limit ({_mbl})")
        if self.min_gpu_utilization_target > self.max_gpu_utilization_target:
            raise ValueError(
                f"min_gpu_utilization_target ({self.min_gpu_utilization_target}) 不能大于"
                f" max_gpu_utilization_target ({self.max_gpu_utilization_target})",
            )


class GPUPerformanceOptimizer:
    """GPU自适应性能优化器.

    根据性能监控数据动态调整GPU碰撞引擎参数。
    """

    __slots__ = (
        "_adjustment_cooldown_sec",
        "_adjustment_count",
        "_current_profile",
        "_initial_batch_size",
        "_last_adjustment_time",
        "_lock",
        "_metrics_history",
        "_performance_degraded",
        "_vendor_profiles",
    )

    # P2-02修复: 提取魔法数字为类级别常量
    MAX_METRICS_HISTORY = 100  # 最大保留的性能指标记录数
    ADJUSTMENT_COOLDOWN_SEC = 10  # 调整冷却期（秒）
    MAX_ADJUSTMENTS_PER_MINUTE = 5  # 每分钟最大调整次数
    AGGRESSIVE_GROWTH_CAP = 1.5  # 激进增长倍率上限
    AGGRESSIVE_GROWTH_BASE = 1.2  # 激进增长基础倍率
    ERROR_RATE_GOOD_MULTIPLIER = 2.0  # 性能良好判断的错误率宽松倍数
    STABLE_RECOVERY_THRESHOLD = 10  # 连续稳定次数阈值（触发batch恢复）
    RECOVERY_RATIO = 0.9  # batch恢复比例（恢复到初始值的90%）
    MIN_DATA_POINTS = 3  # 调整所需的最小数据点数
    RECENT_METRICS_WINDOW = 10  # 最近指标分析窗口大小

    def __init__(self) -> None:
        """初始化性能优化器。."""
        self._lock = threading.Lock()
        self._metrics_history: list[PerformanceMetrics] = []
        self._current_profile: GPUProfile | None = None
        self._vendor_profiles = self._init_vendor_profiles()
        self._performance_degraded = False
        self._adjustment_count = 0
        self._last_adjustment_time = 0.0
        self._adjustment_cooldown_sec = 10  # 调整冷却期10秒
        self._initial_batch_size: int = 0  # v4.2.1 修复: 保存真正的初始值

        logger.info("GPU性能优化器初始化完成")

    def _init_vendor_profiles(self) -> dict[GPUVendor, GPUProfile]:
        """初始化各厂商默认配置."""
        return {
            GPUVendor.NVIDIA: GPUProfile(
                vendor=GPUVendor.NVIDIA,
                device_name="NVIDIA GPU",
                max_batch_size=1048576,  # 1M
                work_group_size=256,
                memory_usage_ratio=0.7,  # NVIDIA可以使用更多显存
                preferred_mode="random_collision",
                enable_async_execution=True,
                enable_buffer_pooling=True,
            ),
            GPUVendor.AMD: GPUProfile(
                vendor=GPUVendor.AMD,
                device_name="AMD GPU",
                max_batch_size=524288,  # 512K
                work_group_size=256,
                memory_usage_ratio=0.6,
                preferred_mode="random_collision",
                enable_async_execution=True,
                enable_buffer_pooling=True,
            ),
            GPUVendor.INTEL: GPUProfile(
                vendor=GPUVendor.INTEL,
                device_name="Intel GPU",
                max_batch_size=262144,  # 256K
                work_group_size=512,  # P3修复: 同步v4.2.1优化，匹配Arc A770的512个EU（原128）
                memory_usage_ratio=0.7,  # P3修复: 同步v4.2.1优化的显存率（原0.5）
                preferred_mode="range_scan",
                use_uint32_workaround=True,  # Intel Arc需要workaround
                enable_async_execution=True,  # 启用异步（Intel Arc必须）（原False）
                enable_buffer_pooling=True,
            ),
        }

    def detect_vendor(self, device_name: str, vendor_str: str = "") -> GPUVendor:
        """检测GPU厂商."""
        name_lower = device_name.lower()
        vendor_lower = vendor_str.lower()

        if (
            "nvidia" in vendor_lower
            or "nvidia" in name_lower
            or "geforce" in name_lower
            or "rtx" in name_lower
            or "gtx" in name_lower
        ):
            return GPUVendor.NVIDIA
        if "amd" in vendor_lower or "amd" in name_lower or "radeon" in name_lower:
            return GPUVendor.AMD
        if "intel" in vendor_lower or "intel" in name_lower:
            return GPUVendor.INTEL
        return GPUVendor.UNKNOWN

    def create_optimized_profile(
        self,
        device_name: str,
        vendor_str: str,
        global_mem_size: int,
        compile_time_ms: float = 0.0,
    ) -> GPUProfile:
        """创建优化的GPU配置.

        Args:
            device_name: GPU设备名称
            vendor_str: 厂商标识
            global_mem_size: 全局显存大小（字节）
            compile_time_ms: 内核编译时间（毫秒）

        Returns:
            优化后的GPU配置

        """
        vendor = self.detect_vendor(device_name, vendor_str)

        # 获取厂商默认配置
        if vendor in self._vendor_profiles:
            profile = GPUProfile(
                vendor=vendor,
                device_name=device_name,
                **{
                    k: v
                    for k, v in self._vendor_profiles[vendor].__dict__.items()
                    if k not in ["vendor", "device_name"]
                },
            )
        else:
            profile = GPUProfile(vendor=GPUVendor.UNKNOWN, device_name=device_name)

        # 根据显存大小调整batch_size（优化版：更细粒度的分段）
        mem_gb = global_mem_size / (1024**3)
        if mem_gb >= 16:
            # 16GB+ 旗舰级GPU
            profile.max_batch_size = min(profile.max_batch_size * 4, profile.max_batch_size_limit)
            profile.memory_usage_ratio = min(profile.memory_usage_ratio + 0.15, 0.85)
        elif mem_gb >= 8:
            # 8-16GB 高端GPU
            profile.max_batch_size = min(profile.max_batch_size * 2, profile.max_batch_size_limit)
            profile.memory_usage_ratio = min(profile.memory_usage_ratio + 0.1, 0.8)
        elif mem_gb >= 4:
            # 4-8GB 中端GPU
            profile.max_batch_size = max(profile.max_batch_size // 2, profile.min_batch_size)
            profile.memory_usage_ratio = max(profile.memory_usage_ratio - 0.05, 0.4)
        elif mem_gb >= 2:
            # 2-4GB 入门级GPU
            profile.max_batch_size = max(profile.max_batch_size // 4, profile.min_batch_size)
            profile.memory_usage_ratio = max(profile.memory_usage_ratio - 0.15, 0.3)
        else:
            # <2GB 低端GPU/集成显卡
            profile.max_batch_size = profile.min_batch_size
            profile.memory_usage_ratio = 0.3

        # 根据编译时间调整（编译慢说明内核复杂，减少batch）
        if compile_time_ms > 20000:
            logger.warning(f"内核编译时间较长({compile_time_ms:.0f}ms)，降低batch_size")
            profile.max_batch_size = max(profile.max_batch_size // 2, profile.min_batch_size)

        # 记录配置
        self._current_profile = profile
        self._initial_batch_size = profile.max_batch_size  # v4.2.1 修复: 保存真正的初始值
        logger.info(
            f"GPU配置已优化: {device_name}, "
            f"batch_size={profile.max_batch_size}, "
            f"work_group={profile.work_group_size}, "
            f"mem_ratio={profile.memory_usage_ratio}",
        )

        return profile

    def record_performance(self, metrics: PerformanceMetrics) -> None:
        """记录性能指标.

        Args:
            metrics: 性能指标数据

        """
        # 验证数据有效性
        if metrics.batch_execution_time_ms < 0:
            logger.warning(f"无效的批次执行时间: {metrics.batch_execution_time_ms}")
            return

        if metrics.keys_per_second < 0:
            logger.warning(f"无效的吞吐量: {metrics.keys_per_second}")
            return

        if metrics.error_count < 0:
            logger.warning(f"无效的错误计数: {metrics.error_count}")
            return

        with self._lock:
            self._metrics_history.append(metrics)

            # 保留最近记录
            if len(self._metrics_history) > self.MAX_METRICS_HISTORY:
                self._metrics_history = self._metrics_history[-self.MAX_METRICS_HISTORY :]

    def _analyze_check_readiness(
        self,
        current_batch_size: int,
        engine: Any = None,
    ) -> tuple[int, dict[str, Any]] | None:
        """检查是否可以进行调整（profile存在、冷却期、频率限流）.

        Returns:
            None 表示可以继续调整；否则返回 (batch_size, info) 用于提前返回

        """
        if not self._current_profile:
            return current_batch_size, {"action": "no_profile", "reason": "未创建配置文件"}

        now = time.time()
        with self._lock:
            cooldown_elapsed = now - self._last_adjustment_time
            if cooldown_elapsed < self._adjustment_cooldown_sec:
                remaining = self._adjustment_cooldown_sec - cooldown_elapsed
                return current_batch_size, {
                    "action": "cooldown",
                    "reason": f"调整冷却期，剩余{remaining:.1f}秒",
                }

        if engine is not None:
            monitor = getattr(engine, "_engine_monitor", None)
            if monitor is not None:
                recent_count = monitor.get_recent_adjustments(seconds=60)
                if recent_count >= self.MAX_ADJUSTMENTS_PER_MINUTE:
                    logger.warning("batch_size调整过于频繁 (%s次/60秒)，暂停自动调整", recent_count)
                    return current_batch_size, {
                        "action": "rate_limited",
                        "reason": f"调整频率超限({recent_count}次/60秒)",
                    }

        return None

    def _analyze_get_vendor_strategy(self, engine: Any = None) -> tuple[str, dict[str, Any]]:
        """获取厂商标识和调整策略."""
        vendor_key = "unknown"
        if engine is not None:
            vendor_key = getattr(engine, "_vendor", "unknown")
            if not isinstance(vendor_key, str):
                vendor_key = "unknown"
            vendor_key = vendor_key.lower()
            if vendor_key == "unknown" and hasattr(engine, "gpu_device"):
                vendor_key = str(getattr(engine.gpu_device, "vendor", "unknown")).lower()
        if vendor_key == "unknown" and self._current_profile:
            vendor_key = self._current_profile.vendor.value.lower()
        strategy = VENDOR_ADJUST_STRATEGY.get(vendor_key, DEFAULT_ADJUST_STRATEGY)
        return vendor_key, strategy

    def _analyze_perform_adjustments(
        self,
        current_batch_size: int,
        error_rate: float,
        engine: Any,
        strategy: dict[str, Any],
        now: float,
    ) -> tuple[int, dict[str, Any]]:
        """在持有锁的情况下执行性能分析和batch调整（锁由调用方持有）."""
        if len(self._metrics_history) < self.MIN_DATA_POINTS:
            return current_batch_size, {"action": "insufficient_data", "reason": "数据不足"}

        recent_metrics = self._metrics_history[-self.RECENT_METRICS_WINDOW :]
        n = len(recent_metrics)
        avg_execution_time = sum(m.batch_execution_time_ms for m in recent_metrics) / n
        avg_speed = sum(m.keys_per_second for m in recent_metrics) / n

        adjustments: dict[str, Any] = {}
        new_batch_size = current_batch_size
        profile = self._current_profile
        if profile is None:
            raise RuntimeError("_current_profile not set for batch size calculation")

        gpu_utilization = 0.0
        if engine is not None:
            try:
                monitor = getattr(engine, "_engine_monitor", None)
                if monitor is not None:
                    stats = monitor.get_stats()
                    gpu_utilization = stats.get("avg_gpu_utilization", 0.0)
            except (AttributeError, RuntimeError, TypeError):
                logger.debug("Failed to get GPU utilization stats from monitor")

        min_target = profile.min_gpu_utilization_target
        growth_ratio = self._analyze_compute_growth_ratio(gpu_utilization, min_target, strategy)
        reduction_ratio = strategy.get("reduction_ratio", 0.80)

        # 减少batch：错误率高 AND 执行时间长
        if (
            error_rate > profile.error_rate_threshold
            and avg_execution_time > profile.slow_execution_threshold_ms
        ):
            new_batch_size = max(
                profile.min_batch_size,
                int(current_batch_size * reduction_ratio),
            )
            adjustments["performance_degraded"] = {
                "error_rate": error_rate,
                "error_threshold": profile.error_rate_threshold,
                "avg_time_ms": avg_execution_time,
                "time_threshold_ms": profile.slow_execution_threshold_ms,
                "action": "reduce_batch",
                "old_batch": current_batch_size,
                "new_batch": new_batch_size,
                "reduction_ratio": reduction_ratio,
            }
            logger.warning(
                f"性能下降(错误率{error_rate:.2%}, 时间{avg_execution_time:.0f}ms)，"
                f"减小batch: {current_batch_size} -> {new_batch_size} (*{reduction_ratio})",
            )

        # 增长batch：性能良好 或 GPU利用率不足
        elif (
            avg_execution_time < profile.slow_execution_threshold_ms * 1.0
            and error_rate < profile.error_rate_threshold * self.ERROR_RATE_GOOD_MULTIPLIER
        ) or (gpu_utilization > 0 and gpu_utilization < min_target):
            new_batch_size = min(
                profile.max_batch_size_limit,
                int(current_batch_size * growth_ratio),
            )
            adjustments["performance_good"] = {
                "avg_time_ms": avg_execution_time,
                "avg_speed": avg_speed,
                "growth_ratio": growth_ratio,
                "action": "increase_batch",
                "old_batch": current_batch_size,
                "new_batch": new_batch_size,
            }
            logger.info(
                "性能良好，增大batch: %s -> %s (*%s)",
                current_batch_size,
                new_batch_size,
                growth_ratio,
            )

        if new_batch_size != current_batch_size:
            new_batch_size = clamp_batch_size(new_batch_size)

        new_batch_size = self._analyze_try_recover(new_batch_size, recent_metrics, adjustments)

        if new_batch_size != current_batch_size:
            self._adjustment_count += 1
            self._last_adjustment_time = now
            adjustments["adjustment_count"] = self._adjustment_count

        return new_batch_size, adjustments

    def _analyze_compute_growth_ratio(
        self,
        gpu_utilization: float,
        min_target: float,
        strategy: dict[str, Any],
    ) -> float:
        """计算增长比率：GPU利用率低时更激进."""
        if gpu_utilization > 0 and gpu_utilization < min_target:
            deficit_ratio = min_target / max(gpu_utilization, 0.1)
            growth_ratio = min(
                self.AGGRESSIVE_GROWTH_CAP,
                self.AGGRESSIVE_GROWTH_BASE * deficit_ratio,
            )
            logger.info(
                f"GPU利用率不足({gpu_utilization * 100:.1f}% < {min_target * 100:.1f}%), "
                f"激进增长: *{growth_ratio:.2f}",
            )
            return growth_ratio
        return strategy.get("growth_ratio", 1.20)

    def _analyze_try_recover(
        self,
        new_batch_size: int,
        recent_metrics: list[Any],
        adjustments: dict[str, Any],
    ) -> int:
        """尝试恢复batch_size：连续稳定时恢复到初始水平."""
        if not self._current_profile or self._initial_batch_size <= 0:
            return new_batch_size

        stable_count = sum(1 for m in recent_metrics if m.error_count == 0)
        enough_samples = len(recent_metrics) >= self.STABLE_RECOVERY_THRESHOLD

        if stable_count >= self.STABLE_RECOVERY_THRESHOLD and enough_samples:
            recovery_batch = int(self._initial_batch_size * self.RECOVERY_RATIO)
            if recovery_batch > new_batch_size:
                adjustments["batch_recovery"] = {
                    "reason": "stable_recovery",
                    "old_batch": new_batch_size,
                    "new_batch": recovery_batch,
                    "initial_batch": self._initial_batch_size,
                }
                logger.info(
                    f"batch_size 恢复: {new_batch_size}->{recovery_batch} "
                    f"(初始:{self._initial_batch_size})",
                )
                return recovery_batch

        return new_batch_size

    def analyze_and_adjust(
        self,
        current_batch_size: int,
        error_rate: float = 0.0,
        engine: Any = None,
    ) -> tuple[int, dict[str, Any]]:
        """分析性能数据并调整参数.

        Args:
            current_batch_size: 当前批次大小
            error_rate: 错误率（0.0-1.0）
            engine: GPU引擎实例（可选），用于获取厂商信息和monitor

        Returns:
            (new_batch_size, adjustment_info)

        """
        result = self._analyze_check_readiness(current_batch_size, engine)
        if result is not None:
            return result

        now = time.time()
        _vendor_key, strategy = self._analyze_get_vendor_strategy(engine)

        with self._lock:
            return self._analyze_perform_adjustments(
                current_batch_size,
                error_rate,
                engine,
                strategy,
                now,
            )

    def get_optimization_report(self) -> dict[str, Any]:
        """获取优化报告."""
        if not self._current_profile:
            return {"status": "no_profile"}

        with self._lock:
            if not self._metrics_history:
                return {
                    "status": "no_metrics",
                    "profile": {
                        "vendor": self._current_profile.vendor.value,
                        "device": self._current_profile.device_name,
                        "batch_size": self._current_profile.max_batch_size,
                    },
                }

            recent = self._metrics_history[-self.RECENT_METRICS_WINDOW :]
            avg_speed = sum(m.keys_per_second for m in recent) / len(recent)
            avg_error = sum(m.error_count for m in recent) / len(recent)

            # 计算时间范围
            time_range_sec = self._metrics_history[-1].timestamp - self._metrics_history[0].timestamp

            return {
                "status": "active",
                "time_range": {
                    "start": self._metrics_history[0].timestamp,
                    "end": self._metrics_history[-1].timestamp,
                    "duration_sec": time_range_sec,
                    "duration_min": time_range_sec / 60,
                },
                "profile": {
                    "vendor": self._current_profile.vendor.value,
                    "device": self._current_profile.device_name,
                    "batch_size": self._current_profile.max_batch_size,
                    "work_group_size": self._current_profile.work_group_size,
                    "memory_ratio": self._current_profile.memory_usage_ratio,
                },
                "performance": {
                    "avg_keys_per_second": avg_speed,
                    "avg_error_count": avg_error,
                    "total_adjustments": self._adjustment_count,
                    "metrics_count": len(self._metrics_history),
                },
                "recommendations": self._generate_recommendations(),
            }

    def _generate_recommendations(self) -> list[str]:
        """生成优化建议."""
        recommendations: list[str] = []

        if not self._current_profile or not self._metrics_history:
            return recommendations

        profile = self._current_profile
        recent = self._metrics_history[-5:]

        # 检查编译时间
        compile_times = [m.kernel_compile_time_ms for m in recent if m.kernel_compile_time_ms > 0]
        if compile_times:
            avg_compile = sum(compile_times) / len(compile_times)
            if avg_compile > profile.slow_compile_threshold_ms:
                recommendations.append(
                    f"内核编译时间较长({avg_compile:.0f}ms)，考虑使用内核缓存或预编译",
                )

        # 检查错误率
        total_errors = sum(m.error_count for m in recent)
        if total_errors > 0:
            recommendations.append(f"检测到{total_errors}个错误，建议检查GPU驱动和显存使用")

        # 厂商特定建议
        if profile.vendor == GPUVendor.INTEL and not profile.use_uint32_workaround:
            recommendations.append("Intel GPU建议启用uint32 workaround避免hang bug")
        elif profile.vendor == GPUVendor.NVIDIA and profile.memory_usage_ratio < 0.6:
            recommendations.append("NVIDIA GPU可以尝试提高显存使用率至60-70%")

        return recommendations

    def reset(self) -> None:
        """重置优化器状态."""
        with self._lock:
            self._metrics_history.clear()
            self._current_profile = None
            self._adjustment_count = 0
            self._last_adjustment_time = 0.0
        logger.info("GPU性能优化器已重置")


# 全局优化器实例
_global_optimizer = None
_optimizer_lock = threading.Lock()


def get_gpu_optimizer() -> GPUPerformanceOptimizer:
    """获取全局GPU性能优化器实例（单例模式）."""
    global _global_optimizer

    if _global_optimizer is None:
        with _optimizer_lock:
            if _global_optimizer is None:
                _global_optimizer = GPUPerformanceOptimizer()

    return _global_optimizer
