"""GPU引擎监控模块

负责追踪和报告 GPU 碰撞引擎的运行状态，包括：
- batch_size 调整历史记录
- 引擎运行状态快照
- 性能调整统计汇总

职责边界:
- 本模块仅负责引擎层面的监控数据管理（调整历史、状态摘要）
- GPU设备层性能指标 → performance_optimizer.py (PerformanceMetrics)
- 数据质量监控 → data_monitor.py (DataMonitor)
- 详细性能报告 → performance_reporter.py (PerformanceReportGenerator)
"""

import time
import threading
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # 避免循环导入：仅在类型检查时引用引擎
    from ..collision.gpu_collision_engine import GPUCollisionEngine

logger = logging.getLogger(__name__)


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

    def __init__(self, engine: Optional["GPUCollisionEngine"] = None):
        """初始化引擎监控器

        Args:
            engine: GPU碰撞引擎实例（可选）。传入后可通过
                    :meth:`get_engine_status` 获取实时状态摘要。
        """
        self._engine = engine

        # 调整历史存储
        self._adjustment_history: List[Dict[str, Any]] = []
        self._adjustment_history_lock = threading.Lock()

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

        record: Dict[str, Any] = {
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
            if len(self._adjustment_history) > 100:
                self._adjustment_history = self._adjustment_history[-100:]

        logger.debug(
            "batch_size 调整记录: %s -> %s (%+.1f%%) - %s",
            f"{old_size:,}",
            f"{new_size:,}",
            change_percent,
            reason,
        )

    def get_adjustment_history(self, limit: int = 10) -> List[Dict[str, Any]]:
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

    def get_adjustment_stats(self) -> Dict[str, Any]:
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
            return sum(
                1 for adj in self._adjustment_history
                if adj.get('timestamp', 0) >= cutoff
            )

    def clear_adjustment_history(self) -> None:
        """清空调整历史（重置统计）"""
        with self._adjustment_history_lock:
            self._adjustment_history.clear()
        logger.debug("调整历史已清空")

    # ------------------------------------------------------------------
    # 引擎状态快照
    # ------------------------------------------------------------------

    def get_engine_status(self) -> Dict[str, Any]:
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
        except Exception:
            is_running = False

        try:
            batch_size = engine.batch_size
        except Exception:
            batch_size = None

        try:
            device_info = engine.get_device_info() if hasattr(engine, "get_device_info") else {}
        except Exception:
            device_info = {}

        try:
            stats = engine.get_stats() if hasattr(engine, "get_stats") else None
            stats_snapshot = stats.snapshot() if stats and hasattr(stats, "snapshot") else None
        except Exception:
            stats_snapshot = None

        return {
            "engine_available": True,
            "is_running": is_running,
            "batch_size": batch_size,
            "device_info": device_info,
            "stats_snapshot": stats_snapshot,
            "adjustment_stats": self.get_adjustment_stats(),
        }
