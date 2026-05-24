"""Intel GPU 显存监控器

监控 GPU 显存使用情况，提供：
1. 实时显存使用跟踪
2. 使用率预警机制
3. 显存泄漏检测
4. 自动清理建议

v4.2.1 修复:
- 统一 get_status() 与 _record_snapshot() 的状态判断逻辑，消除不一致
- safe_usage_ratio 默认值从硬编码 INTEL_SAFE_MEMORY_RATIO(0.45) 改为 0.70，
  与 IntelGPUVendor.apply_optimizations() 设置的 memory_efficiency=0.70 保持一致
- 将阈值常量提取为类属性，避免魔法数字
"""

import time
from dataclasses import dataclass
from enum import Enum

from ..utils import get_configured_logger

logger = get_configured_logger("IntelMemoryMonitor")


class MemoryStatus(Enum):
    """显存状态枚举"""

    NORMAL = "normal"  # 正常 (< 70% 限制)
    WARNING = "warning"  # 警告 (70-85% 限制)
    CRITICAL = "critical"  # 严重 (85-95% 限制)
    EMERGENCY = "emergency"  # 紧急 (> 95% 限制)


@dataclass
class MemorySnapshot:
    """显存快照"""

    timestamp: float
    allocated_bytes: int
    total_bytes: int
    usage_percent: float
    status: MemoryStatus
    batch_count: int = 0


