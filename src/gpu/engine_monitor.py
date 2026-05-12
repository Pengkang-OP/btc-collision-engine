"""GPU引擎监控模块

负责追踪和报告 GPU 碰撞引擎的运行状态，包括：
- batch_size 调整历史记录
- 引擎运行状态快照
- 性能调整统计汇总
- 性能指标收集和分析
- 自适应 batch_size 调整

职责边界:
- 本模块仅负责引擎层面的监控数据管理（调整历史、状态摘要）
- GPU设备层性能指标 → performance_optimizer.py (PerformanceMetrics)
- 数据质量监控 → data_monitor.py (DataMonitor)
- 详细性能报告 → performance_reporter.py (PerformanceReportGenerator)
"""

import threading
import time
from collections import deque
from typing import TYPE_CHECKING, Any, Optional

# P3-5: 统一日志获取 + 修复缺失导入
from ..utils import get_configured_logger

if TYPE_CHECKING:
    # 避免循环导入：仅在类型检查时引用引擎
    from ..collision.gpu_collision_engine import GPUCollisionEngine

logger = get_configured_logger("GPUEngineMonitor")


class GPUEngineMonitor:
    """GPU引擎监控器

    封装 GPU 碰撞引擎的调整历史记录和状态快照逻辑，
    将监控职责从核心引擎中解耦出来。

    使用示例::

        engine = GPUCollisionEngine(targets)
        monitor = GPUEngineMonitor(engine)

        # 记录一次 batch_size 调整
        monitor.record_adjustment(old_size=65536, new_size=131072, reason="performance_good")

        # 查询最近的调整历史
        history = monitor.get_adjustment_history(limit=5)

        # 获取引擎状态快照
        status = monitor.get_engine_status()
    """

    def __init__(self, engine: Optional["GPUCollisionEngine"] = None) -> None:
        """初始化引擎监控器

        Args:
            engine: GPU碰撞引擎实例（可选）。传入后可通过
                    :meth:`get_engine_status` 获取实时状态摘要。
        """
        self._engine = engine

        # 调整历史存储
        self._adjustment_history: list[dict[str, Any]] = []
        self._adjustment_history_lock = threading.Lock()

        # 性能窗口（最近100批的性能数据）
        self._performance_window: deque = deque(maxlen=100)
        self._performance_lock = threading.Lock()

        # 自适应调整参数
        self._adaptive_enabled = True
        self._adjust_interval = 30.0  # 调整间隔（秒）
        self._last_adjust_time = 0.0
        self._error_rate_threshold = 0.01  # 错误率阈值1%

        logger.debug("GPUEngineMonitor 已初始化")

    # ------------------------------------------------------------------
    # batch_size 调整历史
    # ------------------------------------------------------------------

    def record_adjustment(
        self,
        old_size: int,
        new_size: int,
        reason: str,
        details: str = "",
    ) -> None:
        """记录一次 batch_size 调整事件

        Args:
            old_size: 调整前的批次大小
            new_size: 调整后的批次大小
            reason:   调整原因标识（如 "performance_good"、"buffer_resize"）
            details:  可选的补充说明
        """
        change_percent = ((new_size - old_size) / old_size * 100) if old_size > 0 else 0.0

        record: dict[str, Any] = {
            "timestamp": time.time(),
            "old_batch_size": old_size,
            "new_batch_size": new_size,
            "reason": reason,
            "details": details,
            "change_percent": change_percent,
        }

        with self._adjustment_history_lock:
            self._adjustment_history.append(record)
            # 保留最近100条记录，防止内存无限增长
            # 使用切片删除而非赋值，避免潜在引用问题
            if len(self._adjustment_history) > 100:
                del self._adjustment_history[:-100]

        logger.debug(
            "batch_size 调整记录: %s -> %s (%+.1f%%) - %s",
            f"{old_size:,}",
            f"{new_size:,}",
            change_percent,
            reason,
        )

    def get_adjustment_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """获取 batch_size 调整历史（按时间倒序）

        Args:
            limit: 返回的记录数量上限

        Returns:
            调整历史记录列表，最新记录在前
        """
        with self._adjustment_history_lock:
            history = self._adjustment_history.copy()

        history.sort(key=lambda x: x["timestamp"], reverse=True)
        return history[:limit]

    def get_adjustment_stats(self) -> dict[str, Any]:
        """统计调整历史摘要

        Returns:
            包含总次数、平均变化幅度等的统计字典
        """
        with self._adjustment_history_lock:
            history = self._adjustment_history.copy()

        if not history:
            return {
                "total_adjustments": 0,
                "increases": 0,
                "decreases": 0,
                "avg_change_percent": 0.0,
                "last_adjustment_time": None,
            }

        increases = sum(1 for r in history if r["change_percent"] > 0)
        decreases = sum(1 for r in history if r["change_percent"] < 0)
        avg_change = sum(r["change_percent"] for r in history) / len(history)
        last_time = max(r["timestamp"] for r in history)

        return {
            "total_adjustments": len(history),
            "increases": increases,
            "decreases": decreases,
            "avg_change_percent": round(avg_change, 2),
            "last_adjustment_time": last_time,
        }

    def get_recent_adjustments(self, seconds: int = 60) -> int:
        """获取最近N秒内的调整次数

        Args:
            seconds: 时间窗口（秒），默认60秒

        Returns:
            该时间窗口内的调整次数
        """
        cutoff = time.time() - seconds
        with self._adjustment_history_lock:
            return sum(1 for adj in self._adjustment_history if adj.get("timestamp", 0) >= cutoff)

    def clear_adjustment_history(self) -> None:
        """清空调整历史（重置统计）"""
        with self._adjustment_history_lock:
            self._adjustment_history.clear()
        logger.debug("调整历史已清空")

    # ------------------------------------------------------------------
    # 引擎状态快照
    # ------------------------------------------------------------------

    def get_engine_status(self) -> dict[str, Any]:
        """获取引擎运行状态快照

        整合引擎基本信息、当前配置和监控统计，供外部组件或 GUI 轮询。

        Returns:
            状态字典，包括::

                {
                    "engine_available": bool,
                    "is_running": bool,
                    "batch_size": int | None,
                    "device_info": dict,
                    "stats_snapshot": dict | None,
                    "adjustment_stats": dict,
                }

        Notes:
            若 :attr:`_engine` 为 None，则 engine_available 为 False，
            其余字段返回默认空值。
        """
        if self._engine is None:
            return {
                "engine_available": False,
                "is_running": False,
                "batch_size": None,
                "device_info": {},
                "stats_snapshot": None,
                "adjustment_stats": self.get_adjustment_stats(),
            }

        engine = self._engine

        try:
            is_running = engine.is_running() if hasattr(engine, "is_running") else False
        except (AttributeError, RuntimeError):
            is_running = False

        try:
            batch_size = engine.batch_size
        except (AttributeError, RuntimeError):
            batch_size = None

        try:
            device_info = engine.get_device_info() if hasattr(engine, "get_device_info") else {}
        except (AttributeError, RuntimeError):
            device_info = {}

        try:
            stats = engine.get_stats() if hasattr(engine, "get_stats") else None
            stats_snapshot = stats.snapshot() if stats and hasattr(stats, "snapshot") else None
        except (AttributeError, RuntimeError):
            stats_snapshot = None

        return {
            "engine_available": True,
            "is_running": is_running,
            "batch_size": batch_size,
            "device_info": device_info,
            "stats_snapshot": stats_snapshot,
            "adjustment_stats": self.get_adjustment_stats(),
            "performance_stats": self.get_performance_stats(),
        }

    # ------------------------------------------------------------------
    # 性能监控和自适应调整
    # ------------------------------------------------------------------

    def record_batch_performance(self, batch_time: float, num_keys: int, success: bool) -> None:
        """记录批次性能数据

        Args:
            batch_time: 批次执行时间（秒）
            num_keys: 处理的私钥数量
            success: 是否成功
        """
        performance_data = {
            "timestamp": time.time(),
            "batch_time": batch_time,
            "num_keys": num_keys,
            "success": success,
            "throughput": num_keys / batch_time if batch_time > 0 else 0,
        }

        with self._performance_lock:
            self._performance_window.append(performance_data)

        # 更新引擎统计信息
        if self._engine and success:
            try:
                eng: Any = self._engine
                eng.stats.last_batch_time = batch_time
                eng.stats.total_keys += num_keys
            except Exception as e:
                logger.warning(f"更新引擎统计信息失败: {e}")

    def should_adjust_batch_size(self) -> bool:
        """判断是否需要调整batch_size

        Returns:
            True表示需要调整，False表示不需要
        """
        if not self._adaptive_enabled:
            return False

        current_time = time.time()
        if current_time - self._last_adjust_time < self._adjust_interval:
            return False

        # 检查是否有足够的性能数据
        with self._performance_lock:
            if len(self._performance_window) < 10:
                return False

        return True

    def calculate_optimal_batch_size(self) -> tuple[int, str, str]:
        """计算最优batch_size

        Returns:
            (new_batch_size, reason, details)
        """
        if not self._engine:
            return 0, "no_engine", "引擎未初始化"

        # 计算错误率
        with self._performance_lock:
            recent_batches = list(self._performance_window)[-50:]  # 最近50批

        error_count = sum(1 for b in recent_batches if not b["success"])
        error_rate = error_count / len(recent_batches) if recent_batches else 0

        current_batch_size = self._engine.batch_size

        # 如果错误率过高，减小batch_size
        if error_rate > self._error_rate_threshold:
            new_size = max(current_batch_size // 2, 1024)
            reason = "high_error_rate"
            details = f"错误率{error_rate:.2%}超过阈值{self._error_rate_threshold:.2%}"
            return new_size, reason, details

        # 计算平均吞吐量
        avg_throughput = sum(b["throughput"] for b in recent_batches) / len(recent_batches)

        # 如果性能良好，尝试增加batch_size
        if avg_throughput > 1_000_000:  # 每秒100万密钥
            new_size = min(current_batch_size * 2, 16 * 1024 * 1024)  # 最大16M
            reason = "good_performance"
            details = f"平均吞吐量{avg_throughput:,.0f} keys/s，性能良好"
            return new_size, reason, details

        # 性能一般，保持当前batch_size
        reason = "stable_performance"
        details = f"平均吞吐量{avg_throughput:,.0f} keys/s，性能稳定"
        return current_batch_size, reason, details

    def adjust_batch_size(self) -> bool:
        """执行batch_size调整

        Returns:
            True表示执行了调整，False表示未调整
        """
        if not self.should_adjust_batch_size():
            return False

        assert self._engine is not None
        old_size = self._engine.batch_size
        new_size, reason, details = self.calculate_optimal_batch_size()

        if new_size != old_size:
            # 执行调整
            try:
                self._engine.batch_size = new_size
                self._last_adjust_time = time.time()

                # 记录调整历史
                self.record_adjustment(old_size, new_size, reason, details)

                logger.info(
                    f"batch_size调整: {old_size:,} -> {new_size:,} (原因: {reason}, 详情: {details})"
                )

                return True
            except Exception as e:
                logger.error(f"调整batch_size失败: {e}")
                return False

        return False

    def get_performance_stats(self) -> dict[str, Any]:
        """获取性能统计信息

        Returns:
            性能统计字典
        """
        with self._performance_lock:
            performance_data = list(self._performance_window)

        if not performance_data:
            return {
                "total_batches": 0,
                "success_rate": 0.0,
                "avg_batch_time": 0.0,
                "avg_throughput": 0.0,
                "max_throughput": 0.0,
                "min_throughput": 0.0,
            }

        total_batches = len(performance_data)
        success_count = sum(1 for b in performance_data if b["success"])
        success_rate = success_count / total_batches

        avg_batch_time = sum(b["batch_time"] for b in performance_data) / total_batches
        avg_throughput = sum(b["throughput"] for b in performance_data) / total_batches
        max_throughput = max(b["throughput"] for b in performance_data)
        min_throughput = min(b["throughput"] for b in performance_data)

        return {
            "total_batches": total_batches,
            "success_rate": round(success_rate, 4),
            "avg_batch_time": round(avg_batch_time, 4),
            "avg_throughput": round(avg_throughput, 2),
            "max_throughput": round(max_throughput, 2),
            "min_throughput": round(min_throughput, 2),
        }

    def clear_performance_data(self) -> None:
        """清空性能数据"""
        with self._performance_lock:
            self._performance_window.clear()
        logger.debug("性能数据已清空")