class IntelMemoryMonitor:
    """Intel GPU 显存监控器

    针对 Intel Arc GPU 的显存管理策略。

    v4.2.1 修复: safe_usage_ratio 默认值从 0.45 改为 0.70，与
    IntelGPUVendor.apply_optimizations() 设置的 memory_efficiency 一致。
    旧值 0.45 导致监控器在正常工作时频繁误报警。

    使用示例:
        >>> monitor = IntelMemoryMonitor(total_memory_bytes=8 * 1024**3)  # 8GB
        >>> # 记录分配
        >>> monitor.track_allocation(1024 * 1024 * 512)  # 分配 512MB
        >>> # 检查状态
        >>> status = monitor.get_status()
        >>> if status['status'] == MemoryStatus.WARNING:
        ...     print("显存使用率过高！")
    """

    # 阈值常量：基于 safe_limit 的使用比例
    WARNING_THRESHOLD = 0.70
    CRITICAL_THRESHOLD = 0.85
    EMERGENCY_THRESHOLD = 0.95

    __slots__ = (
        "total_memory", "safe_usage_ratio", "safe_limit",
        "warning_limit", "critical_limit", "emergency_limit",
        "_warning_ratio", "_critical_ratio", "_emergency_ratio",
        "current_usage", "peak_usage", "total_allocations", "total_deallocations",
        "_history", "_max_history", "_allocation_sizes", "_leak_detection_window",
    )

    def __init__(
        self,
        total_memory_bytes: int,
        safe_usage_ratio: float = 0.70,
        warning_threshold: float = WARNING_THRESHOLD,
        critical_threshold: float = CRITICAL_THRESHOLD,
        emergency_threshold: float = EMERGENCY_THRESHOLD,
    ) -> None:
        """初始化显存监控器

        Args:
            total_memory_bytes: GPU 总显存（字节）
            safe_usage_ratio: 安全使用率上限，默认 0.70（与 memory_efficiency 一致）
            warning_threshold: 警告阈值（相对于 safe_limit，默认 70%）
            critical_threshold: 严重阈值（相对于 safe_limit，默认 85%）
            emergency_threshold: 紧急阈值（相对于 safe_limit，默认 95%）

        """
        self.total_memory = total_memory_bytes
        self.safe_usage_ratio = safe_usage_ratio
        self.safe_limit = int(total_memory_bytes * safe_usage_ratio)
        self.warning_limit = int(self.safe_limit * warning_threshold)
        self.critical_limit = int(self.safe_limit * critical_threshold)
        self.emergency_limit = int(self.safe_limit * emergency_threshold)
        # 保存阈值比例用于统一状态判断
        self._warning_ratio = warning_threshold
        self._critical_ratio = critical_threshold
        self._emergency_ratio = emergency_threshold

        # 跟踪信息
        self.current_usage = 0
        self.peak_usage = 0
        self.total_allocations = 0
        self.total_deallocations = 0

        # 历史记录
        self._history: list[MemorySnapshot] = []
        self._max_history = 100

        # 泄漏检测
        self._allocation_sizes: list[int] = []
        self._leak_detection_window = 50  # 检测窗口大小

        logger.info(
            "Intel 显存监控器已初始化: "
            f"total={total_memory_bytes / 1024**3:.1f}GB, "
            f"safe_limit={self.safe_limit / 1024**2:.0f}MB ({safe_usage_ratio * 100:.0f}%)",
        )

    def track_allocation(self, size_bytes: int, batch_count: int = 0) -> bool:
        """跟踪显存分配

        Args:
            size_bytes: 分配的字节数
            batch_count: 当前批次计数

        Returns:
            如果分配安全返回 True，否则返回 False

        """
        if size_bytes <= 0:
            logger.warning("忽略无效的分配大小: %s", size_bytes)
            return False

        new_usage = self.current_usage + size_bytes

        # 检查是否超出安全限制
        if new_usage > self.safe_limit:
            _new_mb = new_usage / 1024**2
            _limit_mb = self.safe_limit / 1024**2
            logger.warning(f"显存分配超出安全限制: {_new_mb:.0f}MB > {_limit_mb:.0f}MB")
            return False

        self.current_usage = new_usage
        self.peak_usage = max(self.peak_usage, self.current_usage)
        self.total_allocations += 1

        # 记录用于泄漏检测
        self._allocation_sizes.append(size_bytes)
        if len(self._allocation_sizes) > self._leak_detection_window:
            self._allocation_sizes = self._allocation_sizes[-self._leak_detection_window :]

        # 记录快照
        self._record_snapshot(batch_count)

        logger.debug(
            f"显存分配: +{size_bytes / 1024**2:.1f}MB, 总计: {self.current_usage / 1024**2:.1f}MB",
        )

        return True

    def track_deallocation(self, size_bytes: int, batch_count: int = 0) -> None:
        """跟踪显存释放

        Args:
            size_bytes: 释放的字节数
            batch_count: 当前批次计数

        """
        if size_bytes <= 0:
            return

        self.current_usage = max(0, self.current_usage - size_bytes)
        self.total_deallocations += 1

        # 记录快照
        self._record_snapshot(batch_count)

        logger.debug(
            f"显存释放: -{size_bytes / 1024**2:.1f}MB, 总计: {self.current_usage / 1024**2:.1f}MB",
        )

    def get_status(self) -> dict:
        """获取当前显存状态

        Returns:
            包含显存状态的字典

        """
        status = self._determine_status()

        return {
            "status": status,
            "current_bytes": self.current_usage,
            "current_mb": self.current_usage / 1024**2,
            "peak_bytes": self.peak_usage,
            "peak_mb": self.peak_usage / 1024**2,
            "safe_limit_bytes": self.safe_limit,
            "safe_limit_mb": self.safe_limit / 1024**2,
            "usage_percent": (
                (self.current_usage / self.safe_limit * 100) if self.safe_limit > 0 else 0
            ),
            "total_memory_gb": self.total_memory / 1024**3,
            "total_allocations": self.total_allocations,
            "total_deallocations": self.total_deallocations,
        }

    def check_warnings(self) -> list[str]:
        """检查并发出警告

        Returns:
            警告消息列表

        """
        warnings = []
        status = self.get_status()

        # 显存使用率警告
        if status["status"] == MemoryStatus.EMERGENCY:
            warnings.append(
                f"🚨 显存紧急: {status['usage_percent']:.1f}% "
                f"({status['current_mb']:.0f}MB / {status['safe_limit_mb']:.0f}MB)",
            )
        elif status["status"] == MemoryStatus.CRITICAL:
            warnings.append(
                f"[WARN] 显存严重: {status['usage_percent']:.1f}% "
                f"({status['current_mb']:.0f}MB / {status['safe_limit_mb']:.0f}MB)",
            )
        elif status["status"] == MemoryStatus.WARNING:
            warnings.append(
                f"💡 显存警告: {status['usage_percent']:.1f}% "
                f"({status['current_mb']:.0f}MB / {status['safe_limit_mb']:.0f}MB)",
            )

        # 显存泄漏检测
        leak_detected = self._detect_memory_leak()
        if leak_detected:
            warnings.append(
                "🔍 疑似显存泄漏: "
                f"分配={self.total_allocations}, "
                f"释放={self.total_deallocations}, "
                f"未释放={self.total_allocations - self.total_deallocations}",
            )

        return warnings

    def should_reduce_batch_size(self) -> bool:
        """判断是否应该减小 batch_size

        Returns:
            如果显存压力过大返回 True

        """
        status = self.get_status()
        return status["status"] in [MemoryStatus.CRITICAL, MemoryStatus.EMERGENCY]

    def get_recommended_batch_reduction(self) -> float:
        """获取建议的 batch_size 减少比例

        Returns:
            减少比例（0.0-1.0），0.0 表示不需要减少

        """
        status = self.get_status()

        if status["status"] == MemoryStatus.EMERGENCY:
            return 0.5  # 减少 50%
        if status["status"] == MemoryStatus.CRITICAL:
            return 0.3  # 减少 30%
        if status["status"] == MemoryStatus.WARNING:
            return 0.1  # 减少 10%
        return 0.0

    def _detect_memory_leak(self) -> bool:
        """检测显存泄漏

        策略：如果分配次数远大于释放次数，且当前使用量持续增长

        Returns:
            如果检测到可能的泄漏返回 True

        """
        if self.total_allocations < 10:
            return False

        # 计算分配释放比
        if self.total_deallocations == 0:
            return self.total_allocations > 20

        ratio = self.total_allocations / self.total_deallocations

        # 如果分配是释放的 3 倍以上，可能存在泄漏
        return ratio > 3.0

    def _determine_status(self) -> MemoryStatus:
        """统一的状态判断逻辑

        基于 safe_limit 的使用比例判断，确保 get_status() 和
        _record_snapshot() 使用完全相同的判断标准。

        Returns:
            当前显存状态

        """
        if self.safe_limit <= 0:
            return MemoryStatus.EMERGENCY

        usage_ratio = self.current_usage / self.safe_limit

        if usage_ratio >= self._emergency_ratio:
            return MemoryStatus.EMERGENCY
        if usage_ratio >= self._critical_ratio:
            return MemoryStatus.CRITICAL
        if usage_ratio >= self._warning_ratio:
            return MemoryStatus.WARNING
        return MemoryStatus.NORMAL

    def _record_snapshot(self, batch_count: int = 0) -> None:
        """记录显存快照

        Args:
            batch_count: 当前批次计数

        """
        usage_ratio = self.current_usage / self.safe_limit if self.safe_limit > 0 else 0
        status = self._determine_status()

        snapshot = MemorySnapshot(
            timestamp=time.time(),
            allocated_bytes=self.current_usage,
            total_bytes=self.total_memory,
            usage_percent=usage_ratio * 100,
            status=status,
            batch_count=batch_count,
        )

        self._history.append(snapshot)

        # 限制历史记录大小
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

    def get_history(self, last_n: int = 10) -> list[MemorySnapshot]:
        """获取历史记录

        Args:
            last_n: 获取最近 N 条记录

        Returns:
            显存快照列表

        """
        return self._history[-last_n:]

    def reset(self) -> None:
        """重置监控器状态"""
        self.current_usage = 0
        self.peak_usage = 0
        self.total_allocations = 0
        self.total_deallocations = 0
        self._history.clear()
        self._allocation_sizes.clear()
        logger.info("Intel 显存监控器已重置")

    def get_report(self) -> str:
        """生成显存使用报告

        Returns:
            格式化的报告字符串

        """
        status = self.get_status()

        report_lines = [
            "=" * 60,
            "📊 Intel GPU 显存使用报告",
            "=" * 60,
            f"总显存: {status['total_memory_gb']:.1f} GB",
            f"安全限制: {status['safe_limit_mb']:.0f} MB ({self.safe_usage_ratio * 100:.0f}%)",
            f"当前使用: {status['current_mb']:.1f} MB ({status['usage_percent']:.1f}%)",
            f"峰值使用: {status['peak_mb']:.1f} MB",
            f"状态: {status['status'].value.upper()}",
            f"分配次数: {status['total_allocations']}",
            f"释放次数: {status['total_deallocations']}",
            f"未释放: {status['total_allocations'] - status['total_deallocations']}",
            "=" * 60,
        ]

        # 添加警告
        warnings = self.check_warnings()
        if warnings:
            report_lines.append("[WARN] 警告:")
            for warning in warnings:
                report_lines.append(f"  {warning}")

        return "\n".join(report_lines)
